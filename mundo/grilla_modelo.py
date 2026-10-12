"""
Grilla real del modelo DWD ICON, leída del open data de Open-Meteo en AWS.

Antes pedíamos ~250 puntos sueltos a la API pública y los interpolábamos: una
grilla de 1,5° (~165 km). Acá leemos la grilla nativa del modelo, 0,125°
(~14 km), que es la misma resolución con la que trabaja Windy.

Los .om son archivos de cientos de MB en S3 con lectura parcial por rangos.
Bajar la ventana regional entera para todas las horas tarda minutos, así que
nunca se hace dentro de un request: `sincronizar()` guarda la corrida en disco
como .npy y las vistas recortan el viewport con memoria mapeada, en ms.

Docs del dataset: https://github.com/open-meteo/open-data (licencia CC-BY-4.0).
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import threading
import time
from pathlib import Path

import numpy as np
import requests
from django.conf import settings
from django.core.cache import caches

BASE_S3 = 'https://openmeteo.s3.amazonaws.com/'
MODELO = 'dwd_icon'

# Sube cuando cambia el formato en disco. Las corridas con versión menor
# que FORMATO_MINIMO no se pueden leer; las de FORMATO_MINIMO..VERSION sí,
# así el mapa sigue pintando la cobertura anterior mientras se baja una más amplia.
VERSION = 4
FORMATO_MINIMO = 3

# Mundo entero, Antártida y polo norte. ICON publica BBOX[-90,-180,90,179.75];
# el este a 180 cierra el hueco de 0,25° del antimeridiano.
REGION = {'sur': -90.0, 'norte': 90.0, 'oeste': -180.0, 'este': 179.75}

# 0 = guardar todas las horas que publique el modelo (ICON ~7,5 días).
# No hay fecha de corte: cada corrida nueva pisa la anterior.
HORAS = 0
CACHE_TTL = 900

# Celdas por lado que devolvemos al navegador. La GPU interpola el resto, así
# que más que esto solo agrega peso al JSON sin verse mejor.
MAX_LADO = 180

# Cada request autenticado cuesta cientos de ms solo por abrir la conexión a la
# base para leer la sesión, así que conviene traer varias horas juntas: mover
# el deslizador dentro del bloque no vuelve a pedir nada.
HORAS_POR_BLOQUE = 12
MAX_VALORES = 200_000
# La ventana mundial no entra cómoda en RAM de una vez (~1,5 GB/variable).
PASO_HORAS_LECTURA = 16

VARIABLES = (
    'temperature_2m',
    'precipitation',
    'pressure_msl',
    'wind_u_component_10m',
    'wind_v_component_10m',
)

CAPAS = {
    'temp': {
        'nombre': 'Temperatura', 'unidad': '°C', 'decimales': 1,
        'variables': ('temperature_2m',),
    },
    # Los decimales van al mínimo que se nota en pantalla: cada decimal de más
    # son cientos de KB por respuesta.
    'lluvia': {
        'nombre': 'Lluvia', 'unidad': 'mm', 'decimales': 1,
        'variables': ('precipitation',),
    },
    'presion': {
        'nombre': 'Presión', 'unidad': 'hPa', 'decimales': 0,
        'variables': ('pressure_msl',),
    },
    'viento': {
        'nombre': 'Viento', 'unidad': 'km/h', 'decimales': 0,
        'variables': ('wind_u_component_10m', 'wind_v_component_10m'),
    },
}

FUENTE = 'DWD ICON 0,125° · Open-Meteo open data (CC-BY-4.0)'


class SinCorrida(Exception):
    """Todavía no hay ninguna corrida del modelo en disco."""


class FueraDeRegion(Exception):
    """El viewport pedido no toca la ventana sincronizada."""


class CapaIncompleta(Exception):
    """La corrida nueva todavía no tiene esa variable en disco."""


_lock = threading.Lock()
_sincronizando = False
_manifest_cache: dict = {'mtime': 0.0, 'data': None}
_arrays: dict = {}


# --------------------------------------------------------------------------
# Rutas
# --------------------------------------------------------------------------

def directorio() -> Path:
    base = os.getenv('GRILLA_DIR')
    raiz = Path(base) if base else Path(settings.BASE_DIR) / 'datos_grilla'
    return raiz / MODELO


def _ruta_manifest() -> Path:
    return directorio() / 'manifest.json'


def _ruta_lock() -> Path:
    return directorio() / '.sync.lock'


def _proceso_vivo(pid: int) -> bool | None:
    """True/False si se puede saber; None si no conviene adivinar (no soltar el lock)."""
    if pid <= 0:
        return False
    if os.name == 'nt':
        try:
            import ctypes
            # QUERY_LIMITED funciona sin derechos de terminar el proceso.
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
            if h:
                ctypes.windll.kernel32.CloseHandle(h)
                return True
            return False
        except Exception:
            return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def sync_en_curso() -> bool:
    """True si este proceso u otro está bajando una corrida."""
    if _sincronizando:
        return True
    p = _ruta_lock()
    try:
        edad = time.time() - p.stat().st_mtime
    except OSError:
        edad = None
    else:
        if edad > 3 * 3600:
            p.unlink(missing_ok=True)
        else:
            try:
                pid = int(p.read_text(encoding='utf-8').strip())
            except (OSError, ValueError):
                pid = 0
            vivo = _proceso_vivo(pid)
            if vivo is False:
                p.unlink(missing_ok=True)
            else:
                return True
    # El proceso viejo no escribía lock: si hay un .npy tocando ahora, está vivo.
    try:
        for carpeta in directorio().iterdir():
            if not carpeta.is_dir():
                continue
            for f in carpeta.glob('*.npy'):
                if time.time() - f.stat().st_mtime < 180:
                    return True
    except OSError:
        pass
    return False


def _tomar_lock_archivo() -> bool:
    directorio().mkdir(parents=True, exist_ok=True)
    p = _ruta_lock()
    try:
        fd = os.open(str(p), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, 'w') as fh:
            fh.write(str(os.getpid()))
        return True
    except FileExistsError:
        if not sync_en_curso():
            return _tomar_lock_archivo()
        return False


def _soltar_lock_archivo() -> None:
    try:
        _ruta_lock().unlink()
    except OSError:
        pass


def cache_respuestas():
    """Caché en memoria del proceso, para respuestas ya serializadas."""
    try:
        return caches['mapas']
    except Exception:
        return caches['default']


# --------------------------------------------------------------------------
# Lectura del manifest local
# --------------------------------------------------------------------------

def manifest() -> dict | None:
    """Manifest de la corrida sincronizada, releído si cambió en disco."""
    ruta = _ruta_manifest()
    try:
        mtime = ruta.stat().st_mtime
    except OSError:
        _manifest_cache.update(mtime=0.0, data=None)
        return None
    if _manifest_cache['data'] is not None and _manifest_cache['mtime'] == mtime:
        return _manifest_cache['data']
    try:
        with open(ruta, encoding='utf-8') as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    if int(data.get('version') or 0) < FORMATO_MINIMO:
        return None
    _manifest_cache.update(mtime=mtime, data=data)
    _arrays.clear()
    return data


def _array(man: dict, variable: str):
    """Array de una variable, mapeado en memoria (no se carga entero)."""
    clave = (man['reference_time'], variable)
    if clave not in _arrays:
        ruta = directorio() / man['carpeta'] / f'{variable}.npy'
        _arrays[clave] = np.load(ruta, mmap_mode='r')
    return _arrays[clave]


# --------------------------------------------------------------------------
# Metadatos remotos
# --------------------------------------------------------------------------

def _bbox_de_wkt(wkt: str) -> tuple[float, float, float, float] | None:
    """BBOX[minlat,minlon,maxlat,maxlon] del CRS que publica Open-Meteo."""
    m = re.search(r'BBOX\[([-\d.,\s]+)\]', wkt or '')
    if not m:
        return None
    partes = [float(x) for x in m.group(1).split(',')]
    if len(partes) != 4:
        return None
    return partes[0], partes[1], partes[2], partes[3]


def corrida_remota(timeout: int = 30) -> dict:
    url = f'{BASE_S3}data_run/{MODELO}/latest.json'
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _raiz_corrida(reference_time: str) -> str:
    fecha = reference_time[:10].replace('-', '/')
    hora = reference_time[11:16].replace(':', '')
    return f'{BASE_S3}data_run/{MODELO}/{fecha}/{hora}Z/'


def _slug(reference_time: str) -> str:
    return reference_time[:13].replace(':', '') + '00Z'


# --------------------------------------------------------------------------
# Sincronización
# --------------------------------------------------------------------------

def _escribir_manifest(man: dict) -> None:
    directorio().mkdir(parents=True, exist_ok=True)
    tmp = _ruta_manifest().with_suffix('.json.tmp')
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(man, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, _ruta_manifest())
    _manifest_cache.update(mtime=0.0, data=None)
    _arrays.clear()


def _abrir_om(url: str, cache_dir: Path):
    """Lector .om sobre HTTP. omfiles exige un OpenFile de fsspec."""
    import fsspec
    from omfiles import OmFileReader

    cache_dir.mkdir(parents=True, exist_ok=True)
    of = fsspec.open(f'blockcache::{url}', mode='rb',
                     blockcache={'cache_storage': str(cache_dir)})
    return OmFileReader(of)


def _leer_ventana(url: str, cache_dir: Path, y0, y1, x0, x1, t0, t1):
    """En Windows el blockcache a veces no puede renombrar el archivo temporal."""
    ultimo = None
    for intento in range(4):
        try:
            lector = _abrir_om(url, cache_dir)
            try:
                return np.asarray(lector[y0:y1, x0:x1, t0:t1], dtype=np.float32)
            finally:
                lector.close()
        except Exception as e:
            ultimo = e
            shutil.rmtree(cache_dir, ignore_errors=True)
            time.sleep(1.5 * (intento + 1))
    raise ultimo


def _guardar_npy(ruta: Path, datos) -> None:
    """Escribe .npy por un temporal: en Windows no se puede pisar un mmap abierto."""
    tmp = ruta.with_name(ruta.stem + '.tmp.npy')
    try:
        with open(tmp, 'wb') as fh:
            np.save(fh, datos)
        os.replace(tmp, ruta)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


def sincronizar(log=None, horas: int = HORAS, forzar: bool = False) -> dict:
    """Baja la ventana regional de la última corrida y la deja en disco.

    Tarda del orden de minutos: llamarla desde un comando o un hilo, nunca
    desde una vista.
    """
    global _sincronizando

    def decir(msg):
        if log:
            log(msg)

    remoto = corrida_remota()
    ref = remoto['reference_time']
    local = manifest()
    n_objetivo = _horas_objetivo(remoto, horas)
    if (not forzar and local and local.get('reference_time') == ref
            and int(local.get('horas') or 0) >= n_objetivo
            and not cobertura_incompleta(local)):
        decir(f'Ya está al día con la corrida {ref}.')
        return {'estado': 'al_dia', 'reference_time': ref}

    if sync_en_curso() and not _lock.locked():
        return {'estado': 'en_curso'}
    if not _lock.acquire(blocking=False):
        return {'estado': 'en_curso'}
    if not _tomar_lock_archivo():
        _lock.release()
        return {'estado': 'en_curso'}
    _sincronizando = True
    comienzo = time.time()
    cache_raiz = None
    try:
        raiz = _raiz_corrida(ref)
        bbox = _bbox_de_wkt(remoto.get('crs_wkt', ''))
        valid = remoto.get('valid_times') or []
        n_horas = n_objetivo
        if n_horas < 1:
            raise RuntimeError('la corrida remota no trae horas')
        # Carpeta nueva: no se pisan los .npy que el servidor ya tiene mapeados.
        # La etiqueta de región evita reescribir América cuando el objetivo
        # pasa a ser el mundo.
        carpeta = f'{_slug(ref)}_{n_horas}h_{_id_region()}'
        destino = directorio() / carpeta
        destino.mkdir(parents=True, exist_ok=True)
        cache_raiz = Path(os.getenv('TEMP') or '/tmp') / (
            f'om_blockcache_{os.getpid()}_{int(time.time())}')
        hay_corrida_completa = bool(
            local and set(VARIABLES) <= set(local.get('variables') or []))
        decir(f'Corrida {ref}: bajando {len(VARIABLES)} variables'
              f' × {n_horas} h a {destino}')

        geo = None
        man = None
        for variable in VARIABLES:
            t0 = time.time()
            lector = _abrir_om(raiz + f'{variable}.om', cache_raiz / variable)
            try:
                ny, nx = lector.shape[0], lector.shape[1]
                if bbox:
                    lat_min, lon_min, lat_max, lon_max = bbox
                else:
                    lat_min, lon_min, lat_max, lon_max = -90.0, -180.0, 90.0, 179.75
                paso_lat = (lat_max - lat_min) / (ny - 1)
                paso_lon = (lon_max - lon_min) / (nx - 1)

                y0 = max(0, int(math.floor((REGION['sur'] - lat_min) / paso_lat)))
                y1 = min(ny, int(math.ceil((REGION['norte'] - lat_min) / paso_lat)) + 1)
                x0 = max(0, int(math.floor((REGION['oeste'] - lon_min) / paso_lon)))
                x1 = min(nx, int(math.ceil((REGION['este'] - lon_min) / paso_lon)) + 1)

                nt = min(n_horas, lector.shape[2])
            finally:
                lector.close()

            trozos = []
            for t0 in range(0, nt, PASO_HORAS_LECTURA):
                t1 = min(nt, t0 + PASO_HORAS_LECTURA)
                trozos.append(_leer_ventana(
                    raiz + f'{variable}.om', cache_raiz / f'{variable}_datos',
                    y0, y1, x0, x1, t0, t1))
            datos = np.concatenate(trozos, axis=2)

            # Se guarda como [hora][fila][columna]: el mapa pinta una hora por
            # vez, y así esa hora es un bloque contiguo en disco. Con la hora
            # como última dimensión, leer una sola hora obliga a recorrer el
            # archivo entero.
            datos = np.ascontiguousarray(datos.transpose(2, 0, 1))
            _guardar_npy(destino / f'{variable}.npy', datos)
            geo = {
                'lat0': round(lat_min + y0 * paso_lat, 6),
                'lon0': round(lon_min + x0 * paso_lon, 6),
                'paso_lat': round(paso_lat, 6),
                'paso_lon': round(paso_lon, 6),
                'horas': int(datos.shape[0]),
                'filas': int(datos.shape[1]),
                'cols': int(datos.shape[2]),
            }
            decir(f'  {variable:24s} {time.time() - t0:6.1f}s'
                  f' {datos.shape} {datos.nbytes / 1e6:.1f} MB')
            listas = [
                v for v in VARIABLES
                if (destino / f'{v}.npy').exists()
            ]
            man = {
                'version': VERSION,
                'modelo': MODELO,
                'fuente': FUENTE,
                'reference_time': ref,
                'carpeta': carpeta,
                'valid_times': [_iso_utc(t) for t in valid[:geo['horas']]],
                'variables': listas,
                'creado': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                **geo,
            }
            # Si ya hay una corrida usable, el mapa la sigue sirviendo hasta
            # que esta bajada esté entera. Si no, se publica variable a variable.
            if not hay_corrida_completa:
                _escribir_manifest(man)
        if man is None:
            raise RuntimeError('no se pudo guardar ninguna variable')
        _escribir_manifest(man)
        _limpiar_viejas(carpeta)
        shutil.rmtree(cache_raiz, ignore_errors=True)

        decir(f'Listo en {time.time() - comienzo:.0f}s'
              f' ({geo["filas"]}×{geo["cols"]} celdas, {geo["horas"]} h)')
        return {'estado': 'ok', 'reference_time': ref,
                'segundos': round(time.time() - comienzo, 1), **geo}
    finally:
        if cache_raiz is not None:
            shutil.rmtree(cache_raiz, ignore_errors=True)
        _soltar_lock_archivo()
        _sincronizando = False
        _lock.release()


def _limpiar_viejas(actual: str) -> None:
    raiz = directorio()
    try:
        hijos = list(raiz.iterdir())
    except OSError:
        return
    for hijo in hijos:
        if hijo.is_dir() and hijo.name != actual:
            shutil.rmtree(hijo, ignore_errors=True)


def _iso_utc(t: str) -> str:
    """Normaliza '2026-09-12T12:00Z' a '2026-09-12T12:00Z'."""
    t = t.replace('Z', '')
    if len(t) == 13:
        t += ':00'
    return t + 'Z'


def sincronizar_en_hilo() -> bool:
    """Arranca la sincronización de fondo si no hay otra corriendo."""
    if sync_en_curso():
        return False
    hilo = threading.Thread(target=_sincronizar_silencioso,
                            name='grilla-modelo', daemon=True)
    hilo.start()
    return True


def _sincronizar_silencioso() -> None:
    import logging
    log = logging.getLogger(__name__)
    try:
        sincronizar(log=log.info)
    except Exception as e:
        log.warning(f'[grilla] sincronización falló: {e}')


# --------------------------------------------------------------------------
# Recorte para el mapa
# --------------------------------------------------------------------------

def region_disponible() -> dict:
    man = manifest()
    if not man:
        return dict(REGION)
    return {
        'sur': man['lat0'],
        'norte': round(man['lat0'] + (man['filas'] - 1) * man['paso_lat'], 4),
        'oeste': man['lon0'],
        'este': round(man['lon0'] + (man['cols'] - 1) * man['paso_lon'], 4),
    }


def _id_region() -> str:
    if (REGION['norte'] - REGION['sur'] >= 160
            and REGION['este'] - REGION['oeste'] >= 350):
        return 'mundo'
    return 'reg'


def viewport_cubierto(sur: float, norte: float, oeste: float,
                      este: float, holgura: float = 1.5) -> bool:
    """True si la corrida en disco cubre el recuadro que pide el mapa."""
    r = region_disponible()
    if not r:
        return False
    return (
        sur >= r['sur'] - holgura
        and norte <= r['norte'] + holgura
        and oeste >= r['oeste'] - holgura
        and este <= r['este'] + holgura
    )


def viewport_intersecta(sur: float, norte: float, oeste: float,
                        este: float) -> bool:
    """True si el pedido toca la ventana que ya tenemos en disco."""
    r = region_disponible()
    if not r:
        return False
    return not (
        norte < r['sur'] or sur > r['norte']
        or este < r['oeste'] or oeste > r['este']
    )


def cobertura_incompleta(man=None) -> bool:
    """True si lo guardado no cubre el recuadro objetivo (p. ej. solo América)."""
    man = man or manifest()
    if not man:
        return True
    r = {
        'sur': man['lat0'],
        'norte': man['lat0'] + (man['filas'] - 1) * man['paso_lat'],
        'oeste': man['lon0'],
        'este': man['lon0'] + (man['cols'] - 1) * man['paso_lon'],
    }
    eps = max(float(man.get('paso_lat') or 0.2), 0.2)
    return (
        r['sur'] > REGION['sur'] + eps
        or r['norte'] < REGION['norte'] - eps
        or r['oeste'] > REGION['oeste'] + eps
        or r['este'] < REGION['este'] - eps
    )


def _horas_objetivo(remoto: dict, horas: int = HORAS) -> int:
    """Cuántas horas hay que guardar: todas las del modelo, o el recorte pedido."""
    valid = remoto.get('valid_times') or []
    if horas and horas > 0:
        return min(horas, len(valid)) if valid else horas
    return len(valid)


def corrida_vencida(man=None) -> bool:
    """True si la última hora guardada ya quedó en el pasado."""
    from datetime import datetime, timezone
    man = man or manifest()
    if not man or not man.get('valid_times'):
        return True
    ultima = _iso_utc(man['valid_times'][-1])
    t = datetime.fromisoformat(ultima.replace('Z', '+00:00'))
    return t < datetime.now(timezone.utc)


def necesita_actualizacion(chequear_remoto: bool = False) -> bool:
    """Hay que bajar una corrida nueva: no hay datos, se venció, o DWD publicó otra."""
    if sync_en_curso():
        return False
    local = manifest()
    if not local or corrida_vencida(local) or cobertura_incompleta(local):
        return True
    if not chequear_remoto:
        return False
    try:
        remoto = corrida_remota(timeout=12)
    except Exception:
        return False
    if remoto.get('reference_time') != local.get('reference_time'):
        return True
    return int(local.get('horas') or 0) < _horas_objetivo(remoto)


def asegurar_actualizada(chequear_remoto: bool = False) -> bool:
    """Dispara la bajada en segundo plano si hace falta. No bloquea."""
    if not necesita_actualizacion(chequear_remoto=chequear_remoto):
        return False
    return sincronizar_en_hilo()


def estado() -> dict:
    man = manifest()
    return {
        'listo': bool(man),
        'sincronizando': sync_en_curso(),
        'reference_time': man.get('reference_time') if man else None,
        'horas': man.get('horas') if man else None,
        'region': region_disponible(),
        'objetivo': dict(REGION),
        'cobertura_incompleta': cobertura_incompleta(man) if man else True,
        'modelo': MODELO,
        'fuente': FUENTE,
    }


def recortar(capa: str, hora: int, sur: float, norte: float,
             oeste: float, este: float, max_lado: int = MAX_LADO) -> dict:
    """Bloque de horas de una capa, recortado al viewport.

    Devuelve el bloque que contiene `hora`. Cada elemento de `valores` es una
    hora, plana en orden fila-mayor empezando por el NORTE, que es como las
    espera un canvas o una imagen.
    """
    man = manifest()
    if not man:
        raise SinCorrida('todavía no hay ninguna corrida sincronizada')
    meta = CAPAS.get(capa)
    if meta is None:
        raise ValueError(f'capa desconocida: {capa}')
    faltan = [v for v in meta['variables']
              if v not in (man.get('variables') or [])]
    if faltan:
        raise CapaIncompleta(capa)

    lat0, lon0 = man['lat0'], man['lon0']
    paso_lat, paso_lon = man['paso_lat'], man['paso_lon']
    filas, cols, n_horas = man['filas'], man['cols'], man['horas']

    hora = max(0, min(int(hora), n_horas - 1))

    # Un poco de margen para que la imagen no corte justo en el borde visible.
    margen_lat = max(paso_lat, (norte - sur) * 0.08)
    margen_lon = max(paso_lon, (este - oeste) * 0.08)
    y0 = int(math.floor((sur - margen_lat - lat0) / paso_lat))
    y1 = int(math.ceil((norte + margen_lat - lat0) / paso_lat)) + 1
    x0 = int(math.floor((oeste - margen_lon - lon0) / paso_lon))
    x1 = int(math.ceil((este + margen_lon - lon0) / paso_lon)) + 1
    y0, y1 = max(0, y0), min(filas, y1)
    x0, x1 = max(0, x0), min(cols, x1)
    if y1 - y0 < 2 or x1 - x0 < 2:
        raise FueraDeRegion('el viewport cae fuera de la región sincronizada')

    salto = max(1, math.ceil(max(y1 - y0, x1 - x0) / max_lado))
    n_filas = len(range(y0, y1, salto))
    n_cols = len(range(x0, x1, salto))

    # Cuantas más celdas tenga la grilla, menos horas entran por respuesta.
    por_bloque = max(1, min(HORAS_POR_BLOQUE, MAX_VALORES // (n_filas * n_cols)))
    desde = (hora // por_bloque) * por_bloque
    hasta = min(n_horas, desde + por_bloque)

    def leer(variable):
        return np.asarray(
            _array(man, variable)[desde:hasta, y0:y1:salto, x0:x1:salto],
            dtype=np.float32)

    if capa == 'viento':
        u = leer('wind_u_component_10m')
        v = leer('wind_v_component_10m')
        cubo = np.hypot(u, v) * 3.6
    else:
        cubo = leer(meta['variables'][0])

    # De sur-a-norte a norte-a-sur: el orden natural de una imagen.
    cubo = cubo[:, ::-1, :]
    finitos = cubo[np.isfinite(cubo)]

    dec = meta['decimales']
    # Con dec=0 hay que pasar a int: round(1013.4, 0) serializa "1013.0" y el
    # decimal de más se paga en cada celda de cada hora.
    redondear = (lambda v: round(float(v), dec)) if dec else (
        lambda v: int(round(float(v))))
    valores = [
        [None if not math.isfinite(v) else redondear(v) for v in plano.ravel()]
        for plano in cubo
    ]

    return {
        'ok': True,
        'capa': capa,
        'nombre': meta['nombre'],
        'unidad': meta['unidad'],
        'decimales': dec,
        'modelo': MODELO,
        'fuente': man.get('fuente', FUENTE),
        'reference_time': man['reference_time'],
        'times': man['valid_times'],
        'hora': hora,
        'hora_desde': int(desde),
        'horas_en_bloque': int(hasta - desde),
        'filas': int(n_filas),
        'cols': int(n_cols),
        # bbox de los centros de celda, en el orden que espera MapLibre.
        'bbox': [
            round(lon0 + x0 * paso_lon, 4),
            round(lat0 + y0 * paso_lat, 4),
            round(lon0 + (x0 + (n_cols - 1) * salto) * paso_lon, 4),
            round(lat0 + (y0 + (n_filas - 1) * salto) * paso_lat, 4),
        ],
        'paso_lat': round(paso_lat * salto, 5),
        'paso_lon': round(paso_lon * salto, 5),
        'res_km': round(paso_lat * salto * 111.32, 1),
        'min': round(float(finitos.min()), dec) if finitos.size else None,
        'max': round(float(finitos.max()), dec) if finitos.size else None,
        'valores': valores,
        'cache_s': CACHE_TTL,
    }
