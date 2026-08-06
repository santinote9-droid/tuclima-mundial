"""
Semáforo operativo por sector: ¿puedo operar hoy?

Unifica umbrales ya usados en las vistas agro/naval/aereo/energia
en un dict estándar para UI (badge) y APIs.
"""

NIVELES = {
    'go': {'nivel': 'go', 'label': 'OPERABLE', 'color': '#22c55e', 'emoji': '🟢'},
    'caution': {'nivel': 'caution', 'label': 'PRECAUCIÓN', 'color': '#fbbf24', 'emoji': '🟡'},
    'stop': {'nivel': 'stop', 'label': 'NO OPERAR', 'color': '#ef4444', 'emoji': '🔴'},
    'unknown': {'nivel': 'unknown', 'label': 'SIN DATOS', 'color': '#94a3b8', 'emoji': '⚪'},
}


def _pack(nivel_key, motivos, resumen):
    base = dict(NIVELES.get(nivel_key, NIVELES['unknown']))
    base['motivos'] = motivos or []
    base['resumen'] = resumen
    return base


def evaluar_operabilidad(sector, m):
    """
    sector: agro|naval|aereo|energia
    m: dict de métricas numéricas ya calculadas en la vista
    """
    sector = (sector or '').lower().strip()
    if not m:
        return _pack('unknown', [], 'Sin métricas disponibles')

    if sector == 'agro':
        return _agro(m)
    if sector == 'naval':
        return _naval(m)
    if sector == 'aereo':
        return _aereo(m)
    if sector == 'energia':
        return _energia(m)
    return _pack('unknown', [], f'Sector desconocido: {sector}')


def _agro(m):
    delta_t = float(m.get('delta_t') or 0)
    viento = float(m.get('viento_kmh') or 0)
    vpd = float(m.get('vpd') or 0)
    balance = float(m.get('balance_neto') or 0)
    motivos = []

    if delta_t > 10 or viento > 20:
        if delta_t > 10:
            motivos.append(f'Delta T crítico ({delta_t:.1f}°C)')
        if viento > 20:
            motivos.append(f'Vento fuerte ({viento:.1f} km/h) — deriva')
        return _pack('stop', motivos, 'Pulverización no recomendada')

    if delta_t > 8 or vpd > 1.6 or viento > 15:
        if delta_t > 8:
            motivos.append(f'Delta T elevado ({delta_t:.1f}°C)')
        if vpd > 1.6:
            motivos.append(f'VPD alto ({vpd:.2f} kPa)')
        if viento > 15:
            motivos.append(f'Vento marginal ({viento:.1f} km/h)')
        return _pack('caution', motivos, 'Condiciones marginales — evaluar labores')

    if balance < -30:
        motivos.append(f'Déficit hídrico ({balance:.0f} mm)')
        return _pack('caution', motivos, 'Operable con vigilancia hídrica')

    motivos.append('Delta T, viento y VPD dentro de rango')
    return _pack('go', motivos, 'Ventana operativa favorable')


def _naval(m):
    olas = float(m.get('olas_m') or 0)
    viento_kt = float(m.get('viento_kt') or 0)
    vis_nm = float(m.get('vis_nm') or 99)
    motivos = []

    if olas >= 2.5 or viento_kt >= 25 or vis_nm < 0.5:
        if olas >= 2.5:
            motivos.append(f'Oleaje alto ({olas:.1f} m)')
        if viento_kt >= 25:
            motivos.append(f'Vento fuerte ({viento_kt:.0f} kt)')
        if vis_nm < 0.5:
            motivos.append(f'Visibilidad nula ({vis_nm:.1f} NM)')
        return _pack('stop', motivos, 'No salir a navegar')

    if olas >= 1.5 or viento_kt >= 15 or vis_nm < 2:
        if olas >= 1.5:
            motivos.append(f'Mar picado ({olas:.1f} m)')
        if viento_kt >= 15:
            motivos.append(f'Vento moderado ({viento_kt:.0f} kt)')
        if vis_nm < 2:
            motivos.append(f'Visibilidad reducida ({vis_nm:.1f} NM)')
        return _pack('caution', motivos, 'Precaución — evaluar cada salida')

    motivos.append('Oleaje, viento y visibilidad OK')
    return _pack('go', motivos, 'Condiciones operativas favorables')


def _aereo(m):
    cat = str(m.get('categoria') or 'VFR').upper()
    cape = float(m.get('cape') or 0)
    shear = float(m.get('shear_kt') or 0)
    vis_km = float(m.get('vis_km') or 10)
    motivos = []

    if cat in ('IFR', 'LIFR') or cape > 1500:
        if cat in ('IFR', 'LIFR'):
            motivos.append(f'Categoría {cat}')
        if cape > 1500:
            motivos.append(f'CAPE alto ({cape:.0f} J/kg)')
        return _pack('stop', motivos, 'Vuelo VFR no recomendado')

    if cat == 'MVFR' or shear > 15 or vis_km < 5:
        if cat == 'MVFR':
            motivos.append('MVFR activo')
        if shear > 15:
            motivos.append(f'Wind shear ({shear:.0f} kt)')
        if vis_km < 5:
            motivos.append(f'Visibilidad {vis_km:.1f} km')
        return _pack('caution', motivos, 'Condiciones subóptimas — verificar METAR')

    motivos.append(f'{cat} · visibilidad {vis_km:.1f} km')
    return _pack('go', motivos, 'Ventana VFR favorable')


def _energia(m):
    temp = float(m.get('temp_c') or 20)
    wind_ms = float(m.get('viento_ms') or 0)
    rad = float(m.get('radiacion') or 0)
    motivos = []

    # Stop solo en extremos peligrosos para equipos
    if wind_ms > 20 or temp > 45:
        if wind_ms > 20:
            motivos.append(f'Vento extremo ({wind_ms:.1f} m/s)')
        if temp > 45:
            motivos.append(f'Temperatura crítica ({temp:.0f}°C)')
        return _pack('stop', motivos, 'Riesgo para equipos — revisar protocolo')

    if wind_ms > 12 or temp > 38 or (rad < 50 and wind_ms < 3):
        if wind_ms > 12:
            motivos.append(f'Vento fuerte ({wind_ms:.1f} m/s)')
        if temp > 38:
            motivos.append(f'Calor reduce eficiencia solar ({temp:.0f}°C)')
        if rad < 50 and wind_ms < 3:
            motivos.append(f'Baja generación (rad {rad:.0f} W/m²)')
        return _pack('caution', motivos, 'Generación limitada o con precaución')

    motivos.append(f'Rad {rad:.0f} W/m² · viento {wind_ms:.1f} m/s')
    return _pack('go', motivos, 'Condiciones de generación favorables')
