"""
Evapotranspiración de cultivo: ETc y ETa (FAO-56 simplificado).

  ETc = ETo × Kc          (demanda bien regada)
  ETa = ETc × Ks(θ)       (evapo real con estrés hídrico)
"""
from __future__ import annotations

from typing import Any


# Kc FAO-56 típicos (etapa media / pico) — valores de referencia operativa
KC_CULTIVOS: dict[str, dict[str, Any]] = {
    'maiz': {'label': 'Maíz', 'kc_ini': 0.30, 'kc_mid': 1.20},
    'soja': {'label': 'Soja', 'kc_ini': 0.40, 'kc_mid': 1.15},
    'trigo': {'label': 'Trigo', 'kc_ini': 0.30, 'kc_mid': 1.15},
    'girasol': {'label': 'Girasol', 'kc_ini': 0.35, 'kc_mid': 1.10},
    'pasturas': {'label': 'Pasturas', 'kc_ini': 0.40, 'kc_mid': 1.05},
}

# Suelo franco de referencia (m³/m³) — sin textura local del usuario
_THETA_FC = 0.32
_THETA_WP = 0.14
_P_DEPLETION = 0.50  # fracción de agotamiento antes de estrés (cultivos típicos)


def _f(v, default=0.0) -> float:
    try:
        if v is None:
            return float(default)
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def coeficiente_estres_ks(
    theta: float,
    *,
    theta_fc: float = _THETA_FC,
    theta_wp: float = _THETA_WP,
    p: float = _P_DEPLETION,
) -> dict[str, Any]:
    """
    Ks por agotamiento de agua en la zona radicular (FAO-56 cap. 8).

    TAW = θ_fc − θ_wp
    Dr  = θ_fc − θ   (agotamiento desde capacidad de campo)
    RAW = p · TAW
    Ks  = 1 si Dr ≤ RAW;  si no (TAW − Dr) / ((1−p)·TAW)
    """
    th = max(0.0, min(0.60, _f(theta)))
    fc = max(theta_wp + 0.05, _f(theta_fc, _THETA_FC))
    wp = min(fc - 0.05, max(0.02, _f(theta_wp, _THETA_WP)))
    p = max(0.1, min(0.8, _f(p, _P_DEPLETION)))

    taw = fc - wp
    dr = max(0.0, fc - th)
    raw = p * taw

    if dr <= raw:
        ks = 1.0
    else:
        denom = (1.0 - p) * taw
        ks = max(0.0, (taw - dr) / denom) if denom > 0 else 0.0

    rew = max(0.0, min(1.0, (th - wp) / taw)) if taw > 0 else 0.0

    if ks >= 0.95:
        estado, color = 'Sin estrés hídrico', '#4ade80'
    elif ks >= 0.6:
        estado, color = 'Estrés leve', '#fbbf24'
    elif ks >= 0.3:
        estado, color = 'Estrés moderado', '#fb923c'
    else:
        estado, color = 'Estrés severo', '#ef4444'

    return {
        'ks': round(ks, 3),
        'theta': round(th, 3),
        'theta_pct': round(th * 100, 1),
        'theta_fc': round(fc, 3),
        'theta_wp': round(wp, 3),
        'taw': round(taw, 3),
        'dr': round(dr, 3),
        'raw': round(raw, 3),
        'rew': round(rew, 3),
        'estado': estado,
        'color': color,
    }


def resumen_etc_eta(
    eto: float,
    humedad_raiz: float,
    *,
    cultivo_ref: str = 'soja',
    theta_fc: float = _THETA_FC,
    theta_wp: float = _THETA_WP,
) -> dict[str, Any]:
    """
    ETc / ETa para tabla de cultivos + métricas del cultivo de referencia.
    humedad_raiz: soil_moisture 9–27 cm (fracción).
    """
    eto_v = max(0.0, _f(eto))
    ks_info = coeficiente_estres_ks(humedad_raiz, theta_fc=theta_fc, theta_wp=theta_wp)
    ks = ks_info['ks']

    filas = []
    for key, meta in KC_CULTIVOS.items():
        kc = meta['kc_mid']
        etc = round(eto_v * kc, 2)
        eta = round(etc * ks, 2)
        filas.append({
            'key': key,
            'label': meta['label'],
            'kc_ini': meta['kc_ini'],
            'kc_mid': kc,
            'etc': etc,
            'eta': eta,
            'reduccion_pct': round((1.0 - ks) * 100, 0) if ks < 1 else 0,
        })

    ref_key = cultivo_ref if cultivo_ref in KC_CULTIVOS else 'soja'
    ref = next(f for f in filas if f['key'] == ref_key)

    return {
        'eto': round(eto_v, 2),
        'ks': ks,
        'ks_info': ks_info,
        'cultivo_ref': ref_key,
        'cultivo_ref_label': ref['label'],
        'kc_ref': ref['kc_mid'],
        'etc_ref': ref['etc'],
        'eta_ref': ref['eta'],
        'filas': filas,
        'nota': (
            'ETc = ETo×Kc (demanda bien regada). '
            'ETa = ETc×Ks(θ) con θ zona radicular 9–27 cm vs suelo franco de referencia '
            f'(FC={ks_info["theta_fc"]}, WP={ks_info["theta_wp"]}).'
        ),
    }
