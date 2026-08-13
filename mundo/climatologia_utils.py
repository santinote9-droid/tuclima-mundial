"""
Climatología / anomalías (eje UBA) vía Open-Meteo Archive + ENSO (NOAA/CPC ONI).

Incluye:
  - anomalías corto plazo (panel base)
  - fase ENSO (ONI)
  - climograma año actual vs media ~30 años
  - SPI / SPEI a 3 y 6 meses
"""
from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Callable, Optional

from django.core.cache import cache as django_cache


FetchJson = Callable[[str], Any]
FetchText = Callable[[str], str]

_MES_ES = ['', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
_ONI_URL = 'https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt'


def _f(v, default=0.0) -> float:
    try:
        if v is None:
            return float(default)
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    return var ** 0.5


def _percentile(xs: list[float], p: float) -> Optional[float]:
    if not xs:
        return None
    s = sorted(xs)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


# Variable primaria por sector para el panel
_SECTOR_CFG = {
    'agro': {
        'daily': 'temperature_2m_mean,precipitation_sum',
        'primary': 'temperature_2m_mean',
        'primary_label': 'Temp. media',
        'unidad': '°C',
        'secondary': 'precipitation_sum',
        'secondary_label': 'Precipitación',
        'secondary_unidad': 'mm',
        'marine': False,
        'spei': True,
    },
    'energia': {
        'daily': 'shortwave_radiation_sum,temperature_2m_mean,wind_speed_10m_max',
        'primary': 'shortwave_radiation_sum',
        'primary_label': 'Radiación diaria',
        'unidad': 'MJ/m²',
        'secondary': 'wind_speed_10m_max',
        'secondary_label': 'Viento máx',
        'secondary_unidad': 'km/h',
        'marine': False,
        'spei': False,
    },
    'naval': {
        'daily': 'wind_speed_10m_max,temperature_2m_mean',
        'primary': 'wind_speed_10m_max',
        'primary_label': 'Viento máx',
        'unidad': 'km/h',
        'secondary': 'temperature_2m_mean',
        'secondary_label': 'Temp. media',
        'secondary_unidad': '°C',
        'marine': False,
        'spei': False,
        'nota': 'Proxy atmosférico (viento); oleaje histórico marine archive no siempre disponible.',
    },
    'aereo': {
        'daily': 'wind_speed_10m_max,temperature_2m_mean',
        'primary': 'wind_speed_10m_max',
        'primary_label': 'Viento máx',
        'unidad': 'km/h',
        'secondary': 'temperature_2m_mean',
        'secondary_label': 'Temp. media',
        'secondary_unidad': '°C',
        'marine': False,
        'spei': False,
    },
}


def _etiqueta_z(z: Optional[float], primary_key: str) -> tuple[str, str]:
    if z is None:
        return 'Sin datos', '#94a3b8'
    az = abs(z)
    if az < 1.0:
        return 'Normal', '#4ade80'
    if az < 2.0:
        if 'temp' in primary_key:
            return ('Anómalo cálido' if z > 0 else 'Anómalo frío'), '#fbbf24'
        if 'precip' in primary_key or 'rain' in primary_key:
            return ('Anómalo húmedo' if z > 0 else 'Anómalo seco'), '#fbbf24'
        if 'wind' in primary_key:
            return ('Anómalo ventoso' if z > 0 else 'Anómalo calmo'), '#fbbf24'
        if 'shortwave' in primary_key or 'rad' in primary_key:
            return ('Anómalo soleado' if z > 0 else 'Anómalo nublado'), '#fbbf24'
        return ('Anómalo alto' if z > 0 else 'Anómalo bajo'), '#fbbf24'
    return ('Extremo alto' if z > 0 else 'Extremo bajo'), '#ef4444'


# ═══════════════════════════════════════════════════════════
# ENSO (ONI · NOAA/CPC)
# ═══════════════════════════════════════════════════════════

def _clasificar_oni(anom: float) -> dict[str, Any]:
    a = _f(anom)
    aa = abs(a)
    if a >= 0.5:
        fase, color = 'El Niño', '#f87171'
        if aa >= 1.5:
            intensidad = 'Fuerte'
        elif aa >= 1.0:
            intensidad = 'Moderado'
        else:
            intensidad = 'Débil'
    elif a <= -0.5:
        fase, color = 'La Niña', '#60a5fa'
        if aa >= 1.5:
            intensidad = 'Fuerte'
        elif aa >= 1.0:
            intensidad = 'Moderada'
        else:
            intensidad = 'Débil'
    else:
        fase, color, intensidad = 'Neutral', '#94a3b8', '—'
    return {
        'ok': True,
        'fase': fase,
        'intensidad': intensidad,
        'oni': round(a, 2),
        'color': color,
        'label': f'{fase}' + (f' {intensidad}' if intensidad != '—' else ''),
    }


def fase_enso(fetch_text: FetchText) -> dict[str, Any]:
    """Último ONI publicado por NOAA/CPC. Cache 12 h (global)."""
    cache_key = 'enso:oni:v1'
    cached = django_cache.get(cache_key)
    if cached:
        return cached

    try:
        raw = fetch_text(_ONI_URL)
        if not raw or not isinstance(raw, str):
            raise Exception('ONI vacío')
        last = None
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.upper().startswith('SEAS'):
                continue
            parts = re.split(r'\s+', line)
            if len(parts) < 4:
                continue
            seas, yr, _tot, anom = parts[0], parts[1], parts[2], parts[3]
            try:
                anom_f = float(anom)
                yr_i = int(yr)
            except ValueError:
                continue
            last = {'seas': seas, 'year': yr_i, 'oni': anom_f}
        if not last:
            raise Exception('Sin filas ONI')
        result = _clasificar_oni(last['oni'])
        result['periodo'] = f"{last['seas']} {last['year']}"
        result['fuente'] = 'NOAA/CPC ONI'
        result['nota'] = 'ONI = media móvil 3 meses de anomalía SST Niño 3.4. Umbral ±0.5 °C.'
        django_cache.set(cache_key, result, 43200)
        return result
    except Exception as e:
        return {
            'ok': False,
            'fase': 'N/D',
            'intensidad': '—',
            'oni': None,
            'color': '#94a3b8',
            'label': 'ENSO no disponible',
            'error': str(e)[:120],
        }


# ═══════════════════════════════════════════════════════════
# Serie mensual (archive) — compartida climograma + sequía
# ═══════════════════════════════════════════════════════════

def _agregar_mensual(daily: dict) -> list[dict[str, Any]]:
    """Agrupa daily → lista cronológica {year, month, precip, temp, eto}."""
    times = daily.get('time') or []
    precip = daily.get('precipitation_sum') or []
    temp = daily.get('temperature_2m_mean') or []
    eto = daily.get('et0_fao_evapotranspiration') or []
    buckets: dict[tuple[int, int], dict[str, Any]] = {}
    for i, t in enumerate(times):
        try:
            y, m = int(t[0:4]), int(t[5:7])
        except (TypeError, ValueError, IndexError):
            continue
        key = (y, m)
        if key not in buckets:
            buckets[key] = {'year': y, 'month': m, 'precip': 0.0, 'temp_sum': 0.0, 'temp_n': 0, 'eto': 0.0, 'days': 0}
        b = buckets[key]
        b['precip'] += _f(precip[i] if i < len(precip) else 0)
        b['eto'] += _f(eto[i] if i < len(eto) else 0)
        if i < len(temp) and temp[i] is not None:
            b['temp_sum'] += _f(temp[i])
            b['temp_n'] += 1
        b['days'] += 1

    out = []
    for key in sorted(buckets.keys()):
        b = buckets[key]
        # Mes incompleto al final: exigir al menos 20 días
        if b['days'] < 20 and key != max(buckets.keys()):
            continue
        out.append({
            'year': b['year'],
            'month': b['month'],
            'precip': round(b['precip'], 2),
            'temp': round(b['temp_sum'] / b['temp_n'], 2) if b['temp_n'] else None,
            'eto': round(b['eto'], 2),
            'days': b['days'],
            'completo': b['days'] >= 25,
        })
    return out


def serie_mensual_archivo(
    lat: float,
    lon: float,
    fetch_json: FetchJson,
    *,
    anios: int = 30,
) -> list[dict[str, Any]]:
    """Precip / temp / ETo mensuales ~30 años. Cache 12 h por coordenada."""
    lat_k, lon_k = round(float(lat), 3), round(float(lon), 3)
    cache_key = f'clima:mensual:v2:{lat_k}:{lon_k}:{anios}'
    cached = django_cache.get(cache_key)
    if cached is not None:
        return cached

    end = date.today() - timedelta(days=1)
    start = date(end.year - anios, 1, 1)
    url = (
        'https://archive-api.open-meteo.com/v1/archive'
        f'?latitude={lat}&longitude={lon}'
        f'&start_date={start.isoformat()}&end_date={end.isoformat()}'
        '&daily=precipitation_sum,temperature_2m_mean,et0_fao_evapotranspiration'
        '&timezone=auto'
    )
    data = fetch_json(url)
    if not data or 'error' in data or 'daily' not in data:
        raise Exception((data or {}).get('reason', 'Archive mensual sin datos'))
    series = _agregar_mensual(data['daily'])
    if len(series) < 24:
        raise Exception('Serie mensual insuficiente')
    django_cache.set(cache_key, series, 43200)
    return series


# ═══════════════════════════════════════════════════════════
# Climograma
# ═══════════════════════════════════════════════════════════

def climograma_historico(
    lat: float,
    lon: float,
    fetch_json: FetchJson,
    *,
    anios: int = 30,
) -> dict[str, Any]:
    """
    Mes a mes: año en curso vs media climatológica (~30 años previos + actuales completos).
    """
    lat_k, lon_k = round(float(lat), 3), round(float(lon), 3)
    cache_key = f'clima:cg:v1:{lat_k}:{lon_k}:{anios}'
    cached = django_cache.get(cache_key)
    if cached:
        return cached

    try:
        series = serie_mensual_archivo(lat, lon, fetch_json, anios=anios)
        anio_actual = date.today().year
        # Climatología: todos los años excepto el actual (o incluir años previos completos)
        clima_p = defaultdict(list)
        clima_t = defaultdict(list)
        actual_p = {}
        actual_t = {}
        for row in series:
            m = row['month']
            if row['year'] == anio_actual:
                actual_p[m] = row['precip']
                if row['temp'] is not None:
                    actual_t[m] = row['temp']
            else:
                clima_p[m].append(row['precip'])
                if row['temp'] is not None:
                    clima_t[m].append(row['temp'])

        labels, precip_clim, precip_act, temp_clim, temp_act = [], [], [], [], []
        anom_p_acum = 0.0
        meses_neg = 0
        meses_cmp = 0
        for m in range(1, 13):
            labels.append(_MES_ES[m])
            mp = _mean(clima_p[m]) if clima_p[m] else None
            mt = _mean(clima_t[m]) if clima_t[m] else None
            precip_clim.append(round(mp, 1) if mp is not None else None)
            temp_clim.append(round(mt, 1) if mt is not None else None)
            pa = actual_p.get(m)
            ta = actual_t.get(m)
            # Mes futuro del año: null
            if m > date.today().month and anio_actual == date.today().year:
                precip_act.append(None)
                temp_act.append(None)
            else:
                precip_act.append(round(pa, 1) if pa is not None else None)
                temp_act.append(round(ta, 1) if ta is not None else None)
            if pa is not None and mp is not None and m <= date.today().month:
                d = pa - mp
                anom_p_acum += d
                meses_cmp += 1
                if d < -5:
                    meses_neg += 1

        destacar = meses_cmp >= 3 and (anom_p_acum < -30 or meses_neg >= 3)
        result = {
            'ok': True,
            'anio': anio_actual,
            'anios_base': anios,
            'labels': labels,
            'precip_clim': precip_clim,
            'precip_act': precip_act,
            'temp_clim': temp_clim,
            'temp_act': temp_act,
            'anomalia_precip_acum': round(anom_p_acum, 1),
            'meses_secos': meses_neg,
            'destacar': destacar,
            'titulo': f'Climograma {anio_actual} vs media {anios} años',
            'nota': 'Barras: precipitación (mm). Líneas: temperatura media (°C).',
        }
        django_cache.set(cache_key, result, 21600)
        return result
    except Exception as e:
        return {'ok': False, 'error': str(e)[:160], 'destacar': False}


# ═══════════════════════════════════════════════════════════
# SPI / SPEI
# ═══════════════════════════════════════════════════════════

def _etiqueta_spi(v: Optional[float]) -> tuple[str, str]:
    if v is None:
        return 'N/D', '#94a3b8'
    if v <= -2.0:
        return 'Sequía extrema', '#7f1d1d'
    if v <= -1.5:
        return 'Sequía severa', '#ef4444'
    if v <= -1.0:
        return 'Sequía moderada', '#fb923c'
    if v <= -0.5:
        return 'Ligeramente seco', '#fbbf24'
    if v < 0.5:
        return 'Normal', '#4ade80'
    if v < 1.0:
        return 'Ligeramente húmedo', '#67e8f9'
    if v < 1.5:
        return 'Moderadamente húmedo', '#38bdf8'
    if v < 2.0:
        return 'Muy húmedo', '#2563eb'
    return 'Extremadamente húmedo', '#1d4ed8'


def _rolling_sums(vals: list[float], scale: int) -> list[Optional[float]]:
    out: list[Optional[float]] = [None] * len(vals)
    if scale < 1:
        return out
    acc = 0.0
    for i, v in enumerate(vals):
        acc += v
        if i >= scale:
            acc -= vals[i - scale]
        if i >= scale - 1:
            out[i] = acc
    return out


def _fit_gamma_moments(xs: list[float]) -> Optional[tuple[float, float]]:
    pos = [x for x in xs if x > 1e-6]
    if len(pos) < 12:
        return None
    m = _mean(pos)
    v = _std(pos) ** 2
    if m < 1e-9 or v < 1e-12:
        return None
    alpha = (m * m) / v
    beta = v / m
    if alpha < 0.05 or beta < 1e-9:
        return None
    return alpha, beta


def _inv_norm_approx(p: float) -> float:
    """Aproximación Acklam de Φ⁻¹ (p en (0,1))."""
    p = min(max(p, 1e-10), 1.0 - 1e-10)
    a = [
        -3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
        1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00,
    ]
    b = [
        -5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
        6.680131188771972e+01, -1.328068155288572e+01,
    ]
    c = [
        -7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
        -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00,
    ]
    d = [
        7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
        3.754408661907416e+00,
    ]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5]) * q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def _gamma_cdf_lower(x: float, alpha: float, beta: float) -> float:
    """CDF gamma incompleta inferior (serie) — suficiente para SPI operativo."""
    if x <= 0:
        return 0.0
    # Usamos forma shape-scale: dens ∝ x^{α-1} e^{-x/β}
    # Regularized lower gamma P(α, x/β)
    z = x / beta
    if z <= 0:
        return 0.0
    # Serie para P
    if alpha > 100:
        # Normal approx for large alpha
        return 0.5 * (1 + math.erf((z - alpha) / math.sqrt(2 * alpha)))
    term = 1.0 / alpha
    suma = term
    for n in range(1, 200):
        term *= z / (alpha + n)
        suma += term
        if term < 1e-12:
            break
    try:
        log_g = math.lgamma(alpha)
    except ValueError:
        return 0.5
    val = math.exp(-z + alpha * math.log(z) - log_g) * suma
    return min(max(val, 0.0), 1.0)


def _spi_valor(x: float, hist: list[float]) -> Optional[float]:
    """SPI vía gamma (Thom/moments) + Φ⁻¹; fallback z-score."""
    if not hist or x is None:
        return None
    p0 = sum(1 for h in hist if h <= 1e-6) / len(hist)
    fit = _fit_gamma_moments(hist)
    if fit is None:
        m, s = _mean(hist), _std(hist)
        if s < 1e-9:
            return 0.0
        return round((x - m) / s, 2)
    alpha, beta = fit
    if x <= 1e-6:
        # Probabilidad acumulada en cero
        cdf = p0 / 2.0 if p0 > 0 else 1e-4
    else:
        g = _gamma_cdf_lower(x, alpha, beta)
        cdf = p0 + (1.0 - p0) * g
    cdf = min(max(cdf, 1e-6), 1.0 - 1e-6)
    return round(_inv_norm_approx(cdf), 2)


def _indice_escala(vals: list[float], scale: int) -> Optional[float]:
    rolls = _rolling_sums(vals, scale)
    hist = [r for r in rolls[:-1] if r is not None]
    actual = rolls[-1]
    if actual is None or len(hist) < 24:
        return None
    return _spi_valor(actual, hist)


def _spei_valor(x: float, hist: list[float]) -> Optional[float]:
    """SPEI operativo: estandarización (z) del balance P−ETo (permite negativos)."""
    if not hist or x is None:
        return None
    m, s = _mean(hist), _std(hist)
    if s < 1e-9:
        return 0.0
    return round((x - m) / s, 2)


def _indice_escala_spei(vals: list[float], scale: int) -> Optional[float]:
    rolls = _rolling_sums(vals, scale)
    hist = [r for r in rolls[:-1] if r is not None]
    actual = rolls[-1]
    if actual is None or len(hist) < 24:
        return None
    return _spei_valor(actual, hist)


def indices_sequia(
    lat: float,
    lon: float,
    fetch_json: FetchJson,
    *,
    con_spei: bool = True,
    anios: int = 30,
) -> dict[str, Any]:
    lat_k, lon_k = round(float(lat), 3), round(float(lon), 3)
    cache_key = f'clima:spi:v1:{lat_k}:{lon_k}:{anios}:{int(con_spei)}'
    cached = django_cache.get(cache_key)
    if cached:
        return cached

    try:
        series = serie_mensual_archivo(lat, lon, fetch_json, anios=anios)
        # Usar solo meses razonablemente completos excepto el último (parcial OK si ≥20 d)
        precip = [row['precip'] for row in series]
        balance = [row['precip'] - row['eto'] for row in series]

        def pack(nombre: str, val: Optional[float]) -> dict[str, Any]:
            lab, col = _etiqueta_spi(val)
            return {'valor': val, 'label': lab, 'color': col, 'nombre': nombre}

        result = {
            'ok': True,
            'spi3': pack('SPI-3', _indice_escala(precip, 3)),
            'spi6': pack('SPI-6', _indice_escala(precip, 6)),
            'spei3': None,
            'spei6': None,
            'anios_base': anios,
            'n_meses': len(series),
            'nota': 'SPI: precipitación estandarizada (gamma). SPEI: balance P−ETo estandarizado.',
        }
        if con_spei:
            result['spei3'] = pack('SPEI-3', _indice_escala_spei(balance, 3))
            result['spei6'] = pack('SPEI-6', _indice_escala_spei(balance, 6))
        django_cache.set(cache_key, result, 21600)
        return result
    except Exception as e:
        return {'ok': False, 'error': str(e)[:160]}


# ═══════════════════════════════════════════════════════════
# Panel base (corto plazo)
# ═══════════════════════════════════════════════════════════

def resumen_climatologia(lat: float, lon: float, sector: str, dias: int, fetch_json: FetchJson) -> dict[str, Any]:
    """
    fetch_json(url) -> dict  (inyectar _get_meteo u otro GET).
    dias acotado a [7, 90].
    """
    sector = (sector or 'agro').lower().strip()
    cfg = _SECTOR_CFG.get(sector, _SECTOR_CFG['agro'])
    dias = max(7, min(int(dias or 30), 90))

    cache_key = f'clima:{sector}:{round(float(lat),3)}:{round(float(lon),3)}:{dias}'
    cached = django_cache.get(cache_key)
    if cached:
        return cached

    end = datetime.utcnow().date() - timedelta(days=1)
    start = end - timedelta(days=dias - 1)
    url = (
        'https://archive-api.open-meteo.com/v1/archive'
        f'?latitude={lat}&longitude={lon}'
        f'&start_date={start.isoformat()}&end_date={end.isoformat()}'
        f'&daily={cfg["daily"]}&timezone=auto'
    )

    try:
        data = fetch_json(url)
        if not data or 'error' in data or 'daily' not in data:
            raise Exception((data or {}).get('reason', 'Archive sin datos'))
        daily = data['daily']
        raw_p = daily.get(cfg['primary']) or []
        vals = [_f(v) for v in raw_p if v is not None]

        if len(vals) < 5:
            raise Exception('Serie histórica insuficiente')

        hoy = vals[-1]
        hist = vals[:-1] if len(vals) > 1 else vals
        media = _mean(hist)
        desvio = _std(hist)
        z = ((hoy - media) / desvio) if desvio > 1e-6 else 0.0
        label, color = _etiqueta_z(z, cfg['primary'])

        sec_vals = []
        sec_hoy = None
        sec_media = None
        raw_s = daily.get(cfg['secondary']) or []
        for v in raw_s:
            if v is None:
                continue
            sec_vals.append(_f(v))
        if sec_vals:
            sec_hoy = sec_vals[-1]
            sec_media = _mean(sec_vals[:-1] if len(sec_vals) > 1 else sec_vals)

        result = {
            'ok': True,
            'sector': sector,
            'dias': dias,
            'desde': start.isoformat(),
            'hasta': end.isoformat(),
            'primary_label': cfg['primary_label'],
            'unidad': cfg['unidad'],
            'hoy': round(hoy, 2),
            'media': round(media, 2),
            'desvio': round(desvio, 2),
            'anomalia': round(hoy - media, 2),
            'z': round(z, 2),
            'label': label,
            'color': color,
            'p10': round(_percentile(hist, 10) or 0, 2),
            'p50': round(_percentile(hist, 50) or 0, 2),
            'p90': round(_percentile(hist, 90) or 0, 2),
            'n': len(hist),
            'secondary_label': cfg['secondary_label'],
            'secondary_unidad': cfg['secondary_unidad'],
            'secondary_hoy': round(sec_hoy, 2) if sec_hoy is not None else None,
            'secondary_media': round(sec_media, 2) if sec_media is not None else None,
            'nota': cfg.get('nota') or '',
            'con_spei': bool(cfg.get('spei')),
        }
        django_cache.set(cache_key, result, 3600)
        return result
    except Exception as e:
        return {
            'ok': False,
            'sector': sector,
            'dias': dias,
            'error': str(e)[:160],
            'label': 'No disponible',
            'color': '#94a3b8',
            'con_spei': bool(cfg.get('spei')),
        }
