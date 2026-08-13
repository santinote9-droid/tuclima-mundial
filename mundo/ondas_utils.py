"""
Ondas / dinámica (eje UBA).

Naval: olas marinas (Hs, período, swell, steepness) + SRH (trombas) + QG.
Aéreo: dinámica atmosférica (shear, CAPE, Fr, SRH, régimen) + QG.

Diagnósticos cuasi-geostróficos (QG):
  - aguas someras 1 capa
  - aguas someras 2 capas
  - atmósfera estratificada continuamente
"""
from __future__ import annotations

import math
from typing import Any, Optional


_G = 9.81
_P0 = 1000.0  # hPa ref. potencial
_R_CP = 0.286  # R/cp aire seco
_OMEGA = 7.292115e-5  # rad/s
_L_SINOPTICO_M = 100_000.0  # escala horizontal de referencia (100 km)


def _f(v, default=0.0) -> float:
    try:
        if v is None:
            return float(default)
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _uv(speed: float, direction_deg: float) -> tuple[float, float]:
    """
    Componentes u (oeste→este), v (sur→norte) en m/s.
    Convención meteorológica: dirección = de dónde sopla.
    """
    rad = math.radians(direction_deg)
    u = -speed * math.sin(rad)
    v = -speed * math.cos(rad)
    return u, v


def _theta(t_c: float, p_hpa: float) -> float:
    """Temperatura potencial (K)."""
    tk = t_c + 273.15
    p = max(100.0, _f(p_hpa, 1000.0))
    return tk * ((_P0 / p) ** _R_CP)


def _kmh_to_ms(v: float) -> float:
    return _f(v) / 3.6


def _kt_to_ms(v: float) -> float:
    return _f(v) * 0.514444


def _coriolis(lat: float) -> float:
    """Parámetro de Coriolis f = 2 Ω sin φ (s⁻¹)."""
    return 2.0 * _OMEGA * math.sin(math.radians(_f(lat)))


def _fmt_sci(x: float, digits: int = 2) -> str:
    if x is None:
        return '—'
    ax = abs(x)
    if ax == 0:
        return '0'
    if 1e-3 <= ax < 1e4:
        return f'{x:.{digits}g}'
    return f'{x:.{digits}e}'


def diagnostico_qg(m: dict, *, modo: str = 'aereo') -> dict[str, Any]:
    """
    Diagnósticos del sistema cuasi-geostrófico a partir de datos locales.

    No resuelve las EDPs completas: estima números adimensionales y escalas
    (Ro, Rd, N, g', Bu) que indican si el régimen QG es válido y qué modelo
    (1 capa / 2 capas / estratificado) es más relevante.
    """
    lat = _f(m.get('lat'), -34.6)
    f = _coriolis(lat)
    f_abs = abs(f) if abs(f) > 1e-5 else 1e-4
    hemisferio = 'S' if lat < 0 else 'N'

    unit = (m.get('wind_unit') or 'kmh').lower()
    to_ms = _kt_to_ms if unit in ('kt', 'kn', 'knots') else _kmh_to_ms

    u_sfc = to_ms(m.get('wind_10', m.get('viento_kt', 0)))
    u_850 = to_ms(m.get('wind_850', m.get('viento_altura_kt', u_sfc)))
    u_700 = to_ms(m.get('wind_700', u_850))
    u_char = max(u_sfc, 0.5 * (u_850 + u_700), 0.5)

    # ─── Escala y validez QG (atmósfera / océano) ───
    L = _f(m.get('escala_L_m'), _L_SINOPTICO_M)
    ro = u_char / (f_abs * L)  # Rossby
    if ro < 0.1:
        qg_ok, qg_color, qg_label = True, '#4ade80', 'QG válido (Ro << 1)'
    elif ro < 0.3:
        qg_ok, qg_color, qg_label = True, '#fbbf24', 'QG marginal'
    else:
        qg_ok, qg_color, qg_label = False, '#fb923c', 'Fuera de QG (Ro grande)'

    # ─── 1) Aguas someras / capa barotrópica ───
    if modo == 'naval':
        hs = max(0.1, _f(m.get('hs') or m.get('ola_altura'), 1.0))
        # Profundidad equivalente: plataforma (~50 m) o Hs*factor si no hay batimetría
        H1 = _f(m.get('profundidad_m'), max(30.0, hs * 25.0))
        c_ext = math.sqrt(_G * H1)
        rd_bar = c_ext / f_abs  # radio deformación externo
        fr_sw = u_char / max(c_ext, 1e-6)
        # Vorticidad relativa proxy: shear horizontal ~ ΔU/L
        zeta_proxy = abs(u_850 - u_sfc) / L if L > 0 else 0.0
        pv_sw = (f + zeta_proxy) / H1  # PV aguas someras simplificada
        capa1 = {
            'titulo': 'QG aguas someras (1 capa)',
            'ecuacion': '∂q/∂t + J(ψ,q)=0 · q=(f+∇²ψ)/H',
            'H_m': round(H1, 0),
            'c_ms': round(c_ext, 1),
            'Rd_km': round(rd_bar / 1000.0, 0),
            'Fr_sw': round(fr_sw, 3),
            'PV': _fmt_sci(pv_sw, 2),
            'nota': f'Rd = √(gH)/|f| ≈ {rd_bar/1000:.0f} km. Ondas de Kelvin/Poincaré si L~Rd.',
            'color': '#38bdf8',
        }
    else:
        # Atmósfera barotrópica equivalente: H escala de tropopausa ~10 km
        H1 = _f(m.get('H_eq_m'), 10000.0)
        c_ext = math.sqrt(_G * H1)  # muy grande; mejor usar c = NH o Rd = NH/f abajo
        # Para 1 capa atmosférica usamos altura equivalente menor (barotrópica ~8–10 km
        # con g reducido conceptualmente → usamos Rd_ext = sqrt(g H)/f solo como ref.)
        rd_bar = c_ext / f_abs
        fr_sw = u_char / max(math.sqrt(_G * 1000.0), 1e-6)  # H_eq 1 km aire
        zeta_proxy = abs(u_700 - u_sfc) / L
        pv_sw = (f + zeta_proxy) / H1
        capa1 = {
            'titulo': 'QG capa barotrópica (equiv. 1 capa)',
            'ecuacion': 'Dq/Dt=0 · q=∇²ψ+f · (atm. barotrópica)',
            'H_m': round(H1, 0),
            'c_ms': round(math.sqrt(_G * 1000.0), 1),
            'Rd_km': round(rd_bar / 1000.0, 0),
            'Fr_sw': round(fr_sw, 3),
            'PV': _fmt_sci(pv_sw, 2),
            'nota': 'Modelo de una capa: filtrado de ondas de gravedad; equilibrio geostrófico a O(Ro).',
            'color': '#67e8f9',
        }

    # ─── 2) Dos capas (baroclínico) ───
    if modo == 'naval':
        # Capa mixta superficial vs profunda: Δρ/ρ desde T aire–agua
        t_air = _f(m.get('temp_aire') or m.get('temp_sfc'), 18)
        t_water = _f(m.get('temp_agua'), t_air * 0.85 + 2)
        # Expansión térmica aprox. agua: α≈2e-4 /K → Δρ/ρ ≈ α ΔT
        dT = abs(t_air - t_water)
        drho_rho = max(5e-4, min(0.01, 2.0e-4 * max(dT, 1.0) + 0.001))
        h1 = max(10.0, min(80.0, _f(m.get('hs'), 1) * 20 + 20))  # capa mixta proxy
        h2 = max(h1, _f(m.get('profundidad_m'), 80.0) - h1)
        g_prime = _G * drho_rho
        c_int = math.sqrt(g_prime * h1 * h2 / max(h1 + h2, 1.0))
        rd_int = c_int / f_abs
        capa2 = {
            'titulo': 'QG aguas someras 2 capas',
            'ecuacion': "g'=g Δρ/ρ · Rd_i=√(g'H_e)/|f| · modos BT/BC",
            'g_prime': round(g_prime, 4),
            'drho_pct': round(drho_rho * 100, 3),
            'h1_m': round(h1, 0),
            'h2_m': round(h2, 0),
            'c_int_ms': round(c_int, 2),
            'Rd_int_km': round(rd_int / 1000.0, 1),
            'nota': f"Gravedad reducida g'≈{g_prime:.4f} m/s². Modo baroclínico con Rd≈{rd_int/1000:.1f} km.",
            'color': '#22d3ee',
        }
    else:
        # Dos capas atmosféricas: troposfera baja (sfc–850) vs media (850–700)
        t_sfc = _f(m.get('temp_sfc'), 15)
        t850 = _f(m.get('temp_850'), t_sfc - 8)
        t700 = _f(m.get('temp_700'), t850 - 10)
        th1 = _theta(t_sfc, 1000.0)
        th2 = _theta(t850, 850.0)
        th3 = _theta(t700, 700.0)
        # Contraste potencial entre capas
        dth = max(0.3, abs(th3 - th1))
        th_avg = 0.5 * (th1 + th3)
        # g' ≈ g Δθ/θ
        g_prime = _G * (dth / th_avg)
        h1, h2 = 1500.0, 1500.0  # ~sfc-850 y 850-700
        c_int = math.sqrt(g_prime * h1 * h2 / (h1 + h2))
        rd_int = c_int / f_abs
        # Shear baroclínico (thermal wind proxy)
        du = abs(u_700 - u_sfc)
        capa2 = {
            'titulo': 'QG atmósfera 2 capas',
            'ecuacion': "g'=g Δθ/θ · ∂ug/∂z ∝ ∇T · modos barotrópico/baroclínico",
            'g_prime': round(g_prime, 4),
            'drho_pct': round((dth / th_avg) * 100, 2),
            'h1_m': round(h1, 0),
            'h2_m': round(h2, 0),
            'c_int_ms': round(c_int, 1),
            'Rd_int_km': round(rd_int / 1000.0, 0),
            'shear_ms': round(du, 1),
            'nota': f"Δθ≈{dth:.1f} K entre capas → Rd baroclínico ≈{rd_int/1000:.0f} km. Shear |U700−Us|≈{int(round(du))} m/s.",
            'color': '#a78bfa',
        }

    # ─── 3) Atmósfera estratificada continuamente ───
    t_low = _f(m.get('temp_850'), _f(m.get('temp_sfc'), 15) - 8)
    t_high = _f(m.get('temp_700'), t_low - 10)
    th_l = _theta(t_low, 850.0)
    th_h = _theta(t_high, 700.0)
    dz = 1500.0
    dth_dz = (th_h - th_l) / dz
    th_m = max(200.0, 0.5 * (th_l + th_h))
    if dth_dz > 1e-5:
        N = math.sqrt((_G / th_m) * dth_dz)
        N_label = 'Estratificación estable'
        N_color = '#4ade80'
    elif dth_dz > -1e-5:
        N = 1e-3
        N_label = 'Casi neutra'
        N_color = '#fbbf24'
    else:
        N = 0.0
        N_label = 'Inestable (N²<0)'
        N_color = '#ef4444'

    H_trop = _f(m.get('H_trop_m'), 10000.0)
    rd_cont = (N * H_trop / f_abs) if N > 0 else 0.0
    # Número de Burger Bu = (Rd/L)² — QG fuerte si Bu ~ O(1)
    bu = (rd_cont / L) ** 2 if L > 0 and rd_cont > 0 else 0.0
    # Frecuencia inercial
    f_cph = abs(f) * 3600 / (2 * math.pi)  # ciclos/hora approx

    if bu >= 0.3:
        bu_label, bu_color = 'QG estratificado OK', '#4ade80'
    elif bu >= 0.05:
        bu_label, bu_color = 'QG débil / mesoescala', '#fbbf24'
    else:
        bu_label, bu_color = 'Escala pequeña vs Rd', '#fb923c'

    estrat = {
        'titulo': 'QG atmósfera estratificada continua',
        'ecuacion': 'Dq/Dt=0 · q=∇²ψ+(f²/N²)∂²ψ/∂z²+βy',
        'N': round(N, 5),
        'N_label': N_label,
        'N_color': N_color,
        'Rd_km': round(rd_cont / 1000.0, 0),
        'Bu': round(bu, 3),
        'Bu_label': bu_label,
        'Bu_color': bu_color,
        'H_m': int(H_trop),
        'nota': f'N≈{_fmt_sci(N)} s⁻¹ · Rd=NH/|f|≈{rd_cont/1000:.0f} km · Burger Bu=(Rd/L)²≈{bu:.2f}.',
        'color': '#c4b5fd',
    }

    # Resumen operativo
    if modo == 'naval':
        modelo_sugerido = '2 capas (baroclínico costero)' if capa2['Rd_int_km'] < 80 else '1 capa (aguas someras)'
    else:
        if N > 0.01 and bu >= 0.2:
            modelo_sugerido = 'Estratificado continuo (QG 3D)'
        elif capa2.get('Rd_int_km', 0) > 0:
            modelo_sugerido = '2 capas atmosféricas'
        else:
            modelo_sugerido = 'Capa barotrópica'

    return {
        'ok': True,
        'lat': round(lat, 3),
        'hemisferio': hemisferio,
        'f': f,
        'f_sci': _fmt_sci(f, 3),
        'Ro': round(ro, 3),
        'Ro_label': qg_label,
        'Ro_color': qg_color,
        'qg_valido': qg_ok,
        'L_km': round(L / 1000.0, 0),
        'U_ms': int(round(u_char)),
        'modelo_sugerido': modelo_sugerido,
        'capa1': capa1,
        'capa2': capa2,
        'estratificada': estrat,
        'nota_general': (
            'Ecuaciones filtradas: equilibrio geostrófico a orden dominante, '
            'ondas de gravedad rapidas eliminadas. Ro=U/(|f|L); si Ro << 1 el sistema QG aplica.'
        ),
    }


def numero_froude(
    *,
    wind_ms: float,
    t_low_c: float,
    t_high_c: float,
    p_low_hpa: float = 850.0,
    p_high_hpa: float = 700.0,
    z_low_m: float = 1500.0,
    z_high_m: float = 3000.0,
    elev_m: float = 0.0,
    h_barrera_m: Optional[float] = None,
) -> dict[str, Any]:
    """
    Fr = U / (N · H)  — número de Froude de capa (ondas de montaña).

    N ~ sqrt((g/theta)*dtheta/dz)  (Brunt-Vaisala)
    H ~ elevacion del punto (o H de referencia si terreno bajo)
    U ~ viento de niveles medios (m/s)
    """
    u = max(0.0, _f(wind_ms))
    th_l = _theta(t_low_c, p_low_hpa)
    th_h = _theta(t_high_c, p_high_hpa)
    dz = max(100.0, z_high_m - z_low_m)
    dth = th_h - th_l
    th_avg = max(200.0, 0.5 * (th_l + th_h))

    if dth <= 0.05:
        # Capa neutra/inestable: N→0 ⇒ Fr grande (sin ondas atrapadas clásicas)
        n = 0.0
        fr = 99.0 if u > 0.5 else 0.0
        label, color = 'Capa neutra / Fr alto', '#94a3b8'
        detalle = 'Estratificación débil o inestable — ondas de montaña clásicas poco probables'
    else:
        n = math.sqrt((_G / th_avg) * (dth / dz))
        elev = max(0.0, _f(elev_m))
        if h_barrera_m is not None:
            h = max(200.0, _f(h_barrera_m))
            h_fuente = 'H configurada'
        elif elev >= 250:
            h = min(2500.0, max(300.0, elev))
            h_fuente = f'elevación ~{int(elev)} m'
        else:
            h = 800.0
            h_fuente = 'H ref. 800 m (terreno bajo)'
        fr = u / max(n * h, 1e-6)

        if 0.6 <= fr <= 1.4:
            label, color = 'Ondas / rotores', '#ef4444'
            detalle = 'Fr ~ 1: régimen favorable a ondas de montaña severas y rotores'
        elif 0.4 <= fr < 0.6 or 1.4 < fr <= 2.0:
            label, color = 'Ondas posibles', '#fbbf24'
            detalle = 'Fr cercano a 1 — monitorear turbulencia orográfica'
        elif fr < 0.4:
            label, color = 'Flujo bloqueado', '#60a5fa'
            detalle = 'Fr bajo: flujo bloqueado por la orografía; ondas atrapadas limitadas'
        else:
            label, color = 'Flujo supercrítico', '#4ade80'
            detalle = 'Fr alto: flujo pasa la barrera; ondas de montaña menos resonantes'

    return {
        'fr': round(min(fr, 99.0), 2),
        'n': round(n, 5),
        'u_ms': round(u, 1),
        'h_m': int(h) if dth > 0.05 else None,
        'h_fuente': h_fuente if dth > 0.05 else '—',
        'label': label,
        'color': color,
        'detalle': detalle,
        'alerta': 0.6 <= fr <= 1.4 if dth > 0.05 else False,
    }


def helicidad_srh(
    niveles: list[dict[str, Any]],
    *,
    storm_from_bunkers: bool = True,
) -> dict[str, Any]:
    """
    SRH 0–~3 km (m²/s²) con niveles discretos.

    Cada nivel: {z_m, speed_ms, dir_deg}
    Ordenados por altura creciente.
    """
    pts = []
    for lv in niveles or []:
        z = _f(lv.get('z_m'))
        spd = _f(lv.get('speed_ms'))
        d = _f(lv.get('dir_deg'))
        if z < 0:
            continue
        u, v = _uv(spd, d)
        pts.append((z, u, v))
    pts.sort(key=lambda t: t[0])
    if len(pts) < 2:
        return {
            'srh': None, 'label': 'N/D', 'color': '#94a3b8',
            'detalle': 'Sin perfil de viento para SRH', 'alerta': False,
        }

    # Movimiento de tormenta: media de la capa (proxy Bunkers simple)
    um = _mean([p[1] for p in pts])
    vm = _mean([p[2] for p in pts])
    if storm_from_bunkers:
        # 75% del viento medio de la capa + desviación a la derecha ~7.5 m/s
        cx = 0.75 * um + 7.5 * 0.0  # simplificado: 75% mean wind
        cy = 0.75 * vm
        # Desviación perpendicular a la derecha del mean wind
        mag = math.hypot(um, vm)
        if mag > 0.5:
            rx, ry = -vm / mag, um / mag  # unit right-normal
            cx = 0.75 * um + 7.5 * rx
            cy = 0.75 * vm + 7.5 * ry
    else:
        cx, cy = um, vm

    srh = 0.0
    for i in range(len(pts) - 1):
        _, u0, v0 = pts[i]
        _, u1, v1 = pts[i + 1]
        srh += (u0 - cx) * (v1 - v0) - (v0 - cy) * (u1 - u0)

    srh = round(srh, 0)
    aa = abs(srh)
    if aa >= 300:
        label, color = 'Rotación alta', '#ef4444'
        detalle = 'SRH ≥ 300 m²/s² — potencial supercelular / tromba elevado'
        alerta = True
    elif aa >= 150:
        label, color = 'Rotación moderada', '#fb923c'
        detalle = 'SRH 150–300 — posible organización rotatoria (monitorear)'
        alerta = True
    elif aa >= 100:
        label, color = 'Rotación leve', '#fbbf24'
        detalle = 'SRH 100–150 — cizalladura helicoidal elevada'
        alerta = False
    else:
        label, color = 'Baja helicidad', '#4ade80'
        detalle = 'SRH < 100 — bajo potencial de rotación significativa'
        alerta = False

    return {
        'srh': int(srh),
        'label': label,
        'color': color,
        'detalle': detalle,
        'alerta': alerta,
        'storm_u': round(cx, 1),
        'storm_v': round(cy, 1),
    }


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def resumen_ondas_naval(m: dict) -> dict[str, Any]:
    """
    m: hs, periodo, swell_h, swell_periodo, swell_dir,
       serie_hs (list opcional), umbral_hs (default 1.5),
       + opcional perfil para SRH (niveles o vientos en km/h)
    """
    hs = _f(m.get('hs') or m.get('ola_altura'))
    periodo = _f(m.get('periodo') or m.get('ola_periodo'))
    swell_h = _f(m.get('swell_h') or m.get('swell_altura'))
    swell_t = _f(m.get('swell_periodo'))
    swell_dir = _f(m.get('swell_dir'))
    umbral = _f(m.get('umbral_hs'), 1.5)
    serie = m.get('serie_hs') or []

    ratio = swell_h / max(hs, 0.05)
    if ratio >= 0.7 and swell_h >= 0.3:
        tipo, tipo_color = 'Swell dominante', '#38bdf8'
    elif ratio <= 0.35:
        tipo, tipo_color = 'Mar de viento', '#fbbf24'
    else:
        tipo, tipo_color = 'Mixto', '#a78bfa'

    steepness = None
    steep_label = 'N/D'
    steep_color = '#94a3b8'
    if periodo > 0.5:
        L = 9.81 * (periodo ** 2) / (2 * math.pi)
        steepness = round(hs / max(L, 0.01), 4)
        if steepness >= 0.04:
            steep_label, steep_color = 'Empinado (riesgo)', '#ef4444'
        elif steepness >= 0.025:
            steep_label, steep_color = 'Moderado', '#fbbf24'
        else:
            steep_label, steep_color = 'Suave', '#4ade80'

    horas_riesgo = 0
    for v in serie:
        if _f(v) >= umbral:
            horas_riesgo += 1

    srh_info = m.get('srh') or _srh_desde_perfil(m)
    try:
        qg = diagnostico_qg(m, modo='naval')
    except Exception:
        qg = {'ok': False}

    return {
        'modo': 'naval',
        'hs': round(hs, 2),
        'periodo': round(periodo, 1),
        'swell_h': round(swell_h, 2),
        'swell_periodo': round(swell_t, 1),
        'swell_dir': round(swell_dir, 0),
        'ratio_swell': round(ratio, 2),
        'tipo': tipo,
        'tipo_color': tipo_color,
        'steepness': steepness,
        'steep_label': steep_label,
        'steep_color': steep_color,
        'horas_riesgo': horas_riesgo,
        'umbral_hs': umbral,
        'srh': srh_info.get('srh'),
        'srh_label': srh_info.get('label'),
        'srh_color': srh_info.get('color'),
        'srh_detalle': srh_info.get('detalle'),
        'srh_alerta': srh_info.get('alerta', False),
        'qg': qg,
    }


def _srh_desde_perfil(m: dict) -> dict[str, Any]:
    if m.get('niveles_viento'):
        return helicidad_srh(m['niveles_viento'])
    # Construir desde campos planos (km/h por defecto Open-Meteo)
    unit = (m.get('wind_unit') or 'kmh').lower()
    to_ms = _kt_to_ms if unit in ('kt', 'kn', 'knots') else _kmh_to_ms
    niveles = []
    mapping = [
        (10, 'wind_10', 'dir_10'),
        (500, 'wind_950', 'dir_950'),
        (1500, 'wind_850', 'dir_850'),
        (3000, 'wind_700', 'dir_700'),
    ]
    for z, sk, dk in mapping:
        if m.get(sk) is None and m.get(dk) is None:
            continue
        niveles.append({
            'z_m': z,
            'speed_ms': to_ms(m.get(sk, 0)),
            'dir_deg': m.get(dk, 0),
        })
    if len(niveles) < 2:
        return {
            'srh': None, 'label': 'N/D', 'color': '#94a3b8',
            'detalle': 'Sin perfil de viento', 'alerta': False,
        }
    return helicidad_srh(niveles)


def resumen_ondas_aereo(m: dict) -> dict[str, Any]:
    """
    m: viento_kt (o wind_10 km/h), rafagas, shear, cape, li, viento_altura,
       temps/dirs pressure levels, elevacion_m, wind_unit
    """
    unit = (m.get('wind_unit') or 'kmh').lower()
    to_ms = _kt_to_ms if unit in ('kt', 'kn', 'knots') else _kmh_to_ms

    # Compat: si viene viento_kt desde views (en realidad a menudo km/h)
    viento_disp = _f(m.get('viento_kt') if m.get('viento_kt') is not None else m.get('wind_10'))
    rafagas = _f(m.get('rafagas_kt') if m.get('rafagas_kt') is not None else m.get('gusts'))
    shear = _f(m.get('shear_kt'))
    if shear <= 0 and rafagas > viento_disp:
        shear = rafagas - viento_disp
    cape = _f(m.get('cape'))
    li = _f(m.get('li'), 0)
    v_alt = _f(m.get('viento_altura_kt') if m.get('viento_altura_kt') is not None else m.get('wind_850'))
    shear_vert = abs(v_alt - viento_disp) if v_alt else 0.0

    # Froude: U ~ viento 700 hPa (o 850), N desde θ 850–700
    w700 = m.get('wind_700')
    if w700 is None:
        w700 = v_alt
    t850 = _f(m.get('temp_850'), _f(m.get('temp_sfc'), 15) - 8)
    t700 = _f(m.get('temp_700'), t850 - 10)
    elev = _f(m.get('elevacion_m') or m.get('elevation'), 0)

    fr_info = numero_froude(
        wind_ms=to_ms(w700),
        t_low_c=t850,
        t_high_c=t700,
        elev_m=elev,
    )

    srh_info = _srh_desde_perfil({
        **m,
        'wind_unit': unit,
        'wind_10': m.get('wind_10', viento_disp),
        'dir_10': m.get('dir_10', m.get('wind_dir_10', 0)),
        'wind_950': m.get('wind_950'),
        'dir_950': m.get('dir_950'),
        'wind_850': m.get('wind_850', v_alt),
        'dir_850': m.get('dir_850'),
        'wind_700': m.get('wind_700', w700),
        'dir_700': m.get('dir_700'),
    })

    # Régimen dinámico (prioriza Fr ~ 1 y SRH alta)
    if fr_info.get('alerta'):
        regimen, reg_color = 'Onda de montaña', '#ef4444'
        detalle = fr_info['detalle']
    elif srh_info.get('alerta') and cape >= 500:
        regimen, reg_color = 'Rotación / supercelda', '#ef4444'
        detalle = srh_info['detalle'] + f' · CAPE {int(cape)} J/kg'
    elif cape >= 1000 or li <= -4:
        regimen, reg_color = 'Convectivo', '#ef4444'
        detalle = 'CAPE/LI sugieren convección; posible turbulencia convectiva'
    elif shear >= 15 or shear_vert >= 20:
        regimen, reg_color = 'Onda / shear', '#fbbf24'
        detalle = 'Cizalladura marcada — posible onda de gravedad / wind shear'
    elif cape < 300 and shear < 8:
        regimen, reg_color = 'Estable', '#4ade80'
        detalle = 'Baja inestabilidad y shear moderado'
    else:
        regimen, reg_color = 'Transicional', '#a78bfa'
        detalle = 'Condiciones mixtas — monitorear evolución'

    try:
        qg = diagnostico_qg(m, modo='aereo')
    except Exception:
        qg = {'ok': False}

    return {
        'modo': 'aereo',
        'viento_kt': int(round(viento_disp)),
        'rafagas_kt': int(round(rafagas)),
        'shear_kt': int(round(shear)),
        'shear_vertical_kt': int(round(shear_vert)),
        'viento_altura_kt': int(round(v_alt)),
        'cape': int(round(cape)),
        'li': round(li, 1),
        'regimen': regimen,
        'regimen_color': reg_color,
        'detalle': detalle,
        # Froude
        'fr': fr_info.get('fr'),
        'fr_label': fr_info.get('label'),
        'fr_color': fr_info.get('color'),
        'fr_detalle': fr_info.get('detalle'),
        'fr_alerta': fr_info.get('alerta', False),
        'fr_n': fr_info.get('n'),
        'fr_h_m': fr_info.get('h_m'),
        'fr_h_fuente': fr_info.get('h_fuente'),
        # SRH
        'srh': srh_info.get('srh'),
        'srh_label': srh_info.get('label'),
        'srh_color': srh_info.get('color'),
        'srh_detalle': srh_info.get('detalle'),
        'srh_alerta': srh_info.get('alerta', False),
        'qg': qg,
    }
