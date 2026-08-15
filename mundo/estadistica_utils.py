# -*- coding: utf-8 -*-
"""
============================================================
MÓDULO DE ESTADÍSTICA CLIMÁTICA (pestaña "📊 Estadística")
============================================================
Funciones puras en Python estándar (sin numpy/scipy) para calcular,
a partir de series horarias reales de Open-Meteo:

  - Resumen de caja (boxplot): mínimo, Q1, mediana, Q3, máximo, outliers.
  - Distribución de frecuencias relativas (histograma).
  - Ajuste de una distribución de Poisson a un conteo de "eventos"
    (ej. horas de riesgo por día) y comparación observado vs. teórico.
  - Test de hipótesis de bondad de ajuste Chi-cuadrado para validar
    si el conteo de eventos es compatible con un proceso de Poisson.

No se agregan dependencias nuevas: se usa `math.erf` (built-in desde
Python 3.2) junto con la aproximación de Wilson-Hilferty para no
necesitar tablas ni la librería scipy.
============================================================
"""
import math
from collections import defaultdict


# ------------------------------------------------------------------
# Utilidades de distribución normal (para aproximar p-valores)
# ------------------------------------------------------------------
def normal_cdf(x):
    """Función de distribución acumulada de la Normal(0,1) usando erf."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


# ------------------------------------------------------------------
# BOXPLOT
# ------------------------------------------------------------------
def _percentil(datos_ordenados, p):
    n = len(datos_ordenados)
    if n == 1:
        return datos_ordenados[0]
    k = (n - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return datos_ordenados[int(k)]
    return datos_ordenados[f] + (datos_ordenados[c] - datos_ordenados[f]) * (k - f)


def resumen_boxplot(valores):
    """
    Calcula el resumen de 5 números (+ outliers) de una muestra,
    usando el método del rango intercuartílico (IQR), tal como se
    define un boxplot clásico de Tukey.
    """
    datos = sorted(v for v in valores if v is not None)
    n = len(datos)
    if n == 0:
        return None

    q1 = _percentil(datos, 0.25)
    mediana = _percentil(datos, 0.5)
    q3 = _percentil(datos, 0.75)
    iqr = q3 - q1
    lim_inf = q1 - 1.5 * iqr
    lim_sup = q3 + 1.5 * iqr

    dentro = [v for v in datos if lim_inf <= v <= lim_sup]
    outliers = [round(v, 2) for v in datos if v < lim_inf or v > lim_sup]

    return {
        'min': round(min(dentro), 2) if dentro else round(datos[0], 2),
        'q1': round(q1, 2),
        'mediana': round(mediana, 2),
        'q3': round(q3, 2),
        'max': round(max(dentro), 2) if dentro else round(datos[-1], 2),
        'outliers': outliers,
        'n': n,
    }


def resumen_boxplot_agrupado(grupos):
    """
    grupos: dict ordenado {etiqueta: [valores...]}
    Devuelve una lista de resúmenes de boxplot, uno por grupo
    (ideal para graficar varios días/franjas horarias uno al lado del otro).
    """
    resultado = []
    for etiqueta, valores in grupos.items():
        r = resumen_boxplot(valores)
        if r:
            r['label'] = etiqueta
            resultado.append(r)
    return resultado


# ------------------------------------------------------------------
# FRECUENCIAS RELATIVAS (HISTOGRAMA)
# ------------------------------------------------------------------
def histograma_relativo(valores, n_bins=8):
    """
    Agrupa una serie continua en `n_bins` intervalos de igual ancho
    y calcula frecuencia absoluta y relativa (%) por intervalo.
    """
    datos = [v for v in valores if v is not None]
    if not datos:
        return []

    vmin, vmax = min(datos), max(datos)
    if vmin == vmax:
        vmax = vmin + 1

    ancho = (vmax - vmin) / n_bins
    bins = [0] * n_bins
    for v in datos:
        idx = int((v - vmin) / ancho)
        if idx >= n_bins:
            idx = n_bins - 1
        if idx < 0:
            idx = 0
        bins[idx] += 1

    total = len(datos)
    resultado = []
    for i, cnt in enumerate(bins):
        ini = vmin + i * ancho
        fin = ini + ancho
        resultado.append({
            'rango': f"{ini:.1f} a {fin:.1f}",
            'frecuencia': cnt,
            'frecuencia_relativa': round(cnt / total * 100, 1),
        })
    return resultado


# ------------------------------------------------------------------
# DISTRIBUCIÓN DE POISSON
# ------------------------------------------------------------------
def poisson_pmf(k, lam):
    """P(X = k) para X ~ Poisson(lambda)."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    try:
        return math.exp(-lam) * (lam ** k) / math.factorial(k)
    except OverflowError:
        return 0.0


def ajuste_poisson(conteos_por_periodo):
    """
    conteos_por_periodo: lista con la cantidad de "eventos" observados
    en cada período (ej. horas de riesgo por día).

    Estima lambda = media muestral y compara la distribución observada
    de conteos contra la distribución de Poisson teórica.
    """
    n = len(conteos_por_periodo)
    if n == 0:
        return None

    lam = sum(conteos_por_periodo) / n
    k_max = max(max(conteos_por_periodo), 3)

    observado = [0] * (k_max + 1)
    for c in conteos_por_periodo:
        idx = min(c, k_max)
        observado[idx] += 1

    teorico = [poisson_pmf(k, lam) * n for k in range(k_max + 1)]

    return {
        'lambda': round(lam, 3),
        'k': list(range(k_max + 1)),
        'observado': observado,
        'teorico': [round(t, 3) for t in teorico],
        'n_periodos': n,
    }


# ------------------------------------------------------------------
# TEST DE HIPÓTESIS: BONDAD DE AJUSTE CHI-CUADRADO
# ------------------------------------------------------------------
def chi2_sf_wilson_hilferty(x, df):
    """
    p-valor aproximado P(X > x) para X ~ Chi-cuadrado(df),
    usando la aproximación de Wilson-Hilferty (evita depender de scipy).
    """
    if x <= 0 or df <= 0:
        return 1.0
    z = (((x / df) ** (1 / 3)) - (1 - 2 / (9 * df))) / math.sqrt(2 / (9 * df))
    return max(0.0, min(1.0, 1 - normal_cdf(z)))


def test_bondad_ajuste_poisson(observado, teorico, alfa=0.05):
    """
    H0: el conteo de eventos por período sigue una distribución de Poisson.
    H1: el conteo de eventos por período NO sigue una distribución de Poisson.

    Aplica la regla de Cochran (agrupar categorías con esperado < 5) antes
    de calcular el estadístico Chi-cuadrado, para no invalidar el test.
    """
    obs, esp = [], []
    acc_o, acc_e = 0, 0
    for o, e in zip(observado, teorico):
        acc_o += o
        acc_e += e
        if acc_e >= 5:
            obs.append(acc_o)
            esp.append(acc_e)
            acc_o, acc_e = 0, 0
    if acc_e > 0:
        if esp:
            obs[-1] += acc_o
            esp[-1] += acc_e
        else:
            obs.append(acc_o)
            esp.append(max(acc_e, 0.01))

    k = len(obs)
    if k < 2:
        return None

    # grados de libertad = (nº categorías - 1) - (1 parámetro estimado: lambda)
    df = max(k - 2, 1)
    chi2_stat = sum(((o - e) ** 2) / e for o, e in zip(obs, esp) if e > 0)
    p_valor = chi2_sf_wilson_hilferty(chi2_stat, df)
    rechaza = p_valor < alfa

    return {
        'h0': 'El número de horas de riesgo por bloque de 6h sigue una distribución de Poisson.',
        'h1': 'El número de horas de riesgo por bloque de 6h NO sigue una distribución de Poisson.',
        'estadistico': round(chi2_stat, 3),
        'grados_libertad': df,
        'p_valor': round(p_valor, 4),
        'alfa': alfa,
        'rechaza_h0': rechaza,
        'conclusion': (
            f"Con p = {round(p_valor, 4)} < α = {alfa}, se RECHAZA H0: el patrón de eventos "
            "no se ajusta a un proceso de Poisson en este período."
            if rechaza else
            f"Con p = {round(p_valor, 4)} ≥ α = {alfa}, NO se rechaza H0: el patrón de eventos "
            "es estadísticamente compatible con un proceso de Poisson."
        ),
    }


def motivo_test_no_disponible(conteos_por_periodo, evento_desc=""):
    """
    Cuando el test de bondad de ajuste no puede calcularse (menos de 2
    categorías tras aplicar la regla de Cochran), explica POR QUÉ en
    lenguaje claro, en vez de un mensaje técnico genérico.

    Distingue el caso "el evento no ocurrió nunca en la muestra" (0
    variabilidad, el test no aplica conceptualmente) del caso "el evento
    ocurrió pero muy pocas veces" (variabilidad insuficiente para un
    test Chi-cuadrado válido).
    """
    total_periodos = len(conteos_por_periodo)
    total_eventos = sum(conteos_por_periodo)
    desc = f' de "{evento_desc}"' if evento_desc else ''
    if total_eventos == 0:
        return (
            f'No se registró ningún evento{desc} en los {total_periodos} períodos de este '
            'pronóstico: al no haber variabilidad en los datos, el test de bondad de ajuste '
            'no es aplicable (no hay nada que contrastar contra Poisson).'
        )
    return (
        f'Los eventos{desc} fueron demasiado infrecuentes en este período (solo {total_eventos} '
        f'en {total_periodos} períodos) para formar las categorías mínimas que exige un test '
        'Chi-cuadrado válido. Esto es una limitación de la muestra, no un error de cálculo.'
    )


# ------------------------------------------------------------------
# PERCENTILES DE RIESGO (P90/P95/P99)
# ------------------------------------------------------------------
def percentiles_riesgo(valores, percentiles=(50, 90, 95, 99)):
    """
    Calcula percentiles de una muestra para análisis de riesgo operativo
    (ej. "el viento supera este valor solo el 5% del tiempo" = P95).
    """
    datos = sorted(v for v in valores if v is not None)
    n = len(datos)
    if n == 0:
        return None
    return {
        'n': n,
        'valores': [
            {'p': p, 'valor': round(_percentil(datos, p / 100), 2)}
            for p in percentiles
        ],
    }


# ------------------------------------------------------------------
# DISTRIBUCIÓN DE WEIBULL (estándar en evaluación de recurso eólico)
# ------------------------------------------------------------------
def ajuste_weibull(valores, n_bins=10):
    """
    Ajusta una distribución de Weibull de 2 parámetros a una muestra de
    velocidad de viento (>= 0), usando el método de momentos con la
    aproximación de Justus (1978) para el parámetro de forma k a partir
    del coeficiente de variación. Es el modelo estándar en evaluación de
    recurso eólico (no requiere numpy/scipy).

    k (forma): a mayor k, menos dispersa la velocidad de viento.
    c (escala): parámetro relacionado con el viento medio, mismas unidades
    que `valores`.
    """
    datos = [v for v in valores if v is not None and v >= 0]
    n = len(datos)
    if n < 10:
        return None

    media = sum(datos) / n
    if media <= 0:
        return None
    varianza = sum((v - media) ** 2 for v in datos) / n
    desvio = math.sqrt(varianza)
    if desvio <= 0:
        return None

    cv = desvio / media
    k = cv ** (-1.086)  # Aproximación de Justus
    k = max(0.8, min(k, 8.0))  # límites físicamente razonables
    c = media / math.gamma(1 + 1 / k)

    # Densidad de potencia eólica teórica media (rho aire ≈ 1.225 kg/m3)
    densidad_potencia = 0.5 * 1.225 * (c ** 3) * math.gamma(1 + 3 / k)

    vmax = max(datos) * 1.15 if max(datos) > 0 else 1.0
    ancho = vmax / n_bins
    obs_bins = [0] * n_bins
    for v in datos:
        idx = min(int(v / ancho), n_bins - 1) if ancho > 0 else 0
        obs_bins[idx] += 1

    curva = []
    for i in range(n_bins):
        ini = ancho * i
        fin = ancho * (i + 1)
        centro = (ini + fin) / 2
        dens = (k / c) * ((centro / c) ** (k - 1)) * math.exp(-((centro / c) ** k)) if c > 0 else 0
        curva.append({
            'rango': f"{ini:.1f}–{fin:.1f}",
            'observado': obs_bins[i],
            'teorico': round(dens * ancho * n, 2),
        })

    return {
        'k_forma': round(k, 3),
        'c_escala': round(c, 3),
        'media_muestral': round(media, 2),
        'densidad_potencia_wm2': round(densidad_potencia, 1),
        'curva': curva,
        'n': n,
    }


# ------------------------------------------------------------------
# DISTRIBUCIÓN t DE STUDENT (para test de hipótesis sobre medias)
# ------------------------------------------------------------------
def _betacf(a, b, x):
    """Fracción continua de Lentz para la función beta incompleta (Numerical Recipes)."""
    maxit = 200
    eps = 3e-12
    fpmin = 1e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, maxit + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def _incbeta(a, b, x):
    """Función beta incompleta regularizada I_x(a, b) (sin depender de scipy)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    bt = math.exp(lbeta)
    if x < (a + 1) / (a + b + 2):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1 - x) / b


def t_p_valor_dos_colas(t_stat, df):
    """p-valor a dos colas de |t_stat| para una t de Student con `df` grados de libertad."""
    if df <= 0:
        return 1.0
    x = df / (df + t_stat * t_stat)
    return max(0.0, min(1.0, _incbeta(df / 2.0, 0.5, x)))


def carta_control(valor_hoy, media_hist, desvio_hist, n_hist):
    """
    Carta de control estadístico (tipo Shewhart) para el valor de "hoy"
    contra la media y desvío histórico (ya calculados en BigQuery a
    partir de los snapshots horarios reales). Marca anomalía si "hoy"
    cae fuera de las bandas de ±2σ / ±3σ.
    """
    if valor_hoy is None or media_hist is None or desvio_hist is None or not n_hist or n_hist < 3:
        return None
    if desvio_hist <= 0:
        return None
    z = (valor_hoy - media_hist) / desvio_hist
    return {
        'media': round(media_hist, 2),
        'desvio': round(desvio_hist, 2),
        'limite_superior_2s': round(media_hist + 2 * desvio_hist, 2),
        'limite_inferior_2s': round(media_hist - 2 * desvio_hist, 2),
        'limite_superior_3s': round(media_hist + 3 * desvio_hist, 2),
        'limite_inferior_3s': round(media_hist - 3 * desvio_hist, 2),
        'valor_hoy': round(valor_hoy, 2),
        'z_score': round(z, 2),
        'n_historico': n_hist,
        'estado': 'fuera_3s' if abs(z) > 3 else ('fuera_2s' if abs(z) > 2 else 'normal'),
    }


def test_t_una_observacion(valor_hoy, media_hist, desvio_hist, n_hist, alfa=0.05):
    """
    Test t de Student de una nueva observación ("hoy") contra la muestra
    histórica de semanas anteriores a esta misma hora.

    H0: "hoy" proviene del mismo proceso climático que el histórico.
    H1: "hoy" difiere significativamente del patrón histórico.

    Usa el error estándar de una PREDICCIÓN individual (SE = σ·√(1+1/n)),
    mayor al error estándar de la media, porque se compara un único valor
    puntual (no un promedio) contra la distribución histórica.
    """
    if valor_hoy is None or media_hist is None or desvio_hist is None or not n_hist or n_hist < 3:
        return None
    if desvio_hist <= 0:
        return None

    se = desvio_hist * math.sqrt(1 + 1 / n_hist)
    t_stat = (valor_hoy - media_hist) / se
    df = n_hist - 1
    p_valor = t_p_valor_dos_colas(t_stat, df)
    rechaza = p_valor < alfa

    return {
        'h0': 'El valor de hoy proviene del mismo proceso climático que el histórico de semanas anteriores a esta hora (no hay diferencia significativa).',
        'h1': 'El valor de hoy difiere significativamente del patrón histórico a esta hora.',
        'media_historica': round(media_hist, 2),
        'desvio_historico': round(desvio_hist, 2),
        'valor_hoy': round(valor_hoy, 2),
        'n_historico': n_hist,
        'estadistico_t': round(t_stat, 3),
        'grados_libertad': df,
        'p_valor': round(p_valor, 4),
        'alfa': alfa,
        'rechaza_h0': rechaza,
        'conclusion': (
            f"Con p = {round(p_valor, 4)} < α = {alfa}, se RECHAZA H0: el valor de hoy es "
            "estadísticamente atípico respecto del patrón histórico a esta hora."
            if rechaza else
            f"Con p = {round(p_valor, 4)} ≥ α = {alfa}, NO se rechaza H0: el valor de hoy es "
            "compatible con la variabilidad histórica normal a esta hora."
        ),
    }


# ------------------------------------------------------------------
# AGRUPAR SERIE HORARIA POR DÍA (usa el array `time` de Open-Meteo)
# ------------------------------------------------------------------
def agrupar_por_dia(tiempos, valores):
    """
    tiempos: lista de strings ISO ("2026-07-22T14:00")
    valores: lista de floats de igual longitud
    Devuelve un dict ordenado {"22/07": [valores del día...], ...}
    """
    grupos = defaultdict(list)
    orden = []
    for t, v in zip(tiempos, valores):
        if v is None or not t:
            continue
        dia = t[8:10] + "/" + t[5:7]  # DD/MM
        if dia not in grupos:
            orden.append(dia)
        grupos[dia].append(v)
    return {d: grupos[d] for d in orden}


# ------------------------------------------------------------------
# AGRUPAR SERIE HORARIA POR BLOQUES DE N HORAS (más granularidad
# que por día completo → más periodos → test de Poisson más robusto)
# ------------------------------------------------------------------
def agrupar_por_bloque(tiempos, valores, horas_bloque=6):
    """
    tiempos: lista de strings ISO ("2026-07-22T14:00")
    valores: lista de floats/ints de igual longitud (ej. 0/1 de "hubo evento")
    horas_bloque: tamaño del bloque horario (6h → 4 periodos por día).

    Con 14 días de pronóstico horario, agrupar por día completo da solo
    ~14 periodos, insuficientes para un test Chi-cuadrado válido si el
    evento es raro. Agrupando por bloques de 6h se obtienen ~56 periodos,
    dando mucho más poder estadístico al test de bondad de ajuste.

    Devuelve un dict ordenado {"22/07 12h": [valores del bloque...], ...}
    """
    grupos = defaultdict(list)
    orden = []
    for t, v in zip(tiempos, valores):
        if v is None or not t:
            continue
        try:
            hora = int(t[11:13])
        except (ValueError, IndexError):
            continue
        bloque_ini = (hora // horas_bloque) * horas_bloque
        etiqueta = f"{t[8:10]}/{t[5:7]} {bloque_ini:02d}h"
        if etiqueta not in grupos:
            orden.append(etiqueta)
        grupos[etiqueta].append(v)
    return {e: grupos[e] for e in orden}


# ------------------------------------------------------------------
# Histórico "misma hora" (fallback Open-Meteo si n8n/BigQuery cae)
# ------------------------------------------------------------------
_HISTORICO_VARS = {
    'agro': {
        'precipitacion': {'api': 'weather', 'campo': 'precipitation', 'factor': 1.0, 'label': 'Precipitación', 'unidad': 'mm'},
        'temperatura': {'api': 'weather', 'campo': 'temperature_2m', 'factor': 1.0, 'label': 'Temperatura', 'unidad': '°C'},
        'humedad': {'api': 'weather', 'campo': 'relative_humidity_2m', 'factor': 1.0, 'label': 'Humedad', 'unidad': '%'},
        'viento': {'api': 'weather', 'campo': 'wind_speed_10m', 'factor': 1.0, 'label': 'Viento', 'unidad': 'km/h'},
        'et0': {'api': 'weather', 'campo': 'et0_fao_evapotranspiration', 'factor': 1.0, 'label': 'ET0', 'unidad': 'mm'},
    },
    'naval': {
        'olas': {'api': 'marine', 'campo': 'wave_height', 'factor': 1.0, 'label': 'Altura de olas', 'unidad': 'm'},
        'periodo_ola': {'api': 'marine', 'campo': 'wave_period', 'factor': 1.0, 'label': 'Período de ola', 'unidad': 's'},
        'viento': {'api': 'weather', 'campo': 'wind_speed_10m', 'factor': 0.539957, 'label': 'Viento', 'unidad': 'kt'},
        'temperatura': {'api': 'weather', 'campo': 'temperature_2m', 'factor': 1.0, 'label': 'Temperatura', 'unidad': '°C'},
    },
    'aereo': {
        'temperatura': {'api': 'weather', 'campo': 'temperature_2m', 'factor': 1.0, 'label': 'Temperatura', 'unidad': '°C', 'models': 'gfs_seamless'},
        'viento': {'api': 'weather', 'campo': 'wind_speed_10m', 'factor': 1.0 / 1.852, 'label': 'Viento', 'unidad': 'kt', 'models': 'gfs_seamless'},
        'rafagas': {'api': 'weather', 'campo': 'wind_gusts_10m', 'factor': 1.0 / 1.852, 'label': 'Ráfagas', 'unidad': 'kt', 'models': 'gfs_seamless'},
        'nubosidad': {'api': 'weather', 'campo': 'cloud_cover', 'factor': 1.0, 'label': 'Nubosidad', 'unidad': '%', 'models': 'gfs_seamless'},
        'cape': {'api': 'weather', 'campo': 'cape', 'factor': 1.0, 'label': 'CAPE', 'unidad': 'J/kg', 'models': 'gfs_seamless'},
    },
    'energia': {
        'radiacion': {'api': 'weather', 'campo': 'shortwave_radiation', 'factor': 1.0, 'label': 'Radiación', 'unidad': 'W/m²'},
        'viento': {'api': 'weather', 'campo': 'wind_speed_10m', 'factor': 1.0 / 3.6, 'label': 'Viento', 'unidad': 'm/s'},
        'temperatura': {'api': 'weather', 'campo': 'temperature_2m', 'factor': 1.0, 'label': 'Temperatura', 'unidad': '°C'},
        'presion': {'api': 'weather', 'campo': 'pressure_msl', 'factor': 1.0, 'label': 'Presión', 'unidad': 'hPa'},
    },
}


def _media(xs):
    return sum(xs) / len(xs) if xs else None


def _desvio(xs):
    if not xs or len(xs) < 2:
        return None
    m = _media(xs)
    var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    return var ** 0.5


def historico_misma_hora_openmeteo(lat, lon, sector, variable, fetch_json, *, past_days=35):
    """
    Compara el valor de la hora actual vs. el mismo slot horario
    en días previos (Open-Meteo past_days). Misma forma de respuesta
    que el webhook n8n/BigQuery para el frontend de Estadística.
    """
    sector = (sector or '').lower()
    vars_sec = _HISTORICO_VARS.get(sector) or {}
    defaults = {
        'agro': 'precipitacion',
        'naval': 'olas',
        'aereo': 'temperatura',
        'energia': 'radiacion',
    }
    if variable not in vars_sec:
        variable = defaults.get(sector, next(iter(vars_sec), None))
    cfg = vars_sec.get(variable)
    if not cfg:
        return {'ok': False, 'error': 'Variable no soportada para histórico'}

    past_days = max(14, min(int(past_days), 92))
    campos = cfg['campo']
    models = cfg.get('models')
    if cfg['api'] == 'marine':
        url = (
            f"https://marine-api.open-meteo.com/v1/marine"
            f"?latitude={lat}&longitude={lon}"
            f"&hourly={campos}&past_days={past_days}&forecast_days=1&timezone=auto"
        )
    else:
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&hourly={campos}&past_days={past_days}&forecast_days=1&timezone=auto"
        )
        if models:
            url += f"&models={models}"

    try:
        data = fetch_json(url)
    except Exception as e:
        return {'ok': False, 'error': f'No se pudo obtener histórico: {e}'}

    if not isinstance(data, dict) or data.get('error'):
        return {'ok': False, 'error': data.get('reason', 'API histórico con error') if isinstance(data, dict) else 'API histórico inválida'}

    hourly = data.get('hourly') or {}
    times = hourly.get('time') or []
    raw = hourly.get(cfg['campo']) or []
    if len(times) < 48:
        return {'ok': False, 'error': 'Serie histórica insuficiente'}

    factor = float(cfg.get('factor') or 1.0)

    def _parse_hourly(payload):
        hourly = (payload or {}).get('hourly') or {}
        times = hourly.get('time') or []
        raw = hourly.get(cfg['campo']) or []
        by_day = defaultdict(dict)
        for i, t in enumerate(times):
            if i >= len(raw) or raw[i] is None:
                continue
            day = str(t)[:10]
            try:
                hour = int(str(t)[11:13])
            except (ValueError, IndexError):
                continue
            by_day[day][hour] = float(raw[i]) * factor
        return by_day

    by_day_hour = _parse_hourly(data)

    # Marino en tierra firme → Open-Meteo devuelve nulls; buscar celda costera cercana
    if cfg['api'] == 'marine' and sum(len(h) for h in by_day_hour.values()) < 24:
        for dlat, dlon in ((0.0, 0.35), (0.0, 0.55), (-0.15, 0.45), (0.15, 0.45), (0.0, -0.35)):
            url_c = (
                f"https://marine-api.open-meteo.com/v1/marine"
                f"?latitude={lat + dlat}&longitude={lon + dlon}"
                f"&hourly={campos}&past_days={past_days}&forecast_days=1&timezone=auto"
            )
            try:
                data_c = fetch_json(url_c)
            except Exception:
                continue
            by_try = _parse_hourly(data_c)
            if sum(len(h) for h in by_try.values()) >= 24:
                by_day_hour = by_try
                break

    days = sorted(by_day_hour.keys())
    if len(days) < 4:
        return {'ok': False, 'error': 'Todavía no hay suficientes días de histórico'}

    # Hora de referencia: última hora disponible del día más reciente
    hoy_day = days[-1]
    horas_hoy = sorted(by_day_hour[hoy_day].keys())
    if not horas_hoy:
        return {'ok': False, 'error': 'Sin dato para la hora actual'}
    hora_ref = horas_hoy[-1]
    valor_hoy = by_day_hour[hoy_day][hora_ref]

    hist_vals = []
    for d in days[:-1]:
        if hora_ref in by_day_hour[d]:
            hist_vals.append(by_day_hour[d][hora_ref])

    if len(hist_vals) < 3:
        return {'ok': False, 'error': 'Pocos días con dato a esta misma hora'}

    media = _media(hist_vals)
    desvio = _desvio(hist_vals)
    diff_pct = None
    if media is not None and abs(media) > 1e-9:
        diff_pct = round(100.0 * (valor_hoy - media) / abs(media), 1)
    elif media is not None:
        diff_pct = 0.0 if abs(valor_hoy - media) < 1e-9 else (100.0 if valor_hoy > media else -100.0)

    # Serie semanal: promedios de la misma hora en ventanas de 7 días (más Hoy)
    prev_days = days[:-1]
    serie = []
    n_sem = min(4, max(1, len(prev_days) // 7))
    for s in range(n_sem, 0, -1):
        bloque = prev_days[-s * 7: -(s - 1) * 7 if s > 1 else None]
        if not bloque:
            continue
        vals = [by_day_hour[d][hora_ref] for d in bloque if hora_ref in by_day_hour[d]]
        if not vals:
            continue
        serie.append({'semana': f'S-{s}', 'valor': round(_media(vals), 2)})
    serie.append({'semana': 'Hoy', 'valor': round(valor_hoy, 2)})

    return {
        'ok': True,
        'fuente': 'open-meteo',
        'sector': sector,
        'variable': variable,
        'variable_label': cfg.get('label'),
        'unidad': cfg.get('unidad'),
        'hora_local': f'{hora_ref:02d}:00',
        'hoy': {'valor': round(valor_hoy, 2), 'fecha': hoy_day},
        'promedio_historico': {
            'valor': round(media, 2),
            'desviacion': round(desvio, 2) if desvio is not None else None,
            'n_dias': len(hist_vals),
        },
        'diferencia_pct': diff_pct,
        'serie_semanas': serie,
        'nota': (
            f'Comparación a las {hora_ref:02d}:00 (hora local) vs. {len(hist_vals)} días previos · '
            'Open-Meteo (fallback; n8n/BigQuery no disponible).'
        ),
    }

