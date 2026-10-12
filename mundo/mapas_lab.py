"""
Grilla gruesa armada con puntos sueltos de la API pública de Open-Meteo.

Respaldo de `grilla_modelo`, que lee la grilla nativa del modelo (0,125°) pero
solo para la región que sincronizamos. Fuera de esa ventana caemos acá: mucho
menos detalle (~1,5°) pero cobertura mundial.

La grilla se cuantiza a una celda fija antes de pedir datos: así los
desplazamientos chicos del mapa reutilizan la misma respuesta cacheada en vez
de disparar una llamada nueva a Open-Meteo.
"""
from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor

from django.core.cache import caches

CAPAS = {
    'temp': {'om': 'temperature_2m', 'unidad': '°C', 'nombre': 'Temperatura'},
    'lluvia': {'om': 'precipitation', 'unidad': 'mm', 'nombre': 'Lluvia'},
    'presion': {'om': 'pressure_msl', 'unidad': 'hPa', 'nombre': 'Presión'},
    'viento': {'om': 'wind_speed_10m', 'unidad': 'km/h', 'nombre': 'Viento'},
}

HOURLY = ','.join(c['om'] for c in CAPAS.values())
FORECAST_DAYS = 2
CACHE_TTL = 900
MAX_AXIS = 40
NICE_STEPS = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 10.0, 12.0, 15.0, 20.0)
DEFAULT_HALF = 6.0
CHUNK_TARGET = 80
MAX_CHUNKS = 10


def _cache():
    try:
        return caches['mapas']
    except Exception:
        return caches['default']


def _clamp_lat(lat: float) -> float:
    return max(-90.0, min(90.0, float(lat)))


def _limit_lon(lon: float) -> float:
    return max(-180.0, min(180.0, float(lon)))


def _wrap_lon(lon: float) -> float:
    return ((float(lon) + 180.0) % 360.0) - 180.0


def _snap(v: float, step: float) -> float:
    return round(round(v / step) * step, 3)


def _parse_bounds(south, north, west, east) -> tuple[float, float, float, float]:
    south, north = _clamp_lat(south), _clamp_lat(north)
    if south > north:
        south, north = north, south
    if north - south < 0.5:
        mid = (south + north) / 2.0
        south, north = _clamp_lat(mid - 0.25), _clamp_lat(mid + 0.25)

    west, east = _limit_lon(west), _limit_lon(east)
    if west > east:
        west, east = east, west
    if east - west < 0.5:
        mid = (west + east) / 2.0
        west, east = _limit_lon(mid - 0.25), _limit_lon(mid + 0.25)
    return south, north, west, east


def plan_grid(south: float, north: float, west: float, east: float):
    """Ejes de la grilla. Siempre cubre el recuadro pedido: si no entra
    a 1,5°, se agranda el paso (antes, el mundo se cortaba en el Atlántico)."""
    south, north, west, east = _parse_bounds(south, north, west, east)
    span0_lat = north - south
    span0_lon = east - west
    if span0_lat < 160:
        pad_lat = max(0.3, span0_lat * 0.15)
        south, north = _clamp_lat(south - pad_lat), _clamp_lat(north + pad_lat)
    if span0_lon < 330:
        pad_lon = max(0.3, span0_lon * 0.15)
        west, east = _limit_lon(west - pad_lon), _limit_lon(east + pad_lon)

    span_lat = max(0.5, north - south)
    span_lon = max(0.5, east - west)
    step_needed = max(span_lat / (MAX_AXIS - 1), span_lon / (MAX_AXIS - 1))
    step = NICE_STEPS[-1]
    for nice in NICE_STEPS:
        if nice >= step_needed - 1e-9:
            step = nice
            break
    else:
        step = math.ceil(step_needed * 2.0) / 2.0

    n_lat = min(MAX_AXIS, max(2, int(math.floor(span_lat / step)) + 1))
    n_lon = min(MAX_AXIS, max(2, int(math.floor(span_lon / step)) + 1))
    step_lat = span_lat / (n_lat - 1)
    step_lon = span_lon / (n_lon - 1)
    lats = [round(_clamp_lat(south + i * step_lat), 3) for i in range(n_lat)]
    lons = [round(_limit_lon(west + j * step_lon), 3) for j in range(n_lon)]
    lats[-1], lons[-1] = round(north, 3), round(east, 3)
    return lats, lons, step_lat, step_lon


def _as_list(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return [payload]
    return []


def _url(lats, lons) -> str:
    return (
        'https://api.open-meteo.com/v1/forecast'
        f'?latitude={",".join(str(x) for x in lats)}'
        f'&longitude={",".join(str(x) for x in lons)}'
        f'&hourly={HOURLY}'
        f'&forecast_days={FORECAST_DAYS}'
        '&models=icon_seamless'
        '&wind_speed_unit=kmh'
        '&timezone=UTC'
    )


def _fetch_bloques(req_lats, req_lons) -> list:
    """Pide la grilla en tandas paralelas; Open-Meteo responde en orden."""
    from .views import _get_meteo

    total = len(req_lats)
    n_partes = max(1, min(MAX_CHUNKS, math.ceil(total / CHUNK_TARGET)))
    size = math.ceil(total / n_partes)
    partes = [
        (req_lats[i:i + size], req_lons[i:i + size])
        for i in range(0, total, size)
    ]

    def pedir(parte):
        return _get_meteo(_url(*parte), timeout=25, reintentos=1)

    if len(partes) == 1:
        crudos = [pedir(partes[0])]
    else:
        with ThreadPoolExecutor(max_workers=len(partes)) as ex:
            crudos = list(ex.map(pedir, partes))

    bloques = []
    for raw in crudos:
        if isinstance(raw, dict) and raw.get('error'):
            raise ValueError(raw.get('reason') or 'Open-Meteo error')
        bloques.extend(_as_list(raw))
    return bloques


def fetch_grilla(lat: float, lon: float, bounds=None) -> dict:
    lat, lon = _clamp_lat(lat), _wrap_lon(lon)
    if bounds:
        south, north, west, east = bounds
    else:
        south, north = lat - DEFAULT_HALF, lat + DEFAULT_HALF
        west, east = lon - DEFAULT_HALF, lon + DEFAULT_HALF

    lats, lons, step_lat, step_lon = plan_grid(south, north, west, east)
    step = max(step_lat, step_lon)
    cache_key = (
        f'mapas_lab:v5:{lats[0]}:{lats[-1]}:{lons[0]}:{lons[-1]}'
        f':{round(step_lat, 4)}:{round(step_lon, 4)}'
    )
    cache = _cache()
    cached = cache.get(cache_key)
    if cached:
        return cached

    req_lats, req_lons = [], []
    for la in lats:
        for lo in lons:
            req_lats.append(la)
            req_lons.append(lo)

    bloques = _fetch_bloques(req_lats, req_lons)
    if not bloques:
        raise ValueError('Open-Meteo no devolvió puntos')
    if len(bloques) != len(req_lats):
        raise ValueError('Open-Meteo devolvió una grilla incompleta')

    times = [
        t if t.endswith('Z') else f'{t}Z'
        for t in ((bloques[0].get('hourly') or {}).get('time') or [])
    ]
    n_horas = len(times)

    # series[capa][i] = serie horaria de la celda i, en orden fila-mayor
    # (lat externo, lon interno). Evita repetir lat/lon/claves por punto.
    series = {k: [] for k in CAPAS}
    for bloque in bloques:
        hourly = bloque.get('hourly') or {}
        for key, meta in CAPAS.items():
            serie = hourly.get(meta['om']) or []
            fila = [
                None if v is None else round(float(v), 1)
                for v in serie[:n_horas]
            ]
            if len(fila) < n_horas:
                fila.extend([None] * (n_horas - len(fila)))
            series[key].append(fila)

    payload = {
        'ok': True,
        'centro': {'lat': _snap(lat, step), 'lon': _snap(lon, step)},
        'grid': {'lats': lats, 'lons': lons, 'step': step,
                 'step_lat': step_lat, 'step_lon': step_lon},
        'times': times,
        'series': series,
        'capas': {
            k: {'unidad': v['unidad'], 'nombre': v['nombre']}
            for k, v in CAPAS.items()
        },
        'fuente': 'Open-Meteo',
        'cache_s': CACHE_TTL,
    }
    cache.set(cache_key, payload, CACHE_TTL)
    return payload


def recortar_puntos(capa: str, hora: int, sur: float, norte: float,
                    oeste: float, este: float) -> dict:
    """Payload con la misma forma que `grilla_modelo.recortar`.

    Permite que el mapa use un solo formato: si el viewport sale de la región
    del modelo, cambia la fuente y no el código del navegador.
    """
    meta = CAPAS.get(capa)
    if meta is None:
        raise ValueError(f'capa desconocida: {capa}')

    data = fetch_grilla((sur + norte) / 2.0, (oeste + este) / 2.0,
                        bounds=(sur, norte, oeste, este))
    lats = data['grid']['lats']
    lons = data['grid']['lons']
    times = data['times']
    hora = max(0, min(int(hora), max(0, len(times) - 1)))
    serie = data['series'][capa]

    filas, cols = len(lats), len(lons)
    from .grilla_modelo import HORAS_POR_BLOQUE
    desde = (hora // HORAS_POR_BLOQUE) * HORAS_POR_BLOQUE
    hasta = min(len(times), desde + HORAS_POR_BLOQUE)

    valores = []
    for h in range(desde, hasta):
        plano = []
        # De norte a sur, que es el orden de las filas de una imagen.
        for i in range(filas - 1, -1, -1):
            base = i * cols
            for j in range(cols):
                plano.append(serie[base + j][h])
        valores.append(plano)

    finitos = [v for plano in valores for v in plano if v is not None]
    grid = data['grid']
    paso_lat = grid.get('step_lat', grid['step'])
    paso_lon = grid.get('step_lon', grid['step'])
    return {
        'ok': True,
        'capa': capa,
        'nombre': meta['nombre'],
        'unidad': meta['unidad'],
        'decimales': 1 if capa in ('temp', 'lluvia') else 0,
        'modelo': 'open-meteo-mix',
        'fuente': 'Open-Meteo API (mezcla de modelos, grilla gruesa)',
        'reference_time': None,
        'times': times,
        'hora': hora,
        'hora_desde': desde,
        'horas_en_bloque': hasta - desde,
        'filas': filas,
        'cols': cols,
        'bbox': [lons[0], lats[0], lons[-1], lats[-1]],
        'paso_lat': round(paso_lat, 5),
        'paso_lon': round(paso_lon, 5),
        'res_km': round(paso_lat * 111.32, 1),
        'min': min(finitos) if finitos else None,
        'max': max(finitos) if finitos else None,
        'valores': valores,
        'cache_s': CACHE_TTL,
    }
