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
