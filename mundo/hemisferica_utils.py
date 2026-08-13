r"""
Circulación hemisférica: flujo de calor eddy v'T' (media zonal),
actividad de storm tracks (local) y corriente en chorro (perfil U).

Fuentes:
  - Archive Open-Meteo: malla zonal + SLP/v en el punto (storm tracks)
  - Forecast Open-Meteo: U en niveles de presión (jet / time–height)
"""
from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from typing import Any, Callable, Optional

from django.core.cache import cache as django_cache

FetchJson = Callable[[str], Any]

_LONS = (0.0, 90.0, 180.0, -90.0)
_LATS_N = (20.0, 35.0, 45.0, 55.0, 65.0)
_LATS_S = (-20.0, -35.0, -45.0, -55.0, -65.0)

_CLIM_PICO_VT = {
    'N': [2.8, 2.4, 1.8, 1.2, 0.8, 0.6, 0.5, 0.6, 1.0, 1.6, 2.2, 2.7],
    'S': [0.7, 0.8, 1.2, 1.8, 2.4, 2.8, 2.9, 2.6, 2.0, 1.4, 0.9, 0.7],
}

# Niveles para U (hPa), superficie ≈ 10 m etiquetada 1013
_JET_LEVELS = (1000, 925, 850, 700, 500, 400, 300, 250, 200)
_HP_WINDOW_H = 120  # ~5 días para high-pass (eddies transientes)


def _f(v, default=None) -> Optional[float]:
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5


def _v_meridional(speed_kmh: float, direction_deg: float) -> float:
    """Viento hacia el norte (m/s)."""
    spd = speed_kmh / 3.6
    th = math.radians(direction_deg)
    return -spd * math.cos(th)


def _u_zonal(speed_kmh: float, direction_deg: float) -> float:
    """Viento hacia el este (m/s)."""
    spd = speed_kmh / 3.6
    th = math.radians(direction_deg)
    return -spd * math.sin(th)


def _ms_to_kt(ms: float) -> float:
    return ms * 1.94384


def _high_pass(xs: list[float], window: int = _HP_WINDOW_H) -> list[float]:
    """Resta media móvil centrada (aprox. high-pass synoptic)."""
    n = len(xs)
    if n == 0:
        return []
    w = max(3, min(window, n if n % 2 == 1 else n - 1))
    half = w // 2
    out: list[float] = []
    for i in range(n):
        a = max(0, i - half)
        b = min(n, i + half + 1)
        out.append(xs[i] - _mean(xs[a:b]))
    return out


def _fetch_punto(lat: float, lon: float, start: date, end: date, fetch: FetchJson) -> Optional[dict]:
    url = (
        'https://archive-api.open-meteo.com/v1/archive'
        f'?latitude={lat}&longitude={lon}'
        f'&start_date={start.isoformat()}&end_date={end.isoformat()}'
        '&hourly=temperature_2m,wind_speed_10m,wind_direction_10m'
        '&timezone=UTC'
    )
    try:
        data = fetch(url)
    except Exception:
        return None
    hourly = (data or {}).get('hourly') or {}
    times = hourly.get('time') or []
    temps = hourly.get('temperature_2m') or []
    speeds = hourly.get('wind_speed_10m') or []
    dirs = hourly.get('wind_direction_10m') or []
    if not times:
        return None

    by_day: dict[str, list[tuple[float, float]]] = {}
    for i, t in enumerate(times):
        day = str(t)[:10]
        T = _f(temps[i] if i < len(temps) else None)
        sp = _f(speeds[i] if i < len(speeds) else None)
        di = _f(dirs[i] if i < len(dirs) else None)
        if T is None or sp is None or di is None:
            continue
        by_day.setdefault(day, []).append((T, _v_meridional(sp, di)))

    daily_T: dict[str, float] = {}
    daily_v: dict[str, float] = {}
    for day, pairs in by_day.items():
        if len(pairs) < 8:
            continue
        daily_T[day] = _mean([p[0] for p in pairs])
        daily_v[day] = _mean([p[1] for p in pairs])
    if not daily_T:
        return None
    return {'lat': lat, 'lon': lon, 'T': daily_T, 'v': daily_v}


def _perfil_zonal(puntos: list[dict], lats: tuple[float, ...]) -> dict:
    by_lat: dict[float, list[dict]] = {la: [] for la in lats}
    for p in puntos:
        if p and p['lat'] in by_lat:
            by_lat[p['lat']].append(p)

    all_days: set[str] = set()
    for la in lats:
        for p in by_lat[la]:
            all_days |= set(p['T'].keys())
    days = sorted(all_days)
    if not days:
        return {'ok': False, 'error': 'Sin días válidos en la malla zonal'}

    perfil_vt: list[float] = []
    perfil_T: list[float] = []
    perfil_v: list[float] = []
    lats_out: list[float] = []

    for la in lats:
        pts = by_lat[la]
        if len(pts) < 2:
            continue
        vt_days: list[float] = []
        T_days: list[float] = []
        v_days: list[float] = []
        for day in days:
            Ts, vs = [], []
            for p in pts:
                if day in p['T'] and day in p['v']:
                    Ts.append(p['T'][day])
                    vs.append(p['v'][day])
            if len(Ts) < 2:
                continue
            Tbar, vbar = _mean(Ts), _mean(vs)
            cov = _mean([(vs[i] - vbar) * (Ts[i] - Tbar) for i in range(len(Ts))])
            vt_days.append(cov)
            T_days.append(Tbar)
            v_days.append(vbar)
        if not vt_days:
            continue
        lats_out.append(la)
        sign = 1.0 if la >= 0 else -1.0
        perfil_vt.append(round(sign * _mean(vt_days), 3))
        perfil_T.append(round(_mean(T_days), 2))
        perfil_v.append(round(_mean(v_days), 3))

    if not lats_out:
        return {'ok': False, 'error': 'Malla zonal insuficiente'}

    i_max = max(range(len(perfil_vt)), key=lambda i: perfil_vt[i])
    return {
        'ok': True,
        'lats': lats_out,
        'vt_polo': perfil_vt,
        'T_zonal': perfil_T,
        'v_zonal': perfil_v,
        'pico_lat': lats_out[i_max],
        'pico_vt': perfil_vt[i_max],
        'n_dias': len(days),
        'n_lons': len(_LONS),
    }


def _ciclo_estacional(hemisferio: str, mes: int) -> dict:
    clim = _CLIM_PICO_VT[hemisferio]
    labels = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    return {
        'labels': labels,
        'valores': clim,
        'mes_actual': mes,
        'valor_mes': clim[mes - 1],
    }


def _storm_tracks_local(lat: float, lon: float, fetch: FetchJson, *, dias: int = 21) -> dict:
    """
    Actividad de storm tracks sobre el usuario:
    varianza high-pass (~5 d) de pressure_msl y del viento meridional.
    """
    hoy = date.today()
    end = hoy - timedelta(days=2)
    start = end - timedelta(days=max(14, min(dias, 28)) - 1)
    cache_key = f'tc_storm_{round(lat, 2)}_{round(lon, 2)}_{start}_{end}_v1'
    cached = django_cache.get(cache_key)
    if cached:
        out = dict(cached)
        out['desde_cache'] = True
        return out

    url = (
        'https://archive-api.open-meteo.com/v1/archive'
        f'?latitude={lat}&longitude={lon}'
        f'&start_date={start.isoformat()}&end_date={end.isoformat()}'
        '&hourly=pressure_msl,wind_speed_10m,wind_direction_10m'
        '&timezone=UTC'
    )
    try:
        data = fetch(url)
    except Exception as e:
        return {'ok': False, 'error': str(e)[:120]}

    hourly = (data or {}).get('hourly') or {}
    times = hourly.get('time') or []
    p_raw = hourly.get('pressure_msl') or []
    speeds = hourly.get('wind_speed_10m') or []
    dirs = hourly.get('wind_direction_10m') or []
    if len(times) < 48:
        return {'ok': False, 'error': 'Serie horaria insuficiente para storm tracks'}

    p_list: list[float] = []
    v_list: list[float] = []
    t_ok: list[str] = []
    for i, t in enumerate(times):
        p = _f(p_raw[i] if i < len(p_raw) else None)
        sp = _f(speeds[i] if i < len(speeds) else None)
        di = _f(dirs[i] if i < len(dirs) else None)
        if p is None or sp is None or di is None:
            continue
        p_list.append(p)
        v_list.append(_v_meridional(sp, di))
        t_ok.append(str(t))

    if len(p_list) < 48:
        return {'ok': False, 'error': 'Datos SLP/v incompletos'}

    p_hp = _high_pass(p_list)
    v_hp = _high_pass(v_list)
    sigma_p = _std(p_hp)
    sigma_v = _std(v_hp)

    # Score 0–100 (midlatitudes): σ_SLP ~6 hPa y σ_v ~5 m/s ≈ actividad alta
    score_p = min(100.0, (sigma_p / 6.0) * 100.0)
    score_v = min(100.0, (sigma_v / 5.0) * 100.0)
    indice = round(0.55 * score_p + 0.45 * score_v, 1)

    if indice >= 75:
        label, color = 'Muy alta', '#f87171'
    elif indice >= 50:
        label, color = 'Alta', '#fb923c'
    elif indice >= 25:
        label, color = 'Moderada', '#fbbf24'
    else:
        label, color = 'Baja', '#67e8f9'

    # Varianza diaria de SLP' (para sparkline)
    by_day: dict[str, list[float]] = {}
    for i, t in enumerate(t_ok):
        by_day.setdefault(t[:10], []).append(p_hp[i])
    dias_lab, var_diaria = [], []
    for day in sorted(by_day.keys()):
        xs = by_day[day]
        if len(xs) < 8:
            continue
        dias_lab.append(day[5:])  # MM-DD
        var_diaria.append(round(_std(xs) ** 2, 2))

    out = {
        'ok': True,
        'indice': indice,
        'label': label,
        'color': color,
        'sigma_slp': round(sigma_p, 2),
        'sigma_v': round(sigma_v, 2),
        'unidad_slp': 'hPa',
        'unidad_v': 'm/s',
        'desde': start.isoformat(),
        'hasta': end.isoformat(),
        'n_horas': len(p_list),
        'dias_labels': dias_lab,
        'var_slp_diaria': var_diaria,
        'filtro': 'high-pass ~5 días (media móvil)',
        'nota': (
            'Alta varianza de SLP′ y v′ ⇒ muchos eddies transientes '
            '(frentes / tormentas) cruzando el punto en las últimas semanas.'
        ),
        'desde_cache': False,
    }
    django_cache.set(cache_key, out, 6 * 3600)
    return out


def _jet_meridional_u250(lat: float, lon: float, fetch: FetchJson) -> dict:
    """Perfil meridional de U a 250 hPa a lo largo de la longitud del usuario."""
    hemi = 'S' if lat < 0 else 'N'
    if hemi == 'S':
        lats = [-20.0, -30.0, -35.0, -40.0, -45.0, -50.0, -55.0, -60.0]
    else:
        lats = [20.0, 30.0, 35.0, 40.0, 45.0, 50.0, 55.0, 60.0]

    def one(la: float) -> Optional[tuple[float, float]]:
        url = (
            'https://api.open-meteo.com/v1/forecast'
            f'?latitude={la}&longitude={lon}'
            '&hourly=wind_speed_250hPa,wind_direction_250hPa'
            '&forecast_days=1&past_days=0&timezone=UTC'
        )
        try:
            data = fetch(url)
        except Exception:
            return None
        h = (data or {}).get('hourly') or {}
        speeds = h.get('wind_speed_250hPa') or []
        dirs = h.get('wind_direction_250hPa') or []
        us = []
        for i in range(min(len(speeds), len(dirs), 12)):
            sp, di = _f(speeds[i]), _f(dirs[i])
            if sp is None or di is None:
                continue
            us.append(_u_zonal(sp, di))
        if not us:
            return None
        return la, _mean(us)

    lats_out, u_kt = [], []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(one, la): la for la in lats}
        results = []
        for fut in as_completed(futs):
            try:
                r = fut.result()
            except Exception:
                r = None
            if r:
                results.append(r)
    for la, u_ms in sorted(results, key=lambda x: x[0]):
        lats_out.append(la)
        u_kt.append(round(_ms_to_kt(u_ms), 1))

    if not lats_out:
        return {'ok': False}
    # Jet core = máximo |U| (oeste intenso en midlatitudes → U negativo en SH a veces;
    # usamos magnitud del zonal hacia el este; en SH el jet es westerly = U > 0 in meteorological
    # convention with u eastward — westerlies are positive U)
    i_max = max(range(len(u_kt)), key=lambda i: abs(u_kt[i]))
    return {
        'ok': True,
        'lats': lats_out,
        'U250_kt': u_kt,
        'jet_lat': lats_out[i_max],
        'jet_U250_kt': u_kt[i_max],
        'lat_usuario': round(float(lat), 3),
    }


def _jet_stream_u(lat: float, lon: float, fetch: FetchJson) -> dict:
    """
    Perfil vertical y sección tiempo–presión de U (kt) desde ~sfc hasta 200 hPa.
    """
    cache_key = f'tc_jet_u_{round(lat, 2)}_{round(lon, 2)}_{date.today().isoformat()}_v1'
    cached = django_cache.get(cache_key)
    if cached:
        out = dict(cached)
        out['desde_cache'] = True
        return out

    hourly_vars = ['wind_speed_10m', 'wind_direction_10m']
    for lev in _JET_LEVELS:
        hourly_vars.append(f'wind_speed_{lev}hPa')
        hourly_vars.append(f'wind_direction_{lev}hPa')

    url = (
        'https://api.open-meteo.com/v1/forecast'
        f'?latitude={lat}&longitude={lon}'
        f'&hourly={",".join(hourly_vars)}'
        '&past_days=7&forecast_days=2&timezone=UTC'
    )
    try:
        data = fetch(url)
    except Exception as e:
        return {'ok': False, 'error': str(e)[:120]}

    h = (data or {}).get('hourly') or {}
    times = h.get('time') or []
    if len(times) < 24:
        return {'ok': False, 'error': 'Sin perfil de viento en altura'}

    # Niveles display: 10 m como 1013, luego _JET_LEVELS
    levels_meta = [('10m', 1013)] + [(f'{lev}hPa', lev) for lev in _JET_LEVELS]
    # Series U (m/s) por nivel
    series_u: dict[str, list[Optional[float]]] = {}
    for key, _p in levels_meta:
        if key == '10m':
            sp_key, di_key = 'wind_speed_10m', 'wind_direction_10m'
        else:
            lev = key.replace('hPa', '')
            sp_key, di_key = f'wind_speed_{lev}hPa', f'wind_direction_{lev}hPa'
        speeds = h.get(sp_key) or []
        dirs = h.get(di_key) or []
        col: list[Optional[float]] = []
        for i in range(len(times)):
            sp = _f(speeds[i] if i < len(speeds) else None)
            di = _f(dirs[i] if i < len(dirs) else None)
            if sp is None or di is None:
                col.append(None)
            else:
                col.append(_u_zonal(sp, di))
        series_u[key] = col

    # Agregar a medias cada 6 h para heatmap manejable
    step = 6
    times_s: list[str] = []
    # matrix[level_idx][time_idx] en kt — niveles de arriba (200) a abajo (sfc)
    levels_plot = list(reversed(levels_meta))  # 200 … 10m
    matrix: list[list[Optional[float]]] = [[] for _ in levels_plot]

    for i0 in range(0, len(times), step):
        chunk = range(i0, min(i0 + step, len(times)))
        times_s.append(str(times[i0])[5:13].replace('T', ' '))  # MM-DD HH
        for li, (key, _p) in enumerate(levels_plot):
            vals = [series_u[key][i] for i in chunk if series_u[key][i] is not None]
            matrix[li].append(round(_ms_to_kt(_mean(vals)), 1) if vals else None)

    # Perfil "ahora" = última hora válida
    idx_now = len(times) - 1
    for i in range(len(times) - 1, -1, -1):
        if series_u['200hPa'][i] is not None:
            idx_now = i
            break

    perfil_levels = [p for _k, p in levels_plot]
    perfil_u_kt = []
    for key, _p in levels_plot:
        u = series_u[key][idx_now]
        perfil_u_kt.append(round(_ms_to_kt(u), 1) if u is not None else None)

    # Jet overhead: máx |U| entre 400–200 hPa
    jet_hPa, jet_u = None, None
    for key, p in levels_meta:
        if p > 400 or p < 200:
            continue
        u = series_u[key][idx_now]
        if u is None:
            continue
        ukt = abs(_ms_to_kt(u))
        if jet_u is None or ukt > jet_u:
            jet_u = round(_ms_to_kt(u), 1)
            jet_hPa = p

    # Media últimos 7 días del perfil
    perfil_mean = []
    for key, _p in levels_plot:
        vals = [x for x in series_u[key] if x is not None]
        perfil_mean.append(round(_ms_to_kt(_mean(vals)), 1) if vals else None)

    merid = _jet_meridional_u250(lat, lon, fetch)

    # Intensidad del chorro sobre el punto
    if jet_u is None:
        estado, color = 'N/D', '#94a3b8'
    elif abs(jet_u) >= 100:
        estado, color = 'Jet intenso', '#f87171'
    elif abs(jet_u) >= 70:
        estado, color = 'Jet moderado', '#fb923c'
    elif abs(jet_u) >= 40:
        estado, color = 'Jet débil', '#fbbf24'
    else:
        estado, color = 'Sin jet claro', '#94a3b8'

    out = {
        'ok': True,
        'levels_hPa': perfil_levels,
        'level_labels': [k for k, _p in levels_plot],
        'times': times_s,
        'U_kt_matrix': matrix,
        'perfil_ahora_kt': perfil_u_kt,
        'perfil_media_kt': perfil_mean,
        'jet_hPa': jet_hPa,
        'jet_U_kt': jet_u,
        'estado': estado,
        'color': color,
        'hora_perfil': str(times[idx_now]),
        'meridional': merid,
        'nota': (
            'U zonal (hacia el este) en kt. Sección tiempo–presión (paso 6 h, '
            'últimos 7 d + 2 d pronóstico). Núcleo del jet ≈ máximo |U| en 200–400 hPa.'
        ),
        'desde_cache': False,
    }
    django_cache.set(cache_key, out, 2 * 3600)
    return out


def _zonal_hemisferio(lat: float, fetch: FetchJson, *, dias: int = 21) -> dict:
    hemisferio = 'S' if lat < 0 else 'N'
    lats = _LATS_S if hemisferio == 'S' else _LATS_N
    hoy = date.today()
    end = hoy - timedelta(days=2)
    start = end - timedelta(days=max(10, min(dias, 28)) - 1)
    cache_key = f'tc_hemi_vt_{hemisferio}_{start}_{end}_v2'
    cached = django_cache.get(cache_key)
    if cached:
        out = dict(cached)
        out['desde_cache'] = True
        return out

    jobs = [(la, lo) for la in lats for lo in _LONS]
    puntos: list[dict] = []

    def _job(pair):
        la, lo = pair
        return _fetch_punto(la, lo, start, end, fetch)

    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(_job, j) for j in jobs]
        for fut in as_completed(futs):
            try:
                r = fut.result()
            except Exception:
                r = None
            if r:
                puntos.append(r)

    perfil = _perfil_zonal(puntos, lats)
    mes = end.month
    ciclo = _ciclo_estacional(hemisferio, mes)
    base = {
        'hemisferio': hemisferio,
        'hemisferio_label': 'Sur' if hemisferio == 'S' else 'Norte',
        'desde': start.isoformat(),
        'hasta': end.isoformat(),
        'nivel': '10 m / 2 m (proxy)',
        'ciclo': ciclo,
        'n_puntos': len(puntos),
    }
    if not perfil.get('ok'):
        out = {
            **base,
            'ok': False,
            'error': perfil.get('error', 'Sin datos'),
            'nota': (
                'Promedios zonales sobre paralelos enteros (malla 4×5). '
                'Proxy de superficie; el diagnóstico clásico usa ~850 hPa.'
            ),
            'desde_cache': False,
        }
        return out

    pico = perfil['pico_vt']
    ref = ciclo['valor_mes'] or 1.0
    ratio = pico / ref if ref else None
    if ratio is None:
        estado, color = 'N/D', '#94a3b8'
    elif ratio >= 1.25:
        estado, color = 'Eddy activo', '#f87171'
    elif ratio >= 0.85:
        estado, color = 'Cerca del clima', '#67e8f9'
    else:
        estado, color = 'Eddy débil', '#94a3b8'

    out = {
        **base,
        'ok': True,
        'lats': perfil['lats'],
        'vt_polo': perfil['vt_polo'],
        'T_zonal': perfil['T_zonal'],
        'v_zonal': perfil['v_zonal'],
        'pico_lat': perfil['pico_lat'],
        'pico_vt': perfil['pico_vt'],
        'n_dias': perfil['n_dias'],
        'n_lons': perfil['n_lons'],
        'ratio_clima': round(ratio, 2) if ratio is not None else None,
        'estado': estado,
        'color': color,
        'nota': (
            f'Media zonal sobre {perfil["n_lons"]} longitudes y {perfil["n_dias"]} días. '
            'Primos = desviación zonal del día; positivo = hacia el polo. Proxy superficie.'
        ),
        'desde_cache': False,
    }
    django_cache.set(cache_key, out, 6 * 3600)
    return out


def resumen_hemisferica(lat: float, lon: float, fetch: FetchJson, *, dias: int = 21) -> dict:
    """Diagnóstico hemisférico + storm tracks locales + jet stream (U)."""
    lat_f, lon_f = float(lat), float(lon)

    with ThreadPoolExecutor(max_workers=3) as ex:
        f_zonal = ex.submit(_zonal_hemisferio, lat_f, fetch, dias=dias)
        f_storm = ex.submit(_storm_tracks_local, lat_f, lon_f, fetch, dias=dias)
        f_jet = ex.submit(_jet_stream_u, lat_f, lon_f, fetch)
        zonal = f_zonal.result()
        storm = f_storm.result()
        jet = f_jet.result()

    out = dict(zonal)
    out['lat_usuario'] = round(lat_f, 3)
    out['lon_usuario'] = round(lon_f, 3)
    out['storm_tracks'] = storm
    out['jet'] = jet
    # ok global si al menos un bloque útil
    out['ok'] = bool(zonal.get('ok') or storm.get('ok') or jet.get('ok'))
    if not out['ok'] and not out.get('error'):
        out['error'] = 'Sin datos hemisféricos / storm tracks / jet'
    return out
