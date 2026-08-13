"""
Radiación / balance energético (eje UBA).

Resumen operativo a partir de Open-Meteo:
  GHI = shortwave_radiation
  DNI ≈ direct_radiation
  DHI = diffuse_radiation
  Rn  = Rns − Rnl  (balance neto, estilo FAO-56 + Stefan–Boltzmann)
  Air Mass + Beer–Lambert (atenuación atmosférica / nubes)
  PAR en µmol/m²/s (conteo de fotones)
"""
from __future__ import annotations

import math
from datetime import date
from typing import Any


_SOLAR_CONSTANT = 1367.0
_PAR_FRAC = 0.45
_PAR_UMOL_PER_W = 4.57  # µmol/s por W (banda PAR, aprox. McCree)
_SIGMA = 5.670374419e-8  # W/m²/K⁴ Stefan–Boltzmann
_ALBEDO_CULTIVO = 0.23
_LAMBDA_VAP = 2.45e6  # J/kg calor latente vaporización (~20 °C)
_TAU_CLEAR = 0.15  # profundidad óptica típica cielo limpio (Beer–Lambert)


def _f(v, default=0.0) -> float:
    try:
        if v is None:
            return float(default)
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _serie(hourly: dict, key: str) -> list:
    raw = hourly.get(key) or []
    return list(raw) if isinstance(raw, list) else []


def _solar_geometry(lat: float, doy: int, hora_local: float) -> dict[str, float]:
    """Ángulo cenital, cos(z) e irradiancia TOA horizontal aproximada."""
    phi = math.radians(lat)
    delta = math.radians(23.45 * math.sin(math.radians(360.0 * (284 + doy) / 365.0)))
    omega = math.radians(15.0 * (hora_local - 12.0))
    cos_z = (
        math.sin(phi) * math.sin(delta)
        + math.cos(phi) * math.cos(delta) * math.cos(omega)
    )
    cos_z = max(-1.0, min(1.0, cos_z))
    z_deg = math.degrees(math.acos(cos_z)) if cos_z > -1 else 180.0
    if cos_z <= 0:
        return {'cos_z': 0.0, 'zenith_deg': z_deg, 'g0': 0.0}
    e0 = 1.0 + 0.033 * math.cos(math.radians(360.0 * doy / 365.0))
    g0 = _SOLAR_CONSTANT * e0 * cos_z
    return {'cos_z': cos_z, 'zenith_deg': z_deg, 'g0': g0}


def _g0_toa_aproximado(lat: float, doy: int, hora_local: float) -> float:
    """Irradiancia extraterrestre aproximada sobre plano horizontal (W/m²)."""
    return _solar_geometry(lat, doy, hora_local)['g0']


def air_mass(zenith_deg: float) -> float:
    """
    Masa óptica relativa (Kasten & Young 1989).
    AM≈1 con sol en el cenit; crece al atardecer → más atmósfera en el camino.
    """
    z = max(0.0, min(90.0, _f(zenith_deg)))
    if z >= 90.0:
        return 40.0
    # AM = 1 / (cos z + 0.50572*(96.07995−z)^−1.6364)
    return 1.0 / (math.cos(math.radians(z)) + 0.50572 * ((96.07995 - z) ** -1.6364))


def beer_lambert_transmitancia(air_mass_val: float, tau: float = _TAU_CLEAR) -> float:
    """T = exp(−τ · AM) — atenuación Beer–Lambert en la columna atmosférica."""
    am = max(0.0, _f(air_mass_val))
    tau_v = max(0.0, _f(tau, _TAU_CLEAR))
    return math.exp(-tau_v * am)


def _parse_hora_doy(times: list, idx: int) -> tuple[int, float]:
    doy, hora_local = 1, float(idx % 24)
    if times and idx < len(times):
        t = str(times[idx])
        try:
            parts = t[:10].split('-')
            d = date(int(parts[0]), int(parts[1]), int(parts[2]))
            doy = d.timetuple().tm_yday
        except Exception:
            pass
        try:
            hora_local = float(t[11:13]) + float(t[14:16]) / 60.0
        except Exception:
            pass
    return doy, hora_local


def _rn_a_mm_h(rn_wm2: float) -> float:
    """Equivalente evaporativo si todo Rn → calor latente (mm/h)."""
    return _f(rn_wm2) * 3600.0 / _LAMBDA_VAP


def _integral_dia(short_h: list, times: list, idx: int, umbral: float):
    """Suma Wh/m² del día calendario de idx (o próximas 24 h)."""
    if not short_h:
        return 0.0, 0
    idx = max(0, min(idx, len(short_h) - 1))
    dia_ref = str(times[idx])[:10] if times and idx < len(times) else None
    suma = 0.0
    horas = 0
    if dia_ref:
        for i, g in enumerate(short_h):
            t = str(times[i]) if i < len(times) else ''
            if not t.startswith(dia_ref):
                continue
            gv = _f(g)
            suma += gv
            if gv >= umbral:
                horas += 1
    else:
        for i in range(idx, min(idx + 24, len(short_h))):
            gv = _f(short_h[i])
            suma += gv
            if gv >= umbral:
                horas += 1
    return suma, horas


def _presion_vapor_saturacion_kpa(t_c: float) -> float:
    """es(T) Tetens, kPa."""
    return 0.6108 * math.exp((17.27 * t_c) / (t_c + 237.3))


def estimar_albedo(
    humedad_sup: float | None = None,
    *,
    albedo_base: float = _ALBEDO_CULTIVO,
) -> dict[str, Any]:
    """
    Albedo efectivo de cultivo (~0.23) ajustado por humedad superficial.
    Suelo más húmedo → refleja menos (albedo baja).
    humedad_sup: fracción volumétrica 0–1 (Open-Meteo soil_moisture).
    """
    base = max(0.12, min(0.40, _f(albedo_base, _ALBEDO_CULTIVO)))
    if humedad_sup is None:
        return {
            'albedo': round(base, 3),
            'albedo_pct': round(base * 100, 1),
            'albedo_fuente': 'cultivo (α≈0.23)',
            'humedad_sup_pct': None,
        }
    theta = max(0.0, min(0.55, _f(humedad_sup)))
    # Ajuste ±0.05 alrededor del base según humedad relativa a ~0.28 (franco húmedo)
    factor = (theta - 0.14) / 0.20  # 0 en marchitez aprox., 1 cerca de FC
    factor = max(0.0, min(1.0, factor))
    alpha = base + 0.05 * (1.0 - factor) - 0.03 * factor
    alpha = max(0.15, min(0.32, alpha))
    return {
        'albedo': round(alpha, 3),
        'albedo_pct': round(alpha * 100, 1),
        'albedo_fuente': 'cultivo + humedad superficial',
        'humedad_sup_pct': round(theta * 100, 1),
    }


def balance_radiativo_neto(
    ghi: float,
    *,
    temp_aire: float = 20.0,
    temp_suelo: float | None = None,
    humedad_rel: float = 50.0,
    albedo: float = _ALBEDO_CULTIVO,
    g0: float | None = None,
    kt: float | None = None,
) -> dict[str, Any]:
    """
    Rn = Rns − Rnl (W/m²), aproximación operativa estilo FAO-56.

    Rns = (1 − α) · Rs
    Rnl = σ Ta⁴ (0.34 − 0.14√ea) · f_nubosidad
         + corrección leve con emisión de suelo σ ε Ts⁴ vs aire.
    """
    rs = max(0.0, _f(ghi))
    alpha = max(0.05, min(0.45, _f(albedo, _ALBEDO_CULTIVO)))
    rns = (1.0 - alpha) * rs

    ta = _f(temp_aire, 20.0)
    ts = _f(temp_suelo, ta) if temp_suelo is not None else ta
    rh = max(1.0, min(100.0, _f(humedad_rel, 50.0)))
    ea = _presion_vapor_saturacion_kpa(ta) * (rh / 100.0)
    ea = max(0.05, ea)

    ta_k = ta + 273.16
    ts_k = ts + 273.16

    # Factor de claridad / nubosidad (FAO-56)
    if kt is not None and kt > 0:
        clearness = max(0.05, min(1.05, _f(kt)))
    elif g0 and g0 > 50:
        clearness = max(0.05, min(1.05, rs / _f(g0)))
    else:
        clearness = 0.75 if rs > 50 else 0.3
    f_cloud = max(0.05, min(1.0, 1.35 * clearness - 0.35))

    # Emisión neta atmosférica (FAO) + término suelo (onda larga saliente relativa)
    rnl_atm = _SIGMA * (ta_k ** 4) * (0.34 - 0.14 * math.sqrt(ea)) * f_cloud
    eps_s = 0.98
    # Diferencia suelo−aire: si el suelo está más caliente, aumenta la pérdida neta LW
    rnl_suelo = eps_s * _SIGMA * ((ts_k ** 4) - (ta_k ** 4))
    rnl = rnl_atm + 0.5 * rnl_suelo  # peso parcial del término suelo

    rn = rns - rnl

    if rn >= 150:
        rn_label, rn_color = 'Fuerte ganancia', '#facc15'
    elif rn >= 40:
        rn_label, rn_color = 'Ganancia moderada', '#4ade80'
    elif rn >= -20:
        rn_label, rn_color = 'Casi equilibrado', '#94a3b8'
    else:
        rn_label, rn_color = 'Pérdida neta', '#60a5fa'

    # Emisión terrestre Stefan–Boltzmann (onda larga saliente bruta)
    lw_up = eps_s * _SIGMA * (ts_k ** 4)
    evap_mm_h = _rn_a_mm_h(max(0.0, rn))

    return {
        'rns': round(rns, 1),
        'rnl': round(rnl, 1),
        'rn': round(rn, 1),
        'rn_label': rn_label,
        'rn_color': rn_color,
        'ea_kpa': round(ea, 3),
        'temp_aire': round(ta, 1),
        'temp_suelo': round(ts, 1),
        'f_cloud': round(f_cloud, 3),
        'lw_up_stefan': round(lw_up, 1),
        'eps_suelo': eps_s,
        'evap_mm_h': round(evap_mm_h, 3),
    }


def resumen_radiacion(
    current: dict,
    hourly: dict,
    idx: int = 0,
    *,
    lat: float = -34.6,
    umbral_util: float = 200.0,
    area_m2: float = 20.0,
    eficiencia: float = 0.18,
    loss_factor: float = 1.0,
    temp_aire: float | None = None,
    temp_suelo: float | None = None,
    humedad_rel: float | None = None,
    humedad_suelo_sup: float | None = None,
    albedo: float | None = None,
) -> dict[str, Any]:
    """Dict listo para template (panel Plus+)."""
    ghi = _f(current.get('shortwave_radiation'))
    dni = _f(current.get('direct_radiation'))
    dhi = _f(current.get('diffuse_radiation'))
    if dhi <= 0 and ghi > 0:
        dhi = max(0.0, ghi - dni)

    fraccion_difusa = (dhi / ghi) if ghi > 1 else 0.0
    par_wm2 = ghi * _PAR_FRAC
    par_umol = par_wm2 * _PAR_UMOL_PER_W

    short_h = _serie(hourly, 'shortwave_radiation')
    times = _serie(hourly, 'time')
    n = len(short_h)
    idx = max(0, min(idx, n - 1)) if n else 0

    suma_wh, horas_utiles = _integral_dia(short_h, times, idx, umbral_util)
    if suma_wh <= 0 and ghi > 0 and not short_h:
        suma_wh = ghi * 12  # proxy si no hay serie
        horas_utiles = 1 if ghi >= umbral_util else 0

    mj_dia = round(suma_wh * 0.0036, 2)

    doy, hora_local = _parse_hora_doy(times, idx)
    geo = _solar_geometry(lat, doy, hora_local)
    g0_now = geo['g0']
    zenith = geo['zenith_deg']
    am_now = air_mass(zenith) if geo['cos_z'] > 0 else None
    t_clear = beer_lambert_transmitancia(am_now, _TAU_CLEAR) if am_now else 0.0
    ghi_beer_clear = round(g0_now * t_clear, 1) if g0_now > 0 else 0.0

    # Profundidad óptica efectiva observada (atmósfera + nubes) vía Beer–Lambert inversa
    tau_eff = None
    if am_now and am_now > 0.3 and g0_now > 80 and ghi > 5:
        ratio = max(1e-4, min(0.999, ghi / g0_now))
        tau_eff = round(-math.log(ratio) / am_now, 3)

    kt = round(ghi / g0_now, 3) if g0_now > 50 and ghi >= 0 else None

    if kt is None:
        kt_label, kt_color = 'N/D', '#94a3b8'
    elif kt >= 0.65:
        kt_label, kt_color = 'Cielo claro', '#facc15'
    elif kt >= 0.35:
        kt_label, kt_color = 'Parcialmente nublado', '#fbbf24'
    else:
        kt_label, kt_color = 'Nublado / difuso', '#64748b'

    kwh_est = round(mj_dia * area_m2 * eficiencia * max(0.0, loss_factor) / 3.6, 2)

    # Temperaturas / humedad desde current si no se pasan
    ta = _f(temp_aire if temp_aire is not None else current.get('temperature_2m'), 20.0)
    ts_raw = temp_suelo if temp_suelo is not None else current.get('soil_temperature_0cm')
    if ts_raw is None:
        ts_raw = current.get('soil_temperature_6cm')
    ts = _f(ts_raw, ta) if ts_raw is not None else ta
    rh = _f(humedad_rel if humedad_rel is not None else current.get('relative_humidity_2m'), 50.0)
    theta_sup = humedad_suelo_sup
    if theta_sup is None and current.get('soil_moisture_0_to_1cm') is not None:
        theta_sup = current.get('soil_moisture_0_to_1cm')

    alb = estimar_albedo(theta_sup, albedo_base=albedo if albedo is not None else _ALBEDO_CULTIVO)
    bal = balance_radiativo_neto(
        ghi,
        temp_aire=ta,
        temp_suelo=ts,
        humedad_rel=rh,
        albedo=alb['albedo'],
        g0=g0_now,
        kt=kt,
    )

    # Series 24 h: GHI, G0, Beer claro, AM, Rns/Rnl/Rn
    temp_h = _serie(hourly, 'temperature_2m')
    rh_h = _serie(hourly, 'relative_humidity_2m')
    i0 = idx
    i1 = min(idx + 24, len(short_h)) if short_h else idx
    labels_h: list[str] = []
    serie_ghi: list[float] = []
    serie_g0: list[float] = []
    serie_beer: list[float] = []
    serie_am: list[float] = []
    serie_rns: list[float] = []
    serie_rnl: list[float] = []
    serie_rn: list[float] = []
    rn_pos_wh = 0.0

    for i in range(i0, i1):
        tstr = str(times[i]) if i < len(times) else ''
        labels_h.append(tstr[11:16] if len(tstr) >= 16 else str(i - i0))
        g = _f(short_h[i]) if i < len(short_h) else 0.0
        serie_ghi.append(round(g, 1))
        d_i, h_i = _parse_hora_doy(times, i)
        geo_i = _solar_geometry(lat, d_i, h_i)
        g0_i = geo_i['g0']
        serie_g0.append(round(g0_i, 1))
        am_i = air_mass(geo_i['zenith_deg']) if geo_i['cos_z'] > 0 else 0.0
        serie_am.append(round(am_i, 2) if am_i else 0.0)
        beer_i = g0_i * beer_lambert_transmitancia(am_i, _TAU_CLEAR) if g0_i > 0 else 0.0
        serie_beer.append(round(beer_i, 1))

        ta_i = _f(temp_h[i] if i < len(temp_h) else None, ta)
        rh_i = _f(rh_h[i] if i < len(rh_h) else None, rh)
        kt_i = (g / g0_i) if g0_i > 50 else None
        bal_i = balance_radiativo_neto(
            g,
            temp_aire=ta_i,
            temp_suelo=ts,
            humedad_rel=rh_i,
            albedo=alb['albedo'],
            g0=g0_i,
            kt=kt_i,
        )
        serie_rns.append(bal_i['rns'])
        serie_rnl.append(bal_i['rnl'])
        serie_rn.append(bal_i['rn'])
        if bal_i['rn'] > 0:
            rn_pos_wh += bal_i['rn']

    def _stats(vals: list, labs: list) -> dict:
        if not vals:
            return {'ahora': None, 'max': None, 'max_hora': None, 'min': None}
        ahora = vals[0]
        i_max = max(range(len(vals)), key=lambda i: vals[i] if vals[i] is not None else float('-inf'))
        i_min = min(range(len(vals)), key=lambda i: vals[i] if vals[i] is not None else float('inf'))
        return {
            'ahora': vals[0],
            'max': vals[i_max],
            'max_hora': labs[i_max] if i_max < len(labs) else None,
            'min': vals[i_min],
            'min_hora': labs[i_min] if i_min < len(labs) else None,
        }

    st_g0 = _stats(serie_g0, labels_h)
    st_beer = _stats(serie_beer, labels_h)
    st_ghi = _stats(serie_ghi, labels_h)
    st_rns = _stats(serie_rns, labels_h)
    st_rnl = _stats(serie_rnl, labels_h)
    st_rn = _stats(serie_rn, labels_h)

    # mm/día si todo Rn>0 se destinara a evaporación (cota superior)
    evap_mm_dia = round(rn_pos_wh * 3600.0 / _LAMBDA_VAP, 2)
    # Fracción agro típica hacia LE (~60–80% de Rn diurno); usamos 0.7
    evap_mm_dia_le = round(evap_mm_dia * 0.7, 2)

    return {
        'ghi': round(ghi, 1),
        'dni': round(dni, 1),
        'dhi': round(dhi, 1),
        'fraccion_difusa': round(fraccion_difusa, 3),
        'fraccion_difusa_pct': round(fraccion_difusa * 100, 1),
        'par_wm2': round(par_wm2, 1),
        'par_umol': round(par_umol, 0),
        'par_fotones_nota': (
            'µmol/m²/s cuenta fotones (cuántica). Las plantas absorben cuantos en 400–700 nm; '
            'no metabolizan Watts de calor ondulatorio.'
        ),
        'mj_dia': mj_dia,
        'horas_utiles': horas_utiles,
        'umbral_util': umbral_util,
        'kt': kt,
        'kt_label': kt_label,
        'kt_color': kt_color,
        'energia_diaria_kwh': kwh_est,
        'serie_ghi_24': serie_ghi,
        'serie_labels_24': labels_h,
        'serie_g0_24': serie_g0,
        'serie_beer_24': serie_beer,
        'serie_am_24': serie_am,
        'serie_rns_24': serie_rns,
        'serie_rnl_24': serie_rnl,
        'serie_rn_24': serie_rn,
        'chart_beer': {
            'g0': st_g0,
            'beer': st_beer,
            'ghi': st_ghi,
        },
        'chart_rn': {
            'rns': st_rns,
            'rnl': st_rnl,
            'rn': st_rn,
        },
        # Air Mass / Beer–Lambert
        'zenith_deg': round(zenith, 1),
        'air_mass': round(am_now, 2) if am_now is not None else None,
        'tau_clear': _TAU_CLEAR,
        'tau_eff': tau_eff,
        'transmitancia_clear': round(t_clear, 3) if am_now else None,
        'ghi_beer_clear': ghi_beer_clear,
        'g0': round(g0_now, 1),
        # Balance radiativo
        'albedo': alb['albedo'],
        'albedo_pct': alb['albedo_pct'],
        'albedo_fuente': alb['albedo_fuente'],
        'humedad_sup_pct': alb.get('humedad_sup_pct'),
        'rns': bal['rns'],
        'rnl': bal['rnl'],
        'rn': bal['rn'],
        'rn_label': bal['rn_label'],
        'rn_color': bal['rn_color'],
        'rn_temp_aire': bal['temp_aire'],
        'rn_temp_suelo': bal['temp_suelo'],
        'rn_ea_kpa': bal['ea_kpa'],
        'lw_up_stefan': bal['lw_up_stefan'],
        'eps_suelo': bal['eps_suelo'],
        'evap_mm_h': bal['evap_mm_h'],
        'evap_mm_dia_max': evap_mm_dia,
        'evap_mm_dia_le': evap_mm_dia_le,
    }
