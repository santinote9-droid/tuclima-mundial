from django.shortcuts import render, redirect
import requests
import json
import time
import threading
import hmac
import hashlib
import feedparser
import urllib3
import paypalrestsdk
import mercadopago
from cachetools import TTLCache, cached
from django.core.cache import cache as django_cache
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, User
from django.utils import timezone
from datetime import datetime, timedelta
import uuid
from .models import PerfilUsuario, DatoSectorial, UbicacionGuardada, ReporteProgramado, ApiKeyPersonal
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Count
from django.core.mail import send_mail
from django.conf import settings
from django import forms
import pandas as pd
import io
import openai
import os
import logging
from dotenv import load_dotenv
import urllib.request
import xml.etree.ElementTree as ET


# Cargar variables de entorno
load_dotenv()
logger = logging.getLogger(__name__)


# ============================================================
# CACHÉ DE API OPEN-METEO — persistente en base de datos PostgreSQL
# Usa django.core.cache (configurado en settings.py como DatabaseCache).
# Sobrevive reinicios del servidor: 100 usuarios = 1 sola llamada a la API.
# Respuestas válidas: 30 minutos (definido en settings.CACHES).
# Respuestas de error (rate-limit, etc): 60 segundos.
# ============================================================
_METEO_HEADERS = {
    'User-Agent': 'TuClimaMundial/1.0 (proyectoclima@gmail.com)'
}


def _get_meteo(url: str, timeout: int = 6) -> dict:
    """
    GET a Open-Meteo con caché persistente en base de datos.
    - Respuestas válidas: cacheadas 30 min (settings.CACHES TIMEOUT).
    - Errores de rate-limit: cacheados 60 s para no seguir gastando cuota.
    - 100 usuarios pidiendo el mismo lugar = 1 sola llamada a la API.
    """
    cache_key = 'meteo_' + hashlib.md5(url.encode()).hexdigest()
    cached_data = django_cache.get(cache_key)
    if cached_data is not None:
        return cached_data

    data = requests.get(url, timeout=timeout, headers=_METEO_HEADERS).json()

    if not data.get('error') and ('current' in data or 'hourly' in data):
        # Respuesta válida: guardar 30 minutos (usa el TIMEOUT de settings)
        django_cache.set(cache_key, data)
    else:
        # Error de API (rate-limit, fuera de rango, etc): guardar solo 60 segundos
        django_cache.set(cache_key, data, timeout=60)

    return data


# ============================================================
# FORMULARIO DE REGISTRO CON EMAIL REQUERIDO
# ============================================================
class RegistroConEmailForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        label='Correo electrónico',
        widget=forms.EmailInput(attrs={'placeholder': 'tu@email.com'})
    )

    class Meta(UserCreationForm.Meta):
        fields = ('username', 'email', 'password1', 'password2')


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def pedir_datos_seguro(url):
    session = requests.Session()
    
    # 1. Aumentamos la insistencia a 5 intentos
    retries = Retry(total=5, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    
    # 2. HEADER CLAVE: Nos identificamos para que Open-Meteo no nos corte
    headers = {
        'User-Agent': 'ClimaApp-StudentProject/1.0 (santino@example.com)'
    }

    try:
        # 3. EL TRUCO FINAL: verify=False saltará el error de SSL de Windows
        return session.get(url, headers=headers, timeout=20, verify=False)
    except Exception as e:
        print(f"Error de Conexión Crítico: {e}")
        raise e
    
# --- FUNCIONES AUXILIARES (Iconos, Fondos, Noticias, Papers) ---
# (Se mantienen igual que antes, las incluyo para que el código esté completo)

def obtener_icono_url(codigo, es_dia=1):
    base_url = "https://bmcdn.nl/assets/weather-icons/v3.0/fill/svg/"
    suffix = ".svg"
    if codigo == 0: return f"{base_url}{'clear-day' if es_dia else 'clear-night'}{suffix}"
    elif codigo in [1, 2, 3]: return f"{base_url}{'partly-cloudy-day' if es_dia else 'partly-cloudy-night'}{suffix}"
    elif codigo in [45, 48]: return f"{base_url}{'fog' if es_dia else 'fog'}{suffix}"
    elif codigo in [51, 53, 55, 61, 63, 65, 80, 81, 82]: return f"{base_url}{'rain' if es_dia else 'rain'}{suffix}"
    elif codigo in [71, 73, 75, 77, 85, 86]: return f"{base_url}{'snow' if es_dia else 'snow'}{suffix}"
    elif codigo >= 95: return f"{base_url}{'thunderstorms' if es_dia else 'thunderstorms'}{suffix}"
    else: return f"{base_url}not-available{suffix}"

def descifrar_desc(codigo):
    if codigo == 0: return 'Despejado'
    elif codigo in [1, 2, 3]: return 'Nublado'
    elif codigo in [45, 48]: return 'Niebla'
    elif codigo in [51, 53, 55, 61, 63, 65, 80, 81, 82]: return 'Lluvia'
    elif codigo in [71, 73, 75, 77, 85, 86]: return 'Nieve'
    elif codigo >= 95: return 'Tormenta'
    else: return 'Variable'

def obtener_fondo(codigo, es_dia):
    ruta = "img/"
    if es_dia == 0:
        if codigo == 0: return f"{ruta}noche_despejada.jpg"
        elif codigo in [1, 2, 3]: return f"{ruta}noche_nublada.jpg"
        elif codigo >= 95: return f"{ruta}tormenta_electrica.jpg"
        elif codigo in [51, 53, 55, 61, 63, 65, 80, 81, 82]: return f"{ruta}lluvia.jpg"
        elif codigo in [71, 73, 75, 77, 85, 86]: return f"{ruta}nieve.jpg"
        elif codigo in [45, 48]: return f"{ruta}niebla.jpg"
        else: return f"{ruta}noche_despejada.jpg"
    if codigo == 0: return f"{ruta}dia_radiante.jpg"
    elif codigo in [1, 2, 3]: return f"{ruta}dia_nublado.jpg"
    elif codigo >= 95: return f"{ruta}tormenta_electrica.jpg"
    elif codigo in [45, 48]: return f"{ruta}niebla.jpg"
    elif codigo in [51, 53, 55, 61, 63, 65, 80, 81, 82]: return f"{ruta}lluvia.jpg"
    elif codigo in [71, 73, 75, 77, 85, 86]: return f"{ruta}nieve.jpg"
    else: return f"{ruta}dia_radiante.jpg"

def analizar_detalles(codigo, uv_index, visibilidad):
    nube = "Sin Nubes"
    # Lógica de nubes
    if codigo == 0: nube = "Cielos Claros"
    elif codigo == 1: nube = "Cumulus (Bajas)"
    elif codigo == 2: nube = "Altocumulus (Medias)"
    elif codigo == 3: nube = "Stratus (Cielo Cubierto)"
    elif codigo in [45, 48]: nube = "Stratus (Niebla Baja)"
    elif codigo in [51, 53, 55, 61, 63, 65, 80, 81, 82]: nube = "Nimbostratus (Lluvia)"
    elif codigo >= 95: nube = "Cumulonimbus (Tormenta)"

    # Base de iconos
    base_url = "https://bmcdn.nl/assets/weather-icons/v3.0/fill/svg/"
    alerta = "Disfruta el día"
    icono_alerta = f"{base_url}clear-day.svg"
    
    # Lógica de Alertas (PRIORIDAD: Tormenta > UV > Niebla > Lluvia)
    if codigo >= 95:
        alerta = "¡Tormenta Eléctrica! Busca refugio."
        icono_alerta = f"{base_url}thunderstorms.svg"
    elif uv_index > 7:
        alerta = "Radiación Extrema. Usa protector solar."
        icono_alerta = f"{base_url}thermometer-warmer.svg"
    elif visibilidad < 1000:
        alerta = "Niebla densa. Conduce con precaución."
        icono_alerta = f"{base_url}fog.svg"
    elif codigo in [51, 61, 80, 53, 55, 63, 65, 81, 82]: # (Agregué variantes de lluvia para seguridad)
        alerta = "Lleva paraguas o impermeable."
        icono_alerta = f"{base_url}rain.svg"
        
    return nube, alerta, icono_alerta

def obtener_noticias_reales():
    rss_url = "https://news.google.com/rss/search?q=clima+argentina+campo+meteorologia&hl=es-419&gl=AR&ceid=AR:es-419"
    try:
        feed = feedparser.parse(rss_url)
        noticias = []
        for entry in feed.entries[:3]:
            categoria = "Actualidad 📰"
            imagen = "https://images.unsplash.com/photo-1590055531615-f16d36ffe8ec?w=500&q=60"
            titulo_lower = entry.title.lower()
            if "alerta" in titulo_lower or "tormenta" in titulo_lower:
                categoria = "Alerta ⚠️"
                imagen = "https://images.unsplash.com/photo-1527482797697-8795b05a13fe?w=500&q=60"
            elif "campo" in titulo_lower or "agro" in titulo_lower:
                categoria = "Agro 🚜"
                imagen = "https://images.unsplash.com/photo-1625246333195-58f21a4061a9?w=500&q=60"
            elif "calor" in titulo_lower:
                categoria = "Temperaturas 🌡️"
                imagen = "https://images.unsplash.com/photo-1504370805625-d32c54b16100?w=500&q=60"
            elif "lluvia" in titulo_lower:
                categoria = "Lluvias 🌧️"
                imagen = "https://images.unsplash.com/photo-1515694346937-94d85e41e6f0?w=500&q=60"

            noticias.append({'titulo': entry.title,'link': entry.link,'resumen': entry.published[:16],'categoria': categoria,'imagen': imagen})
        return noticias
    except:
        return [{'titulo': 'Sin conexión', 'categoria': 'Error', 'imagen': '', 'resumen': 'Revise internet', 'link': '#'}]


def obtener_papers_cientificos():
    import logging
    import time
    import random
    
    url_arxiv = "https://export.arxiv.org/api/query?search_query=cat:physics.ao-ph+OR+cat:physics.geo-ph&start=0&max_results=6&sortBy=submittedDate&sortOrder=descending"
    
    # Papers de respaldo si falla ArXiv
    papers_respaldo = [
        {
            'titulo': 'Climate Change Impact on Extreme Weather Events',
            'autor': 'IPCC Research',
            'resumen': 'Comprehensive analysis of climate change effects on extreme weather patterns across different geographical regions...',
            'link': 'https://arxiv.org/abs/2024.01001v1',
            'fecha': '2024-02-12'
        },
        {
            'titulo': 'Machine Learning Approaches for Weather Prediction',
            'autor': 'Climate AI Lab',
            'resumen': 'Novel machine learning techniques applied to meteorological forecasting with improved accuracy metrics...',
            'link': 'https://arxiv.org/abs/2024.01002v1',
            'fecha': '2024-02-11'
        },
        {
            'titulo': 'Atmospheric Dynamics and Climate Variability',
            'autor': 'Weather Research Institute',
            'resumen': 'Investigation of atmospheric circulation patterns and their relationship with climate variability indices...',
            'link': 'https://arxiv.org/abs/2024.01003v1',
            'fecha': '2024-02-10'
        }
    ]
    
    try:
        import feedparser
        feed = feedparser.parse(url_arxiv)
        
        if hasattr(feed, 'status') and feed.status == 429:
            logging.warning("ArXiv rate limit exceeded, using fallback papers")
            return {'error': None, 'papers': papers_respaldo}
        
        if hasattr(feed, 'status') and feed.status != 200:
            logging.error(f"arXiv API status: {feed.status}")
            return {'error': None, 'papers': papers_respaldo}
            
        if not feed.entries:
            logging.error("arXiv API: No entries found, using fallback")
            return {'error': None, 'papers': papers_respaldo}
            
        papers = []
        for entry in feed.entries[:6]:  # Limitar a máximo 6
            papers.append({
                'titulo': entry.title.strip(),
                'autor': entry.authors[0].name if entry.authors else "Autor desconocido",
                'resumen': entry.summary[:150].strip() + "...",
                'link': entry.link,
                'fecha': entry.published[:10]
            })
        return {'error': None, 'papers': papers}
    except Exception as e:
        logging.exception("Error al obtener papers de arXiv, usando fallback")
        return {'error': None, 'papers': papers_respaldo}

# --- API para frontend: /api/papers/ ---
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def api_papers(request):
    if request.method == 'GET':
        resultado = obtener_papers_cientificos()
        return JsonResponse(resultado)
    return JsonResponse({'error': 'Método no permitido'}, status=405)

# --- CORRECCIÓN DE UBICACIÓN "CENTRO" ---
# --- FUNCIÓN GPS CON FILTRO ANTI-"CENTRO" ---
def obtener_barrio_exacto(lat, lon):
    """
    Intenta obtener el barrio o localidad más específico posible.
    """
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
        # EL USER-AGENT ES OBLIGATORIO PARA QUE NO TE BLOQUEEN
        headers = {'User-Agent': 'MiClimaApp/1.0'}
        
        response = requests.get(url, headers=headers, timeout=5).json()
        
        if 'address' in response:
            ad = response['address']
            # Orden de prioridad ampliado para cubrir GBA y otras regiones
            nombre = (
                ad.get('neighbourhood') or
                ad.get('quarter') or
                ad.get('suburb') or
                ad.get('village') or
                ad.get('city_district') or
                ad.get('town') or
                ad.get('municipality') or
                ad.get('city') or
                ad.get('county') or
                ad.get('state_district') or
                ad.get('state')
            )
            pais = ad.get('country', '')
            return nombre, pais
            
    except Exception as e:
        print(f"Fallo Nominatim: {e}")
        return None, None
    return None, None

# --- VISTA HOME (PÚBLICA) ---
def home(request):
    # Configuración Default - Sin ubicación predeterminada para carga instantánea
    lat = 0.0
    lon = 0.0
    nombre_ciudad = "Detectando ubicación..."
    pais = ""
    opciones_ciudades = None
    mensaje_error = None
    
    contexto = {
        'temp': 0, 'sensacion': 0, 'humedad': 0, 'viento': 0, 'presion': 0, 
        'visibilidad': 10, 'uv_index': 0, 'lluvia_hoy': 0,
        'tira_horas': [], 'datos_json': '{}', 'horas_grafico': [], 'temps_grafico': [],
        'pronostico': [], 'noticias': [], 'papers': [],
        'hora_local': datetime.now(), 'delta_temp': 0,
        'icono': 'https://bmcdn.nl/assets/weather-icons/v3.0/fill/svg/not-available.svg',
        'fondo': 'img/dia_radiante.jpg',
        'descripcion': 'Cargando...', 'tipo_nube': '', 'alerta_texto': '',
        'alerta_color': '#a4b0be', 'alerta_tipo': 'normal',
        'sunrise': '--:--', 'sunset': '--:--'
    }

    # --- GEOLOCALIZACIÓN ---
    lat_gps = request.GET.get('lat')
    lon_gps = request.GET.get('lon')
    busqueda = request.GET.get('ciudad')

    try:
        # GPS
        if lat_gps and lon_gps and not busqueda:
            lat = float(str(lat_gps).replace(',', '.').strip())
            lon = float(str(lon_gps).replace(',', '.').strip())
            try:
                barrio, pais_det = obtener_barrio_exacto(lat, lon)
                if barrio:
                    nombre_ciudad = barrio
                    pais = pais_det
                # Si Nominatim no devuelve nada útil, quedamos con string genérico
                # (se sobreescribe luego con el timezone de Open-Meteo si está disponible)
            except: pass

        # Buscador
        elif busqueda:
            q_ciudad = busqueda
            q_pais = None
            if ',' in busqueda:
                partes = busqueda.split(',')
                q_ciudad = partes[0].strip()
                q_pais = partes[1].strip().lower()

            url_s = f"https://geocoding-api.open-meteo.com/v1/search?name={q_ciudad}&count=10&language=es&format=json"
            res_s = requests.get(url_s, timeout=2).json()
            if 'results' in res_s and res_s['results']:
                resultados = res_s['results']
                sel = resultados[0]
                if q_pais:
                    for r in resultados:
                        if q_pais in r.get('country', '').lower(): sel = r; break
                lat = sel['latitude']; lon = sel['longitude']
                nombre_ciudad = sel['name']; pais = sel.get('country', '')
            else: mensaje_error = f"No encontramos '{q_ciudad}'."
    except: pass

    # --- CLIMA ---
    try:
        # Solo obtener datos del clima si tenemos coordenadas válidas
        if lat != 0.0 and lon != 0.0:
            url_clima = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,weather_code,wind_speed_10m,surface_pressure,visibility&hourly=temperature_2m,weather_code,precipitation_probability,is_day&daily=weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset,uv_index_max&timezone=auto"
            
            response = _get_meteo(url_clima, timeout=8)
            actual = response['current']
            hourly = response['hourly']
            daily = response['daily']

            # Variables Críticas
            code = actual['weather_code']
            uv = daily['uv_index_max'][0] or 0  # puede ser None en algunas regiones/horarios
            vis_metros = actual['visibility'] or 10000
            vis_km = round(vis_metros / 1000, 1)
            
            # --- AQUÍ USAMOS TU FUNCIÓN Y TU LÓGICA ---
            nube_txt, alerta_txt, icono_alerta = analizar_detalles(code, uv, vis_metros)
            
            contexto['tipo_nube'] = nube_txt
            contexto['alerta_texto'] = alerta_txt
            
            # DETERMINAMOS EL COLOR SEGÚN LA MISMA LÓGICA DE TU FUNCIÓN
            # Así aseguramos que si sale UV extremo, el color sea ROJO y no verde.
            alerta_color = "#2ed573" # Verde por defecto (Disfruta el día)
            alerta_tipo = "normal"

            if code >= 95: # Tormenta
                alerta_color = "#ff4757" # Rojo
                alerta_tipo = "tormenta"
            elif uv > 7: # UV Extremo
                alerta_color = "#ff4757" # Rojo
                alerta_tipo = "calor"
            elif vis_metros < 1000: # Niebla
                alerta_color = "#a4b0be" # Gris
                alerta_tipo = "niebla"
            elif code in [51, 61, 80, 53, 55, 63, 65, 81, 82]: # Lluvia
                alerta_color = "#5352ed" # Azul
                alerta_tipo = "lluvia"

            contexto['alerta_color'] = alerta_color
            contexto['alerta_tipo'] = alerta_tipo

            # Resto de variables
            contexto['temp'] = actual['temperature_2m']
            contexto['sensacion'] = actual['apparent_temperature']
            contexto['humedad'] = actual['relative_humidity_2m']
            contexto['viento'] = actual['wind_speed_10m']
            contexto['presion'] = actual['surface_pressure']
            contexto['visibilidad'] = vis_km
            contexto['uv_index'] = uv
            contexto['lluvia_hoy'] = actual['precipitation']
            
            contexto['icono'] = obtener_icono_url(code, actual['is_day'])
            contexto['fondo'] = obtener_fondo(code, actual['is_day'])
            contexto['descripcion'] = descifrar_desc(code)

            # Si Nominatim no resolvió un nombre, usamos el timezone de Open-Meteo
            # Ej: "America/Argentina/Buenos_Aires" → "Buenos Aires"
            if nombre_ciudad in ('Detectando ubicación...', 'Ubicación Exacta', 'Ubicación GPS', ''):
                tz = response.get('timezone', '')
                if tz and '/' in tz:
                    nombre_ciudad = tz.split('/')[-1].replace('_', ' ')

            # Hora Local
            offset = response['utc_offset_seconds']
            now_utc = datetime.utcnow()
            hora_local_dt = now_utc + timedelta(seconds=offset)
            contexto['hora_local'] = hora_local_dt
            
            fecha_hoy = hora_local_dt.strftime('%Y-%m-%d')
            hora_key = hora_local_dt.strftime('%H:00')

            contexto['sunrise'] = daily['sunrise'][0].split('T')[1]
            contexto['sunset'] = daily['sunset'][0].split('T')[1]

            # Carrusel y Gráfico
            datos_por_dia = {}
            for i in range(len(hourly['time'])):
                dt_obj = datetime.strptime(hourly['time'][i], '%Y-%m-%dT%H:%M')
                f_clave = dt_obj.strftime('%Y-%m-%d')
                if f_clave not in datos_por_dia: datos_por_dia[f_clave] = []
                es_act = (f_clave == fecha_hoy and dt_obj.strftime('%H:%M') == hora_key)
                item = {'tipo': 'normal', 'hora': dt_obj.strftime('%H:%M'), 'orden': dt_obj.timestamp(), 'temp': hourly['temperature_2m'][i], 'icono': obtener_icono_url(hourly['weather_code'][i], hourly['is_day'][i]), 'lluvia': hourly['precipitation_probability'][i], 'es_actual': es_act}
                datos_por_dia[f_clave].append(item)

            for i in range(len(daily['time'])):
                f_clave = daily['time'][i]
                if f_clave in datos_por_dia:
                    if daily['sunrise'][i]:
                        sr = datetime.strptime(daily['sunrise'][i], '%Y-%m-%dT%H:%M')
                        datos_por_dia[f_clave].append({'tipo': 'evento', 'hora': sr.strftime('%H:%M'), 'orden': sr.timestamp(), 'evento_titulo': 'Amanecer', 'icono': 'https://bmcdn.nl/assets/weather-icons/v3.0/fill/svg/sunrise.svg'})
                    if daily['sunset'][i]:
                        ss = datetime.strptime(daily['sunset'][i], '%Y-%m-%dT%H:%M')
                        datos_por_dia[f_clave].append({'tipo': 'evento', 'hora': ss.strftime('%H:%M'), 'orden': ss.timestamp(), 'evento_titulo': 'Atardecer', 'icono': 'https://bmcdn.nl/assets/weather-icons/v3.0/fill/svg/sunset.svg'})
                    datos_por_dia[f_clave].sort(key=lambda x: x['orden'])

            tira_hoy = datos_por_dia.get(fecha_hoy, [])
            contexto['tira_horas'] = tira_hoy
            contexto['datos_json'] = json.dumps(datos_por_dia)
            contexto['horas_grafico'] = [h['hora'] for h in tira_hoy if h['tipo'] == 'normal']
            contexto['temps_grafico'] = [h['temp'] for h in tira_hoy if h['tipo'] == 'normal']

            # Pronóstico
            lista_pronostico = []
            dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            for i in range(6):
                dt = datetime.strptime(daily['time'][i], '%Y-%m-%d')
                nom = "HOY" if i == 0 else dias[dt.weekday()]
                lista_pronostico.append({
                    'nombre_dia': nom, 'fecha_corta': dt.strftime('%d/%m'), 'fecha_full': daily['time'][i],
                    'max': daily['temperature_2m_max'][i], 'min': daily['temperature_2m_min'][i],
                    'icono': obtener_icono_url(daily['weather_code'][i], 1), 'desc': descifrar_desc(daily['weather_code'][i])
                })
            contexto['pronostico'] = lista_pronostico
            
            # Carga opcional de noticias y papers - no bloquea la carga principal
            try:
                contexto['noticias'] = obtener_noticias_reales()
            except: 
                contexto['noticias'] = []
            
            try:
                contexto['papers'] = obtener_papers_cientificos()
            except:
                contexto['papers'] = []

            # Anomalía - Solo si tenemos ubicación válida (cacheada vía _get_meteo)
            try:
                fr = hora_local_dt.replace(year=2024).strftime('%Y-%m-%d')
                uh = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={fr}&end_date={fr}&hourly=temperature_2m&timezone=auto"
                rh = _get_meteo(uh, timeout=4)
                if 'hourly' in rh:
                    ta = rh['hourly']['temperature_2m'][hora_local_dt.hour]
                    if ta: contexto['delta_temp'] = round(actual['temperature_2m'] - ta, 1)
            except: pass

        else:
            # Si no tenemos coordenadas válidas, mostrar valores por defecto
            contexto.update({
                'temp': '--', 'sensacion': '--', 'humedad': '--', 'viento': '--', 'presion': '--', 
                'visibilidad': '--', 'uv_index': '--', 'lluvia_hoy': '--',
                'icono': 'https://bmcdn.nl/assets/weather-icons/v3.0/fill/svg/not-available.svg',
                'fondo': 'img/dia_radiante.jpg',
                'descripcion': 'Esperando geolocalización...',
                'tipo_nube': 'Detectando...',
                'alerta_texto': 'Obteniendo su ubicación',
                'alerta_color': '#a4b0be',
                'alerta_tipo': 'normal',
                'sunrise': '--:--',
                'sunset': '--:--',
                'noticias': [],
                'papers': [],
                'pronostico': [],
                'tira_horas': [],
                'datos_json': '{}',
                'horas_grafico': [],
                'temps_grafico': []
            })

    except Exception as e:
        import traceback
        print(f"[ERROR home] {e}")
        traceback.print_exc()

    contexto.update({'ciudad': nombre_ciudad, 'pais': pais, 'lat': lat, 'lon': lon, 'opciones_ciudades': opciones_ciudades, 'mensaje_error': mensaje_error})
    if request.user.is_authenticated:
        try:
            contexto['perfil'] = request.user.perfil
        except Exception:
            pass
    return render(request, 'home.html', contexto)  


# ==============================================================================
# API ENDPOINT para datos del clima en JSON (sin recarga de página)
# ==============================================================================
@require_http_methods(["GET"])
def clima_data_api(request):
    """
    Endpoint API que devuelve datos del clima en JSON
    Permite actualizar datos sin recargar la página completa
    """
    lat = request.GET.get('lat', '0.0')
    lon = request.GET.get('lon', '0.0')
    busqueda = request.GET.get('ciudad')
    
    try:
        lat = float(str(lat).replace(',', '.').strip())
        lon = float(str(lon).replace(',', '.').strip())
    except:
        return JsonResponse({'error': 'Coordenadas inválidas'}, status=400)
    
    nombre_ciudad = "Ubicación Desconocida"
    pais = ""
    
    try:
        # Búsqueda por ciudad
        if busqueda:
            q_ciudad = busqueda
            q_pais = None
            if ',' in busqueda:
                partes = busqueda.split(',')
                q_ciudad = partes[0].strip()
                q_pais = partes[1].strip().lower()

            url_s = f"https://geocoding-api.open-meteo.com/v1/search?name={q_ciudad}&count=10&language=es&format=json"
            res_s = requests.get(url_s, timeout=2).json()
            if 'results' in res_s and res_s['results']:
                resultados = res_s['results']
                sel = resultados[0]
                if q_pais:
                    for r in resultados:
                        if q_pais in r.get('country', '').lower(): sel = r; break
                lat = sel['latitude']; lon = sel['longitude']
                nombre_ciudad = sel['name']; pais = sel.get('country', '')
        
        # Obtener nombre de ubicación si solo hay GPS
        elif lat != 0.0 and lon != 0.0:
            try:
                barrio, pais_det = obtener_barrio_exacto(lat, lon)
                if barrio:
                    nombre_ciudad = barrio
                    pais = pais_det
                # Si no hay nombre, se sobreescribe con timezone más abajo
            except:
                pass
        
        # Obtener datos del clima
        url_clima = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,weather_code,wind_speed_10m,surface_pressure,visibility&hourly=temperature_2m,weather_code,precipitation_probability,is_day&daily=weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset,uv_index_max&timezone=auto"
        
        response = _get_meteo(url_clima, timeout=8)
        if 'current' not in response:
            motivo = response.get('reason', 'Servicio meteorológico no disponible temporalmente')
            return JsonResponse({'success': False, 'error': motivo}, status=503)
        actual = response['current']
        hourly = response['hourly']
        daily = response['daily']

        # Análisis de condiciones
        code = actual['weather_code']
        uv = daily['uv_index_max'][0] or 0  # puede ser None en algunas regiones/horarios
        vis_metros = actual['visibility'] or 10000
        vis_km = round(vis_metros / 1000, 1)
        
        nube_txt, alerta_txt, icono_alerta = analizar_detalles(code, uv, vis_metros)
        
        # Determinar color de alerta
        alerta_color = "#2ed573"
        alerta_tipo = "normal"
        if code >= 95:
            alerta_color = "#ff4757"
            alerta_tipo = "tormenta"
        elif uv > 7:
            alerta_color = "#ff4757"
            alerta_tipo = "calor"
        elif vis_metros < 1000:
            alerta_color = "#a4b0be"
            alerta_tipo = "niebla"
        elif code in [51, 61, 80, 53, 55, 63, 65, 81, 82]:
            alerta_color = "#5352ed"
            alerta_tipo = "lluvia"

        # Hora local
        offset = response['utc_offset_seconds']
        now_utc = datetime.utcnow()
        hora_local_dt = now_utc + timedelta(seconds=offset)
        fecha_hoy = hora_local_dt.strftime('%Y-%m-%d')
        hora_key = hora_local_dt.strftime('%H:00')

        # Carrusel horario
        datos_por_dia = {}
        for i in range(len(hourly['time'])):
            dt_obj = datetime.strptime(hourly['time'][i], '%Y-%m-%dT%H:%M')
            f_clave = dt_obj.strftime('%Y-%m-%d')
            if f_clave not in datos_por_dia:
                datos_por_dia[f_clave] = []
            es_act = (f_clave == fecha_hoy and dt_obj.strftime('%H:%M') == hora_key)
            item = {
                'tipo': 'normal',
                'hora': dt_obj.strftime('%H:%M'),
                'orden': dt_obj.timestamp(),
                'temp': hourly['temperature_2m'][i],
                'icono': obtener_icono_url(hourly['weather_code'][i], hourly['is_day'][i]),
                'lluvia': hourly['precipitation_probability'][i],
                'es_actual': es_act
            }
            datos_por_dia[f_clave].append(item)

        # Agregar amaneceres y atardeceres
        for i in range(len(daily['time'])):
            f_clave = daily['time'][i]
            if f_clave in datos_por_dia:
                if daily['sunrise'][i]:
                    sr = datetime.strptime(daily['sunrise'][i], '%Y-%m-%dT%H:%M')
                    datos_por_dia[f_clave].append({
                        'tipo': 'evento',
                        'hora': sr.strftime('%H:%M'),
                        'orden': sr.timestamp(),
                        'evento_titulo': 'Amanecer',
                        'icono': 'https://bmcdn.nl/assets/weather-icons/v3.0/fill/svg/sunrise.svg'
                    })
                if daily['sunset'][i]:
                    ss = datetime.strptime(daily['sunset'][i], '%Y-%m-%dT%H:%M')
                    datos_por_dia[f_clave].append({
                        'tipo': 'evento',
                        'hora': ss.strftime('%H:%M'),
                        'orden': ss.timestamp(),
                        'evento_titulo': 'Atardecer',
                        'icono': 'https://bmcdn.nl/assets/weather-icons/v3.0/fill/svg/sunset.svg'
                    })
                datos_por_dia[f_clave].sort(key=lambda x: x['orden'])

        tira_hoy = datos_por_dia.get(fecha_hoy, [])

        # Pronóstico
        lista_pronostico = []
        dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        for i in range(6):
            dt = datetime.strptime(daily['time'][i], '%Y-%m-%d')
            nom = "HOY" if i == 0 else dias[dt.weekday()]
            lista_pronostico.append({
                'nombre_dia': nom,
                'fecha_corta': dt.strftime('%d/%m'),
                'fecha_full': daily['time'][i],
                'max': daily['temperature_2m_max'][i],
                'min': daily['temperature_2m_min'][i],
                'icono': obtener_icono_url(daily['weather_code'][i], 1),
                'desc': descifrar_desc(daily['weather_code'][i])
            })

        # Anomalía de temperatura (cacheada vía _get_meteo)
        delta_temp = 0
        try:
            fr = hora_local_dt.replace(year=2024).strftime('%Y-%m-%d')
            uh = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={fr}&end_date={fr}&hourly=temperature_2m&timezone=auto"
            rh = _get_meteo(uh, timeout=4)
            if 'hourly' in rh:
                ta = rh['hourly']['temperature_2m'][hora_local_dt.hour]
                if ta:
                    delta_temp = round(actual['temperature_2m'] - ta, 1)
        except:
            pass

        # Fallback timezone si Nominatim no resolvió el nombre
        if nombre_ciudad in ('Ubicación Desconocida', 'Ubicación Exacta', 'Ubicación GPS', ''):
            tz = response.get('timezone', '')
            if tz and '/' in tz:
                nombre_ciudad = tz.split('/')[-1].replace('_', ' ')

        # Construir respuesta JSON
        data = {
            'success': True,
            'ciudad': nombre_ciudad,
            'pais': pais,
            'lat': lat,
            'lon': lon,
            'temp': actual['temperature_2m'],
            'sensacion': actual['apparent_temperature'],
            'humedad': actual['relative_humidity_2m'],
            'viento': actual['wind_speed_10m'],
            'presion': actual['surface_pressure'],
            'visibilidad': vis_km,
            'uv_index': uv,
            'lluvia_hoy': actual['precipitation'],
            'icono': obtener_icono_url(code, actual['is_day']),
            'fondo': obtener_fondo(code, actual['is_day']),
            'fondo_url': settings.STATIC_URL + obtener_fondo(code, actual['is_day']),
            'descripcion': descifrar_desc(code),
            'tipo_nube': nube_txt,
            'alerta_texto': alerta_txt,
            'alerta_color': alerta_color,
            'alerta_tipo': alerta_tipo,
            'sunrise': daily['sunrise'][0].split('T')[1] if daily['sunrise'][0] else '--:--',
            'sunset': daily['sunset'][0].split('T')[1] if daily['sunset'][0] else '--:--',
            'hora_local': hora_local_dt.strftime('%Y-%m-%d %H:%M:%S'),
            'delta_temp': delta_temp,
            'tira_horas': tira_hoy,
            'datos_json': datos_por_dia,
            'horas_grafico': [h['hora'] for h in tira_hoy if h['tipo'] == 'normal'],
            'temps_grafico': [h['temp'] for h in tira_hoy if h['tipo'] == 'normal'],
            'pronostico': lista_pronostico
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ==============================================================================
# 4. COMPARADOR DE MODELOS (RESTAUARADO TAMBIÉN)
# ==============================================================================








def pricing(request):
    from .models import COSTO_TOKENS
    context = {'planes_tokens': PLANES_TOKENS, 'costos': COSTO_TOKENS}
    if request.user.is_authenticated:
        try:
            perfil = request.user.perfil
            perfil._reset_diario_si_necesario()
            context.update({
                'tokens_disponibles': perfil.tokens_disponibles,
                'tokens_diarios_limite': perfil.tokens_diarios_limite,
                'plan_tokens_activo': bool(
                    perfil.tokens_diarios_limite
                    and perfil.fecha_vencimiento_tokens
                    and perfil.fecha_vencimiento_tokens > timezone.now()
                ),
            })
        except Exception:
            pass
    return render(request, 'pricing.html', context)


@login_required
def activar_suscripcion(request):
    # Vista legacy — no activa nada real. Redirige a pricing.
    return redirect('pricing')

def check_premium(user):
    return user.groups.filter(name='Premium').exists()

def tiene_acceso_pro(user):
    if not user.is_authenticated:
        return False
    try:
        # Verifica si es premium (si la fecha no venció)
        return user.perfilusuario.es_premium()
    except:
        return False




def agro(request):
    # 1. Seguridad y Suscripción
    if not request.user.is_authenticated:
        return redirect('login')

    if hasattr(request.user, 'perfil') and not request.user.perfil.suscripcion_activa:
        return redirect('pricing')

    # 1b. Control de acceso sectorial (plan Starter = 1 sector)
    if hasattr(request.user, 'perfil'):
        perfil = request.user.perfil
        if not perfil.tiene_acceso_sector('agro'):
            return render(request, 'sector_bloqueado.html', {
                'sector_bloqueado': 'Agro',
                'sector_actual': perfil.sector_elegido,
                'plan_nivel': perfil.plan_nivel,
            })
        # Si es Starter y aún no eligió sector, registrarlo
        if perfil.plan_nivel == 'starter' and not perfil.sector_elegido:
            perfil.sector_elegido = 'agro'
            perfil.save(update_fields=['sector_elegido'])

    # 2. Obtener Coordenadas (con valores por defecto seguros)
    try:
        lat = float(request.GET.get('lat', '-34.60').replace(',', '.'))
        lon = float(request.GET.get('lon', '-58.38').replace(',', '.'))
    except ValueError:
        lat, lon = -34.60, -58.38

    # 3. URL API (SOLICITUD DE DATOS "HARDCORE")
    # Agregamos: soil_temperature_6cm, soil_temperature_54cm, shortwave_radiation
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,relative_humidity_2m,is_day,precipitation,rain,weather_code,"
        "cloud_cover,pressure_msl,surface_pressure,wind_speed_10m,wind_direction_10m,"
        "soil_temperature_0cm,soil_temperature_6cm,soil_temperature_18cm,soil_temperature_54cm,"
        "soil_moisture_0_to_1cm,soil_moisture_3_to_9cm,soil_moisture_9_to_27cm,"
        "vapor_pressure_deficit,shortwave_radiation"  # <--- Datos Reales de Radiación
        "&hourly=temperature_2m,relative_humidity_2m,dew_point_2m,precipitation,"
        "precipitation_probability,weather_code,pressure_msl,wind_speed_10m,wind_direction_10m,"
        "vapor_pressure_deficit,et0_fao_evapotranspiration"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,"
        "precipitation_probability_max,et0_fao_evapotranspiration&forecast_days=14&timezone=auto"
    )

    contexto = {}

    try:
        data = _get_meteo(url)
        
        if 'error' in data: 
            raise Exception(f"API Error: {data.get('reason')}")

        # Bloques de datos
        curr = data.get('current', {})
        daily = data.get('daily', {})
        hourly = data.get('hourly', {})
        
        # Indice de hora actual para datos horarios
        idx_hora = datetime.now().hour

        # --- CÁLCULOS AGRONÓMICOS ---

        # 1. Delta T (Calidad de Pulverización)
        temp = curr.get('temperature_2m', 20)
        hum = curr.get('relative_humidity_2m', 50)
        # Fórmula aproximada de Delta T
        delta_t = round(temp - (temp * hum / 100) - 1.5, 1) # Ajuste simple
        # Nota: La formula exacta requiere bulbo humedo, esta es una aproximacion funcional.
        if delta_t < 0: delta_t = 0.5 
        
        cond_pulv = "ÓPTIMA"
        color_pulv = "#4ade80" # Verde
        if delta_t < 2: 
            cond_pulv = "RIESGO INV."; color_pulv = "#facc15" # Amarillo
        elif delta_t > 8 and delta_t <= 10: 
            cond_pulv = "MARGINAL"; color_pulv = "#facc15"
        elif delta_t > 10 or curr.get('wind_speed_10m', 0) > 15: 
            cond_pulv = "CRÍTICA"; color_pulv = "#ef4444" # Rojo

        # 2. GDD (Grados Día - Base 10 Maíz)
        gdd_acum = 0
        temps_max = daily.get('temperature_2m_max', [])
        temps_min = daily.get('temperature_2m_min', [])
        for i in range(min(len(temps_max), 7)): # Acumulado 7 días
            media = (temps_max[i] + temps_min[i]) / 2
            gdd_diario = media - 10 
            if gdd_diario < 0: gdd_diario = 0
            gdd_acum += gdd_diario

        # 3. Balance Hídrico (Lluvia vs ETo)
        lluvia_semana = sum(daily.get('precipitation_sum', [])[:7])
        eto_list = daily.get('et0_fao_evapotranspiration', [])
        # Rellenar con 0 si falta datos
        if not eto_list: eto_list = [0]*14
        
        evapo_semana = sum(eto_list[:7])
        balance_neto = lluvia_semana - evapo_semana

        # 4. Tabla de Balance Diario
        tabla_balance = []
        fechas_raw = daily.get('time', [])
        lluvias_diarias = daily.get('precipitation_sum', [])
        
        for i in range(min(len(fechas_raw), 14)):
            r = lluvias_diarias[i] if i < len(lluvias_diarias) else 0
            e = eto_list[i] if i < len(eto_list) else 0
            diff = round(r - e, 1)
            
            # Formato fecha "YYYY-MM-DD" -> "MM-DD"
            fecha_fmt = fechas_raw[i][5:] 
            
            tabla_balance.append({
                'fecha': fecha_fmt, 
                'lluvia': r, 
                'eto': e, 
                'diff': diff, 
                'color': '#ef4444' if diff < 0 else '#4ade80'
            })

        # 5. VPD (Déficit de Presión de Vapor)
        vpd_val = curr.get('vapor_pressure_deficit', 0)
        vpd_estado = "Normal"
        vpd_color = "#4ade80"
        if vpd_val > 1.6: 
            vpd_estado = "Estrés (Cierre)"; vpd_color = "#ef4444"
        elif vpd_val < 0.4: 
            vpd_estado = "Riesgo Fúngico"; vpd_color = "#facc15"

        # 6. Radiación Real
        watts_now = curr.get('shortwave_radiation', 0)
        rad_estado = "Baja"
        if watts_now > 800: rad_estado = "Máxima"
        elif watts_now > 300: rad_estado = "Media"
        
        # 7. Datos para Gráficos y Listas
        # Convertimos listas a JSON para pasarlas a JavaScript (Highcharts)
        fechas_json = json.dumps([f[5:] for f in fechas_raw]) # Solo MM-DD
        lluvia_json = json.dumps(lluvias_diarias)
        eto_json = json.dumps(eto_list)

        # Zip para el loop de "Pronóstico Extendido" en HTML
        dias_extendidos = list(zip(
            daily.get('time', []), 
            daily.get('temperature_2m_max', []), 
            daily.get('temperature_2m_min', []), 
            daily.get('precipitation_sum', []), 
            daily.get('precipitation_probability_max', []), 
            daily.get('weather_code', [])
        ))

        # --- TIRA HORARIA (próximas 24h para timeline) ---
        _th24 = hourly.get('temperature_2m', [])
        _lh24 = hourly.get('precipitation_probability', [])
        _wh24 = hourly.get('wind_speed_10m', [])
        _ch24 = hourly.get('weather_code', [])
        tira_24h_agro = []
        for _i in range(24):
            _hi = idx_hora + _i
            if _hi >= len(_th24): break
            tira_24h_agro.append({
                'hora': 'Ahora' if _i == 0 else f'{_hi % 24:02d}:00',
                'temp': round(_th24[_hi] or 0, 1),
                'lluvia': int(_lh24[_hi] or 0) if _hi < len(_lh24) else 0,
                'viento': round(_wh24[_hi] or 0, 1) if _hi < len(_wh24) else 0,
                'code': int(_ch24[_hi] or 0) if _hi < len(_ch24) else 0,
            })

        # --- BANNER DE ALERTA CRÍTICA ---
        viento_actual = curr.get('wind_speed_10m', 0)
        alerta_banner = {'activo': False, 'mensaje': '', 'color': '', 'texto': '', 'borde': ''}
        if delta_t > 10 or viento_actual > 20:
            alerta_banner = {'activo': True, 'mensaje': f'Pulverización PROHIBIDA — Delta T {delta_t}°C / Viento {round(viento_actual,1)} km/h. Riesgo de deriva severo.', 'color': 'rgba(239,68,68,0.12)', 'texto': '#ef4444', 'borde': 'rgba(239,68,68,0.4)'}
        elif delta_t > 8 or vpd_val > 1.6:
            alerta_banner = {'activo': True, 'mensaje': f'Condiciones marginales — VPD {round(vpd_val,2)} kPa / Delta T {delta_t}°C. Evaluar postergación de labores.', 'color': 'rgba(251,146,60,0.12)', 'texto': '#fb923c', 'borde': 'rgba(251,146,60,0.4)'}
        elif balance_neto < -30:
            alerta_banner = {'activo': True, 'mensaje': f'Déficit hídrico severo — Balance semanal {round(balance_neto,1)} mm. Riesgo de estrés en cultivos.', 'color': 'rgba(251,191,36,0.10)', 'texto': '#fbbf24', 'borde': 'rgba(251,191,36,0.3)'}

        # --- CONSTRUCCIÓN DEL CONTEXTO (Mapeo a HTML) ---
        contexto = {
            'lat': lat, 
            'lon': lon,
            
            # Tarjeta GDD
            'gdd': {
                'valor': round(gdd_acum, 1), 
                'estado': 'Vigoroso' if gdd_acum > 50 else 'Lento'
            },
            
            # Tarjeta Suelo (Humedad + Temperaturas por capa)
            'suelo': {
                'sup_hum': int(curr.get('soil_moisture_0_to_1cm', 0) * 100), # x100 para %
                'prof_hum': int(curr.get('soil_moisture_3_to_9cm', 0) * 100),
                'temp_0': curr.get('soil_temperature_0cm', 0),   # Superficie
                'temp_6': curr.get('soil_temperature_6cm', 0),   # Cama Siembra
                'temp_18': curr.get('soil_temperature_18cm', 0), # Raíz Activa
                'temp_54': curr.get('soil_temperature_54cm', 0)  # Profundidad
            },
            
            # Tarjeta Pulverización
            'pulverizacion': {
                'delta_t': delta_t, 
                'viento': curr.get('wind_speed_10m', 0), 
                'estado': cond_pulv, 
                'color': color_pulv
            },
            
            # Tarjeta Atmósfera
            'atmosfera': {
                'rocio': hourly.get('dew_point_2m', [0]*24)[idx_hora], 
                'presion': int(curr.get('pressure_msl', 1013)), 
                'nubes': curr.get('cloud_cover', 0)
            },
            
            # Tarjeta Humedad Ambiente
            'ambiente': {
                'humedad': curr.get('relative_humidity_2m', 0)
            },
            
            # Tarjeta Radiación
            'radiacion': {
                'watts': int(watts_now), 
                'estado': rad_estado
            },
            
            # Tarjeta Balance (Resumen)
            'balance': {
                'lluvia': round(lluvia_semana, 1), 
                'evapo': round(evapo_semana, 1), 
                'diff': round(balance_neto, 1), 
                'color_diff': '#ef4444' if balance_neto < -10 else '#4ade80'
            },
            
            # Tabla Balance Detallada
            'tabla_balance': tabla_balance,
            
            # Tarjeta Raíz (Sección específica)
            'raices': {
                'temp': curr.get('soil_temperature_18cm', 0), 
                'hum': int(curr.get('soil_moisture_9_to_27cm', 0) * 100)
            },
            
            # Tarjeta VPD
            'estres': {
                'vpd': vpd_val, 
                'estado': vpd_estado, 
                'color': vpd_color
            },
            
            # Tarjeta ETo
            'eto': {
                'hoy': eto_list[0] if eto_list else 0, 
                'proyeccion': round((eto_list[0] if eto_list else 0) * 7, 1)
            },
            
            # Bucles y Gráficos
            'dias_extendidos': dias_extendidos,
            'grafico_agro': {
                'fechas': fechas_json,
                'lluvia': lluvia_json,
                'eto': eto_json
            },
            'tira_24h': tira_24h_agro,
        }
        contexto['alerta_banner'] = alerta_banner

    except Exception as e:
        print(f"Error en vista AGRO: {e}")
        # En caso de error, mandamos contexto vacío pero seguro para no romper el HTML
        contexto = {
            'error': 'No se pudieron cargar los datos climáticos.',
            'lat': lat, 'lon': lon
        }

    # Permisos de plan
    _perfil = getattr(request.user, 'perfil', None)
    contexto['plan_nivel'] = _perfil.plan_nivel if _perfil else 'free'
    contexto['puede_excel'] = _perfil.puede_excel if _perfil else False
    contexto['puede_devorador'] = _perfil.puede_devorador if _perfil else False

    return render(request, 'agro.html', contexto)
    



# ==========================================
# 2. VISTA: MODO NAVAL (Náutica / Mar)
# ==========================================
def naval(request):

    # 1. SEGURIDAD Y SUSCRIPCIÓN
    if not request.user.is_authenticated:
        return redirect('login')

    if hasattr(request.user, 'perfil') and not request.user.perfil.suscripcion_activa:
        return redirect('pricing')

    # 1b. Control de acceso sectorial (plan Starter = 1 sector)
    if hasattr(request.user, 'perfil'):
        perfil = request.user.perfil
        if not perfil.tiene_acceso_sector('naval'):
            return render(request, 'sector_bloqueado.html', {
                'sector_bloqueado': 'Naval',
                'sector_actual': perfil.sector_elegido,
                'plan_nivel': perfil.plan_nivel,
            })
        if perfil.plan_nivel == 'starter' and not perfil.sector_elegido:
            perfil.sector_elegido = 'naval'
            perfil.save(update_fields=['sector_elegido'])

    # 2. GESTIÓN DE COORDENADAS (PRIORIDAD USUARIO)
    # Intentamos obtener lo que manda el dashboard/mapa
    lat_input = request.GET.get('lat')
    lon_input = request.GET.get('lon')

    try:
        if lat_input and lon_input:
            # Reemplazamos comas por puntos y convertimos
            lat = float(str(lat_input).replace(',', '.'))
            lon = float(str(lon_input).replace(',', '.'))
        else:
            # SOLO si no hay datos (acceso directo), usamos un default seguro (ej. Buenos Aires)
            lat, lon = -34.60, -58.38 
    except ValueError:
        lat, lon = -34.60, -58.38

    # 3. CONEXIÓN API (DOBLE FUENTE: CLIMA + MARINA)
    
    # A. API Meteorológica (Viento, Visibilidad, Sol, Presión)
    url_weather = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,relative_humidity_2m,apparent_temperature,pressure_msl,"
        "wind_speed_10m,wind_direction_10m,wind_gusts_10m,visibility,is_day"
        "&hourly=wind_speed_10m"
        "&daily=sunrise,sunset,daylight_duration,wind_speed_10m_max,wind_gusts_10m_max"
        "&timezone=auto"
    )
    
    # B. API Marina (Olas, Swell, Periodo)
    # Nota: Si es tierra firme, estos valores vendrán como 'null'
    url_marine = (
        f"https://marine-api.open-meteo.com/v1/marine?latitude={lat}&longitude={lon}"
        "&current=wave_height,wave_direction,wave_period,swell_wave_height,"
        "swell_wave_period,swell_wave_direction"
        "&hourly=wave_height,wave_period,swell_wave_height"
        "&daily=wave_height_max,swell_wave_height_max"
        "&timezone=auto"
    )

    contexto = {}

    try:
        res_w = _get_meteo(url_weather)
        res_m = _get_meteo(url_marine)

        if 'error' in res_w or 'error' in res_m:
            raise Exception("Error de conexión con boyas virtuales.")

        # Bloques de datos
        curr_w = res_w.get('current', {})
        daily_w = res_w.get('daily', {})
        hourly_w = res_w.get('hourly', {})
        
        curr_m = res_m.get('current', {})
        hourly_m = res_m.get('hourly', {})
        
        idx = datetime.now().hour

        # --- CÁLCULOS DE INGENIERÍA NAVAL ---

        # 1. VIENTO (Km/h a Nudos) -> Factor 0.539957
        wind_kmh = curr_w.get('wind_speed_10m', 0)
        wind_kt = round(wind_kmh * 0.539957, 1)
        rafaga_kt = round(curr_w.get('wind_gusts_10m', 0) * 0.539957, 1)
        
        # Escala Beaufort (Viento)
        if wind_kt < 1: beaufort = 0; wind_desc = "Calma"
        elif wind_kt <= 3: beaufort = 1; wind_desc = "Ventolina"
        elif wind_kt <= 6: beaufort = 2; wind_desc = "Brisa Muy Débil"
        elif wind_kt <= 10: beaufort = 3; wind_desc = "Brisa Débil"
        elif wind_kt <= 16: beaufort = 4; wind_desc = "Brisa Moderada"
        elif wind_kt <= 21: beaufort = 5; wind_desc = "Brisa Fresca"
        elif wind_kt <= 27: beaufort = 6; wind_desc = "Brisa Fuerte"
        elif wind_kt <= 33: beaufort = 7; wind_desc = "Viento Fuerte"
        elif wind_kt <= 40: beaufort = 8; wind_desc = "Temporal"
        elif wind_kt <= 47: beaufort = 9; wind_desc = "Temporal Fuerte"
        else: beaufort = 10; wind_desc = "Tormenta"

        # 2. OLEAJE (Metros)
        # Si es tierra, wave_height es None -> ponemos 0.0
        wave_h = curr_m.get('wave_height')
        if wave_h is None: wave_h = 0.0
        
        swell_h = curr_m.get('swell_wave_height')
        if swell_h is None: swell_h = 0.0

        # Escala Douglas (Mar)
        if wave_h == 0: douglas = 0; mar_estado = "Calma"
        elif wave_h <= 0.1: douglas = 1; mar_estado = "Rizada"
        elif wave_h <= 0.5: douglas = 2; mar_estado = "Marejadilla"
        elif wave_h <= 1.25: douglas = 3; mar_estado = "Marejada"
        elif wave_h <= 2.5: douglas = 4; mar_estado = "Fuerte Marejada"
        elif wave_h <= 4.0: douglas = 5; mar_estado = "Gruesa"
        elif wave_h <= 6.0: douglas = 6; mar_estado = "Muy Gruesa"
        elif wave_h <= 9.0: douglas = 7; mar_estado = "Arbolada"
        elif wave_h <= 14.0: douglas = 8; mar_estado = "Montañosa"
        else: douglas = 9; mar_estado = "Enorme"

        # 3. SEMÁFORO DE PUERTO (Lógica Combinada)
        status_color = "#10b981"; status_msg = "ABIERTO" # Verde
        
        # Criterio Precaución (Amarillo)
        if (wave_h >= 1.5 and wave_h < 2.5) or (wind_kt >= 15 and wind_kt < 25):
            status_color = "#facc15"; status_msg = "PRECAUCIÓN"
        
        # Criterio Cerrado (Rojo)
        if wave_h >= 2.5 or wind_kt >= 25:
            status_color = "#ef4444"; status_msg = "CERRADO"

        # 4. VISIBILIDAD (Metros a Millas Náuticas)
        vis_m = curr_w.get('visibility', 10000)
        if vis_m is None: vis_m = 10000
        vis_nm = round(vis_m / 1852, 1)
        
        vis_cond = "BUENA"
        if vis_nm < 1: vis_cond = "NIEBLA CERRADA"
        elif vis_nm < 3: vis_cond = "REDUCIDA"
        elif vis_nm < 5: vis_cond = "REGULAR"

        # 5. ASTRONOMÍA
        sunrise = daily_w.get('sunrise', ["00:00"])[0][-5:]
        sunset = daily_w.get('sunset', ["00:00"])[0][-5:]
        day_len = round(daily_w.get('daylight_duration', [0])[0] / 3600, 1)

        # 6. TEMP AGUA (Estimación Algorítmica)
        # Al no tener boya física, estimamos SST basada en T° Aire con inercia térmica
        temp_aire = curr_w.get('temperature_2m', 20)
        # Fórmula simple de aproximación costera
        temp_agua_est = round(temp_aire * 0.85 + 2, 1) 

        # 7. GRÁFICO 24H (Tendencia)
        raw_olas = hourly_m.get('wave_height', [])
        if not raw_olas: raw_olas = [0] * 24
        
        raw_viento = hourly_w.get('wind_speed_10m', [])
        
        # Cortar a próximas 24hs
        graf_olas = raw_olas[idx:idx+24]
        graf_viento = [round(v * 0.539957, 1) for v in raw_viento[idx:idx+24]]
        graf_horas = [f"{(idx+i)%24}:00" for i in range(len(graf_olas))]

        # 8. GRÁFICO 7 DÍAS (Pronóstico Extendido Naval)
        daily_m = res_m.get('daily', {})
        daily_w2 = res_w.get('daily', {})
        graf7_fechas_raw = daily_m.get('time', daily_w2.get('time', []))[:7]
        graf7_olas_max = [round(v, 2) if v is not None else 0 for v in daily_m.get('wave_height_max', [0]*7)[:7]]
        graf7_viento_max = [round(v * 0.539957, 1) if v is not None else 0 for v in daily_w2.get('wind_speed_10m_max', [0]*7)[:7]]
        # Calcular color de riesgo (Beaufort) por día para JS
        def _bft_color(kt):
            if kt >= 22: return '#ef4444'
            if kt >= 11: return '#facc15'
            return '#22d3ee'
        graf7_colores = [_bft_color(v) for v in graf7_viento_max]
        # Formatear fechas DD/MM
        graf7_fechas = [f[5:] for f in graf7_fechas_raw]  # "MM-DD"

        # --- TIRA HORARIA NAVAL (próximas 24h) ---
        tira_24h_naval = []
        for _i in range(24):
            _hi = idx + _i
            _w = round(raw_viento[_hi] * 0.539957, 1) if _hi < len(raw_viento) and raw_viento[_hi] is not None else 0
            _o = round(raw_olas[_hi], 2) if _hi < len(raw_olas) and raw_olas[_hi] is not None else 0
            tira_24h_naval.append({
                'hora': 'Ahora' if _i == 0 else f'{_hi % 24:02d}:00',
                'viento': _w,
                'ola': _o,
            })

        # --- BANNER DE ALERTA CRÍTICA ---
        alerta_banner = {'activo': False, 'mensaje': '', 'color': '', 'texto': '', 'borde': ''}
        if wave_h >= 2.5 or wind_kt >= 25:
            alerta_banner = {'activo': True, 'mensaje': f'PUERTO CERRADO — Oleaje {wave_h}m / Viento {wind_kt}kt. No salir a navegar.', 'color': 'rgba(239,68,68,0.12)', 'texto': '#ef4444', 'borde': 'rgba(239,68,68,0.4)'}
        elif vis_nm < 1:
            alerta_banner = {'activo': True, 'mensaje': f'NIEBLA CERRADA — Visibilidad {vis_nm} NM. Navegación restringida hasta nuevo aviso.', 'color': 'rgba(148,163,184,0.12)', 'texto': '#94a3b8', 'borde': 'rgba(148,163,184,0.35)'}
        elif wave_h >= 1.5 or wind_kt >= 15:
            alerta_banner = {'activo': True, 'mensaje': f'PRECAUCIÓN — Mar {mar_estado} ({wave_h}m) / Viento F{beaufort} ({wind_kt}kt). Evaluar cada salida individualmente.', 'color': 'rgba(251,191,36,0.10)', 'texto': '#fbbf24', 'borde': 'rgba(251,191,36,0.3)'}

        # --- CONSTRUCCIÓN DEL CONTEXTO ---
        contexto = {
            'lat': lat, 'lon': lon,
            
            # 1. Semáforo
            'status': {'msg': status_msg, 'color': status_color},
            
            # 2. Mar
            'mar': {
                'altura': wave_h, 
                'estado': mar_estado, 
                'douglas': douglas,
                'periodo': curr_m.get('wave_period', 0),
                'dir': curr_m.get('wave_direction', 0)
            },
            
            # 3. Viento
            'viento': {
                'kt': wind_kt, 
                'rafaga': rafaga_kt, 
                'desc': wind_desc,
                'beaufort': beaufort
            },
            
            # 4. Swell
            'swell': {
                'altura': swell_h,
                'periodo': curr_m.get('swell_wave_period', 0),
                'dir': curr_m.get('swell_wave_direction', 0)
            },
            
            # 5. Astro
            'astro': {
                'amanecer': sunrise, 
                'atardecer': sunset, 
                'luz': day_len
            },
            
            # 6. Ambiente
            'ambiente': {
                'temp': temp_aire,
                'sensacion': curr_w.get('apparent_temperature', temp_aire),
                'humedad': curr_w.get('relative_humidity_2m', 0)
            },
            
            # 7. Navegación
            'nav': {
                'vis_nm': vis_nm,
                'cond_vis': vis_cond,
                'presion': curr_w.get('pressure_msl', 1013),
                'temp_agua': temp_agua_est
            },
            
            # 8. Gráficos (JSON)
            'grafico_naval': {
                'fechas': json.dumps(graf_horas),
                'olas': json.dumps(graf_olas),
                'viento': json.dumps(graf_viento)
            },
            'grafico_naval_7d': {
                'fechas': json.dumps(graf7_fechas),
                'olas_max': json.dumps(graf7_olas_max),
                'viento_max': json.dumps(graf7_viento_max),
                'colores': json.dumps(graf7_colores),
            },
            'tira_24h': tira_24h_naval,
        }
        contexto['alerta_banner'] = alerta_banner

    except Exception as e:
        print(f"Error Naval: {e}")
        # Contexto de emergencia
        contexto = {
            'error': 'Datos no disponibles para esta ubicación.',
            'lat': lat, 'lon': lon,
            'status': {'msg': 'OFFLINE', 'color': '#ef4444'},
            'mar': {'altura': 0, 'estado': '-', 'douglas': 0},
            'grafico_naval': {'fechas': '[]', 'olas': '[]', 'viento': '[]'}
        }

    # Permisos de plan
    _perfil = getattr(request.user, 'perfil', None)
    contexto['plan_nivel'] = _perfil.plan_nivel if _perfil else 'free'
    contexto['puede_excel'] = _perfil.puede_excel if _perfil else False
    contexto['puede_devorador'] = _perfil.puede_devorador if _perfil else False

    return render(request, 'naval.html', contexto)

# ==========================================
# 3. VISTA: MODO AÉREO (Aviación / Pilotos)
def aereo(request):
    # 1. SEGURIDAD
    if not request.user.is_authenticated:
        return redirect('login')

    if hasattr(request.user, 'perfil') and not request.user.perfil.suscripcion_activa:
        return redirect('pricing')

    # 1b. Control de acceso sectorial (plan Starter = 1 sector)
    if hasattr(request.user, 'perfil'):
        perfil = request.user.perfil
        if not perfil.tiene_acceso_sector('aereo'):
            return render(request, 'sector_bloqueado.html', {
                'sector_bloqueado': 'Aéreo',
                'sector_actual': perfil.sector_elegido,
                'plan_nivel': perfil.plan_nivel,
            })
        if perfil.plan_nivel == 'starter' and not perfil.sector_elegido:
            perfil.sector_elegido = 'aereo'
            perfil.save(update_fields=['sector_elegido'])

    # 2. COORDENADAS
    lat_raw = request.GET.get('lat', '-34.60')
    lon_raw = request.GET.get('lon', '-58.38')
    try:
        lat = float(str(lat_raw).replace(',', '.'))
        lon = float(str(lon_raw).replace(',', '.'))
    except ValueError:
        lat, lon = -34.60, -58.38

    # 3. API OPEN-METEO (INCLUYENDO NIVEL 300hPa / FL300)
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        "&models=gfs_seamless"
        "&current=temperature_2m,relative_humidity_2m,is_day,weather_code,cloud_cover,pressure_msl,wind_speed_10m,wind_direction_10m,wind_gusts_10m,visibility"
        "&hourly=temperature_2m,dew_point_2m,cloud_cover,cloud_cover_low,cloud_cover_mid,cloud_cover_high,wind_speed_10m,"
        "wind_speed_950hPa,wind_direction_950hPa,temperature_950hPa,"  # 2000 ft
        "wind_speed_850hPa,wind_direction_850hPa,temperature_850hPa,"  # 5000 ft
        "wind_speed_700hPa,wind_direction_700hPa,temperature_700hPa,"  # 10000 ft
        "wind_speed_300hPa,wind_direction_300hPa,temperature_300hPa,"  # 30000 ft (NUEVO)
        "cape,lifted_index"
        "&daily=sunrise,sunset"
    )

    try:
        data = _get_meteo(url, timeout=6)
        if 'error' in data:
            raise Exception(data.get('reason', 'API error'))

        curr = data.get('current', {})
        hourly = data.get('hourly', {})
        daily = data.get('daily', {})
        
        idx = datetime.utcnow().hour
        if idx >= len(hourly.get('time', [])): idx = 0

        # Función de seguridad para listas
        def get_safe(arr, i, default=0): 
            val = arr[i] if arr and i < len(arr) else default
            return val if val is not None else default

        # --- PROCESAMIENTO DE DATOS ---
        
        # 1. VISIBILIDAD & TECHO
        vis_metros = curr.get('visibility', 10000)
        if vis_metros is None: vis_metros = 10000
        vis_km = vis_metros / 1000
        vis_display = "10+" if vis_km >= 10 else round(vis_km, 1)

        temp = curr.get('temperature_2m', 15) or 15
        dew = get_safe(hourly.get('dew_point_2m', []), idx, temp-2)
        spread = temp - dew
        base_nubes = spread * 400 if spread > 0 else 9999
        cover = curr.get('cloud_cover', 0) or 0

        # 2. CATEGORÍA
        cat = "VFR"; color = "#22c55e"
        if vis_km < 8 or (cover > 50 and base_nubes < 3000): cat = "MVFR"; color = "#3b82f6"
        if vis_km < 5 or (cover > 50 and base_nubes < 1000): cat = "IFR"; color = "#ef4444"
        if vis_km < 1.6 or (cover > 80 and base_nubes < 500): cat = "LIFR"; color = "#d946ef"

        # Panel Visibilidad Texto
        vis_txt = "Ilimitada"; vis_color = "#22c55e"
        if vis_km < 10: vis_txt = "Reducida"; vis_color = "#facc15"
        if vis_km < 5: vis_txt = "Baja (IFR)"; vis_color = "#ef4444"
        if vis_km < 2: vis_txt = "Niebla (LIFR)"; vis_color = "#d946ef"

        # 3. VIENTOS & RIESGOS
        wind_k = int(curr.get('wind_speed_10m', 0) or 0)
        gusts = int(curr.get('wind_gusts_10m', 0) or 0)
        
        cape_list = [x for x in hourly.get('cape', [])[idx:idx+3] if x is not None]
        li_list = [x for x in hourly.get('lifted_index', [])[idx:idx+3] if x is not None]
        max_cape = max(cape_list) if cape_list else 0
        min_li = min(li_list) if li_list else 0

        r_st="NORMAL"; r_col="#22c55e"; r_av="Sin Ecos"; r_desc="Atmósfera estable."
        if max_cape > 500 or min_li < -2: r_st="ALERTA"; r_col="#facc15"; r_av="Inestabilidad"; r_desc="Posible desarrollo."
        if max_cape > 1000 or min_li < -4: r_st="TORMENTA"; r_col="#ef4444"; r_av="Actividad Convectiva"; r_desc="Riesgo de tormenta."
        if max_cape > 2500: r_st="SEVERO"; r_col="#d946ef"; r_av="CELDAS SUPERPUESTAS"; r_desc="Condiciones extremas."

        riesgo = "BAJO RIESGO"; color_r = "#22c55e"
        if (gusts - wind_k) > 15: riesgo = "WIND SHEAR"; color_r = "#facc15"
        if max_cape > 1000: riesgo = "TORMENTA"; color_r = "#ef4444"
        if temp < 4 and vis_km < 5: riesgo = "RIESGO HIELO"; color_r = "#ef4444"

        # 4. TABLAS DE ALTURA (CON FL300)
        w_2000 = get_safe(hourly.get('wind_speed_950hPa', []), idx)
        w_5000 = get_safe(hourly.get('wind_speed_850hPa', []), idx)
        w_10000 = get_safe(hourly.get('wind_speed_700hPa', []), idx)
        w_30000 = get_safe(hourly.get('wind_speed_300hPa', []), idx) # NUEVO

        tabla_vientos = [
            {'lvl': 'SFC', 'dir': int(curr.get('wind_direction_10m',0) or 0), 'kt': wind_k, 'efecto': f"T: {int(temp)}°C"},
            {'lvl': '2000ft', 'dir': int(get_safe(hourly.get('wind_direction_950hPa', []), idx)), 'kt': int(w_2000), 'efecto': f"SAT: {int(get_safe(hourly.get('temperature_950hPa', []), idx))}°C"},
            {'lvl': '5000ft', 'dir': int(get_safe(hourly.get('wind_direction_850hPa', []), idx)), 'kt': int(w_5000), 'efecto': f"SAT: {int(get_safe(hourly.get('temperature_850hPa', []), idx))}°C"},
            {'lvl': '10000ft', 'dir': int(get_safe(hourly.get('wind_direction_700hPa', []), idx)), 'kt': int(w_10000), 'efecto': f"SAT: {int(get_safe(hourly.get('temperature_700hPa', []), idx))}°C"},
            {'lvl': 'FL300 (Jet)', 'dir': int(get_safe(hourly.get('wind_direction_300hPa', []), idx)), 'kt': int(w_30000), 'efecto': f"SAT: {int(get_safe(hourly.get('temperature_300hPa', []), idx))}°C"}, # NUEVO
        ]

        # 5. GRÁFICO JSON (Corregido con capas)
        def clean(arr): return [x if x is not None else 0 for x in arr[idx:idx+12]]
        
        grafico_data = {
            'labels': json.dumps([f"{(idx+i)%24:02d}Z" for i in range(12)]),
            
            # CAPAS DE NUBES
            'nubes_total': json.dumps(clean(hourly.get('cloud_cover', []))),
            'nubes_low': json.dumps(clean(hourly.get('cloud_cover_low', []))),
            'nubes_mid': json.dumps(clean(hourly.get('cloud_cover_mid', []))),
            'nubes_high': json.dumps(clean(hourly.get('cloud_cover_high', []))), # NUEVO PARA FL300
            
            # VIENTOS
            'v_sfc': json.dumps(clean(hourly.get('wind_speed_10m', []))),
            'v_2000': json.dumps(clean(hourly.get('wind_speed_950hPa', []))),
            'v_5000': json.dumps(clean(hourly.get('wind_speed_850hPa', []))),
            'v_10000': json.dumps(clean(hourly.get('wind_speed_700hPa', []))),
            'v_30000': json.dumps(clean(hourly.get('wind_speed_300hPa', []))), # NUEVO PARA FL300
        }

        # 6. TABLA NUBES
        def c_desc(p, t):
            if p<10: return "Despejado"
            base = "FEW" if p<25 else "SCT" if p<50 else "BKN" if p<90 else "OVC"
            if t=='low' and p>50: return f"{base} - ⚠️ Techo"
            return base

        tabla_nubes = [
            {'capa': 'Bajas', 'pct': get_safe(hourly.get('cloud_cover_low', []), idx), 'desc': c_desc(get_safe(hourly.get('cloud_cover_low', []), idx), 'low')},
            {'capa': 'Medias', 'pct': get_safe(hourly.get('cloud_cover_mid', []), idx), 'desc': c_desc(get_safe(hourly.get('cloud_cover_mid', []), idx), 'mid')},
            {'capa': 'Altas', 'pct': get_safe(hourly.get('cloud_cover_high', []), idx), 'desc': c_desc(get_safe(hourly.get('cloud_cover_high', []), idx), 'high')},
        ]

        # --- BANNER DE ALERTA CRÍTICA ---
        alerta_banner = {'activo': False, 'mensaje': '', 'color': '', 'texto': '', 'borde': ''}
        if cat in ('LIFR', 'IFR') or max_cape > 1000:
            alerta_banner = {'activo': True, 'mensaje': f'{cat} ACTIVO — {"Tormentas en área · " if max_cape > 1000 else ""}Vuelo VFR restringido. Consultar METAR oficial antes de despegar.', 'color': 'rgba(239,68,68,0.12)', 'texto': '#ef4444', 'borde': 'rgba(239,68,68,0.4)'}
        elif (gusts - wind_k) > 20:
            alerta_banner = {'activo': True, 'mensaje': f'WIND SHEAR — Diferencial {gusts - wind_k} KT entre superficie y ráfagas. Precaución en despegue y aproximación.', 'color': 'rgba(251,146,60,0.12)', 'texto': '#fb923c', 'borde': 'rgba(251,146,60,0.4)'}
        elif cat == 'MVFR':
            alerta_banner = {'activo': True, 'mensaje': f'MVFR ACTIVO — Visibilidad {vis_display} km. Condiciones subóptimas para VFR. Verificar METAR antes de despegar.', 'color': 'rgba(59,130,246,0.12)', 'texto': '#60a5fa', 'borde': 'rgba(59,130,246,0.3)'}

        contexto = {
            'lat': lat, 'lon': lon,
            'metar': {'raw': f"VIRTUAL {datetime.utcnow().strftime('%d%H%MZ')} {int(curr.get('wind_direction_10m',0) or 0):03d}{wind_k:02d}KT {9999 if vis_km>=10 else int(vis_metros)}", 'hora': datetime.utcnow().strftime('%H:%MZ')},
            'categoria': {'codigo': cat, 'color': color, 'vis': vis_display, 'techo': int(base_nubes) if cover > 50 else "CAVOK"},
            'altimetria': {'qnh': int(curr.get('pressure_msl', 1013) or 1013), 'density_alt': int((1013-(curr.get('pressure_msl') or 1013))*30 + 120*(temp-15)), 'spread': round(spread, 1)},
            'viento': {'kt': wind_k, 'dir': int(curr.get('wind_direction_10m', 0) or 0), 'rafagas': gusts},
            'nubes': {'estado': "OVC" if cover>90 else ("BKN" if cover>50 else "FEW"), 'cobertura': f"{int(cover)}%", 'base': f"{int(base_nubes)} ft"},
            'riesgos': {'msg': riesgo, 'color': color_r, 'iso_0': f"{int(max(0, temp*1000/2))} ft", 'shear': f"{gusts-wind_k} KT"},
            
            'tabla_vientos': tabla_vientos, 'tabla_nubes': tabla_nubes,
            'viento_altura': {'dir': tabla_vientos[2]['dir'], 'kt': tabla_vientos[2]['kt']},
            'astro': {'sale': daily.get('sunrise', ['--'])[0][-5:] if daily.get('sunrise') else '--', 'puesta': daily.get('sunset', ['--'])[0][-5:] if daily.get('sunset') else '--', 'luz': 'Día' if curr.get('is_day') else 'Noche'},
            'ambiente': {'temp': int(temp), 'humedad': curr.get('relative_humidity_2m', 0) or 0, 'desc': 'Normal', 'sensacion': int(curr.get('apparent_temperature', temp) or temp)},
            'radar': {'estado': r_st, 'color': r_col, 'aviso': r_av, 'desc': r_desc, 'cape': int(max_cape), 'li': round(min_li, 1)},
            'visibilidad_panel': {'km': vis_display, 'estado': vis_txt, 'color': vis_color},
            'grafico_aereo': grafico_data,
            'tira_24h': [
                {
                    'hora': 'Ahora' if _i == 0 else f'{(idx+_i) % 24:02d}Z',
                    'nubes': int(hourly.get('cloud_cover', [0]*200)[(idx+_i)] or 0) if (idx+_i) < len(hourly.get('cloud_cover', [])) else 0,
                    'viento': int(hourly.get('wind_speed_10m', [0]*200)[(idx+_i)] or 0) if (idx+_i) < len(hourly.get('wind_speed_10m', [])) else 0,
                    'temp': round((hourly.get('temperature_2m', [0]*200)[(idx+_i)] or 0), 1) if (idx+_i) < len(hourly.get('temperature_2m', [])) else 0,
                }
                for _i in range(24) if (idx+_i) < len(hourly.get('cloud_cover', [0]*200))
            ],
        }
        contexto['alerta_banner'] = alerta_banner

    except Exception as e:
        print(f"⚠️ ERROR CRÍTICO AEREO: {e}")
        # En caso de fallo, mostramos esto para debug
        contexto = {'error': 'Error de Datos'}

    # Permisos de plan
    _perfil = getattr(request.user, 'perfil', None)
    contexto['plan_nivel'] = _perfil.plan_nivel if _perfil else 'free'
    contexto['puede_excel'] = _perfil.puede_excel if _perfil else False
    contexto['puede_devorador'] = _perfil.puede_devorador if _perfil else False

    return render(request, 'aereo.html', contexto)


# --- VISTA ENERGÍA (ENERGY OPS) ---
def energia(request):

    # 1. SEGURIDAD
    if not request.user.is_authenticated:
        return redirect('login')

    if hasattr(request.user, 'perfil') and not request.user.perfil.suscripcion_activa:
        return redirect('pricing')

    # 1b. Control de acceso sectorial (plan Starter = 1 sector)
    if hasattr(request.user, 'perfil'):
        perfil = request.user.perfil
        if not perfil.tiene_acceso_sector('energia'):
            return render(request, 'sector_bloqueado.html', {
                'sector_bloqueado': 'Energía',
                'sector_actual': perfil.sector_elegido,
                'plan_nivel': perfil.plan_nivel,
            })
        if perfil.plan_nivel == 'starter' and not perfil.sector_elegido:
            perfil.sector_elegido = 'energia'
            perfil.save(update_fields=['sector_elegido'])

    # 2. COORDENADAS
    lat_raw = request.GET.get('lat', '-34.60')
    lon_raw = request.GET.get('lon', '-58.38')
    try:
        lat = float(str(lat_raw).replace(',', '.'))
        lon = float(str(lon_raw).replace(',', '.'))
    except ValueError:
        lat, lon = -34.60, -58.38

    # 3. API OPEN-METEO (DATOS REALES)
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        "&current=shortwave_radiation,direct_radiation,diffuse_radiation,wind_speed_10m,temperature_2m,weather_code,pressure_msl,relative_humidity_2m"
        "&hourly=shortwave_radiation,wind_speed_10m,temperature_2m,pressure_msl"
        "&timezone=auto"
    )

    try:
        data = _get_meteo(url, timeout=5)
        if 'error' in data:
            raise Exception(data.get('reason', 'API error'))

        curr = data.get('current', {})
        hourly = data.get('hourly', {})
        
        idx = datetime.now().hour 
        if idx >= len(hourly.get('time', [])): idx = 0

        # --- FÍSICA REAL (SIN SIMULACIONES) ---
        
        # 1. SOLAR (Irradiancia Real)
        rad_now = curr.get('shortwave_radiation', 0) or 0
        temp_now = curr.get('temperature_2m', 20)
        
        # Pérdida térmica real
        loss_factor = 1.0
        if temp_now > 25: loss_factor = 1.0 - ((temp_now - 25) * 0.004)
        
        potencia_solar = rad_now * 20 * 0.18 * loss_factor # Modelo 20m2
        
        # 2. EÓLICA (Viento Real)
        wind_kmh = curr.get('wind_speed_10m', 0) or 0
        wind_ms = wind_kmh / 3.6
        
        potencia_eolica = 0
        if wind_ms > 3.0: # Cut-in real
            potencia_eolica = min(3000, 10 * (wind_ms ** 3))
        
        # 3. ATMÓSFERA (Cálculo Físico Real)
        presion_hpa = curr.get('pressure_msl', 1013)
        
        # Fórmula de Densidad del Aire (Ley de Gases Ideales): rho = P / (R * T)
        # R aire seco = 287.05 J/(kg·K)
        # P en Pascales (hPa * 100)
        # T en Kelvin (C + 273.15)
        presion_pa = presion_hpa * 100
        temp_kelvin = temp_now + 273.15
        
        densidad_aire = presion_pa / (287.05 * temp_kelvin)

        # 4. TOTALES
        total_kw = (potencia_solar + potencia_eolica) / 1000
        
        # Economía (Referencia estandarizada)
        tarifa_ref = 0.15 
        ahorro_hora = total_kw * tarifa_ref

        # --- PROYECCIÓN 24H ---
        arr_solar = []
        arr_wind = []
        arr_h2 = []
        
        total_kwh_day = 0
        
        for i in range(24):
            r = hourly.get('shortwave_radiation', [0]*24)[i] or 0
            t = hourly.get('temperature_2m', [20]*24)[i] or 20
            w = (hourly.get('wind_speed_10m', [0]*24)[i] or 0) / 3.6
            
            # Solar loop
            lf = 1.0 - ((t - 25) * 0.004) if t > 25 else 1.0
            p_s = r * 20 * 0.18 * lf
            arr_solar.append(round(p_s))
            
            # Wind loop
            p_w = min(3000, 10 * (w ** 3)) if w > 3 else 0
            arr_wind.append(round(p_w))
            
            # H2 loop
            p_tot = (p_s + p_w) / 1000
            total_kwh_day += p_tot
            arr_h2.append(round(p_tot / 55, 3))

        # CO2 Real
        co2_evitado = total_kwh_day * 0.44

        # Estados
        st_solar = "STANDBY" if potencia_solar < 10 else "GENERANDO"
        col_solar = "#64748b" if potencia_solar < 10 else "#facc15"
        
        st_eol = "CALMA"
        col_eol = "#64748b"
        if wind_ms > 3: st_eol = "GENERANDO"; col_eol = "#3b82f6"

        h2_rate = total_kw / 55
        ganador = "RED EXTERNA"
        if total_kw > 0.05:
            ganador = "SOLAR" if potencia_solar > potencia_eolica else "EÓLICA"

        # --- BANNER DE ALERTA CRÍTICA ---
        alerta_banner = {'activo': False, 'mensaje': '', 'color': '', 'texto': '', 'borde': ''}
        if temp_now > 38:
            alerta_banner = {'activo': True, 'mensaje': f'Temperatura crítica — {int(temp_now)}°C reduce eficiencia solar en {round((1-loss_factor)*100,1)}%. Verificar ventilación de paneles.', 'color': 'rgba(239,68,68,0.12)', 'texto': '#f87171', 'borde': 'rgba(239,68,68,0.35)'}
        elif wind_ms > 12:
            alerta_banner = {'activo': True, 'mensaje': f'Viento fuerte — {round(wind_ms,1)} m/s. Verificar anclaje de turbina y revisar protocolo de desconexión de emergencia.', 'color': 'rgba(251,191,36,0.10)', 'texto': '#fbbf24', 'borde': 'rgba(251,191,36,0.3)'}

        contexto = {
            'lat': lat, 'lon': lon,
            'solar': {'rad': int(rad_now), 'potencia': f"{int(potencia_solar)} W", 'estado': st_solar, 'color': col_solar, 'rec': "Limpieza si eficiencia < 15%."},
            'eolica': {'ms': round(wind_ms, 1), 'potencia': f"{int(potencia_eolica)} W", 'estado': st_eol, 'color': col_eol, 'w100': f"{int(wind_kmh)} km/h", 'rec': "Revisar vibraciones en góndola."},
            'hidro': {'kg': round(h2_rate * 24, 2), 'estado': "ELECTRÓLISIS" if h2_rate > 0.01 else "STANDBY", 'color': "#10b981" if h2_rate > 0.01 else "#64748b"},
            'eficiencia': {'temp_panel': f"{int(temp_now + (rad_now/800)*25)}°C", 'factor': f"{int(loss_factor*100)}%", 'perdida': f"-{round((1-loss_factor)*100, 1)}%", 'color': "#ef4444" if loss_factor < 0.9 else "#22c55e"},
            
            # --- CORRECCIÓN CLAVE PARA QUE FUNCIONE EN HTML ---
            # Enviamos dos diccionarios: 'atm' (nuevo estándar) y 'red' (para compatibilidad si el HTML busca 'red')
            'atm': {
                'presion': f"{int(presion_hpa)} hPa",
                'densidad': f"{densidad_aire:.3f} kg/m³", # Dato calculado
                'color': "#22c55e"
            },
            'red': { # Mantenemos 'red' para que no rompa el HTML viejo
                'estabilidad': f"{int(presion_hpa)} hPa",
                'riesgo': "SENSOR ACTIVO",
                'color': "#8b5cf6"
            },
            
            'smart_meter': {
                'total_kw': f"{total_kw:.2f}",
                'dinero': f"${ahorro_hora:.2f}",
                'proyeccion_mes': f"${(total_kwh_day * tarifa_ref * 30):.0f}",
                'co2': round(co2_evitado, 1),
                'arboles': int(co2_evitado / 0.06),
                'km_auto': round(co2_evitado / 0.12, 1),
                'bateria_tiempo': f"{round(10 / (total_kw if total_kw > 0.1 else 0.1), 1)} h",
                'color': col_solar if ganador == "SOLAR" else col_eol
            },
            
            'mix': {'ganador': ganador, 'rec': "Optimizar consumo según tarifa."},
            'hidro_clima': {'mm': 0, 'estado': 'N/A', 'rec': 'Revise sensores locales.'},
            'grafico': {
                'labels': json.dumps([f"{i}h" for i in range(24)]),
                'solar': json.dumps(arr_solar),
                'viento': json.dumps(arr_wind),
                'h2': json.dumps(arr_h2)
            },
            'tira_24h': [
                {
                    'hora': 'Ahora' if _i == 0 else f'{(idx+_i) % 24:02d}:00',
                    'rad': int((hourly.get('shortwave_radiation', [0]*168)[(idx+_i) % len(hourly.get('shortwave_radiation', [1]))] or 0)),
                    'viento': round(((hourly.get('wind_speed_10m', [0]*168)[(idx+_i) % len(hourly.get('wind_speed_10m', [1]))] or 0) / 3.6), 1),
                    'temp': round((hourly.get('temperature_2m', [20]*168)[(idx+_i) % len(hourly.get('temperature_2m', [1]))] or 20), 1),
                }
                for _i in range(24)
            ],
        }
        contexto['alerta_banner'] = alerta_banner

    except Exception as e:
        print(f"Error Energia: {e}")
        contexto = {'error': 'Sin datos'}

    # Permisos de plan
    _perfil = getattr(request.user, 'perfil', None)
    contexto['plan_nivel'] = _perfil.plan_nivel if _perfil else 'free'
    contexto['puede_excel'] = _perfil.puede_excel if _perfil else False
    contexto['puede_devorador'] = _perfil.puede_devorador if _perfil else False

    return render(request, 'energia.html', contexto)



# COMPARADOR DE MODELOS

def comparador_modelos(request):
    # 1. Recuperamos coordenadas
    lat_raw = request.GET.get('lat', '-34.6037')
    lon_raw = request.GET.get('lon', '-58.3816')
    ciudad = request.GET.get('ciudad', 'Ubicación Seleccionada')
    
    try:
        lat = str(lat_raw).replace(',', '.')
        lon = str(lon_raw).replace(',', '.')
    except:
        lat = '-34.6037'; lon = '-58.3816'

    # 2. API MULTI-VAR (Pedimos 6 variables)
    # temperature_2m, wind_speed_10m, precipitation, relative_humidity_2m, pressure_msl, cloud_cover
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,wind_speed_10m,precipitation,relative_humidity_2m,pressure_msl,cloud_cover&models=meteofrance_seamless,gfs_seamless,icon_seamless&timezone=auto&forecast_days=3"
    
    # Listas por defecto
    labels = []
    # Variables
    t_eu=[]; t_gfs=[]; t_icon=[] # Temp
    w_eu=[]; w_gfs=[]; w_icon=[] # Viento
    p_eu=[]; p_gfs=[]; p_icon=[] # Lluvia
    h_eu=[]; h_gfs=[]; h_icon=[] # Humedad
    pr_eu=[]; pr_gfs=[]; pr_icon=[] # Presion
    c_eu=[]; c_gfs=[]; c_icon=[] # Nubosidad

    confianza_score = 0
    estado_confianza = "ND"
    color_confianza = "#94a3b8"

    try:
        response = _get_meteo(url)
        
        if 'hourly' in response:
            hourly = response['hourly']
            rango = 48 
            labels = [dt.split('T')[1] for dt in hourly['time'][:rango]]
            
            # --- EXTRACCIÓN MASIVA DE DATOS ---
            
            # 1. TEMPERATURA
            t_eu = hourly.get('temperature_2m_meteofrance_seamless', [])[:rango]
            t_gfs = hourly.get('temperature_2m_gfs_seamless', [])[:rango]
            t_icon = hourly.get('temperature_2m_icon_seamless', [])[:rango]

            # 2. VIENTO
            w_eu = hourly.get('wind_speed_10m_meteofrance_seamless', [])[:rango]
            w_gfs = hourly.get('wind_speed_10m_gfs_seamless', [])[:rango]
            w_icon = hourly.get('wind_speed_10m_icon_seamless', [])[:rango]

            # 3. LLUVIA
            p_eu = hourly.get('precipitation_meteofrance_seamless', [])[:rango]
            p_gfs = hourly.get('precipitation_gfs_seamless', [])[:rango]
            p_icon = hourly.get('precipitation_icon_seamless', [])[:rango]

            # 4. HUMEDAD
            h_eu = hourly.get('relative_humidity_2m_meteofrance_seamless', [])[:rango]
            h_gfs = hourly.get('relative_humidity_2m_gfs_seamless', [])[:rango]
            h_icon = hourly.get('relative_humidity_2m_icon_seamless', [])[:rango]

            # 5. PRESIÓN (MSL)
            pr_eu = hourly.get('pressure_msl_meteofrance_seamless', [])[:rango]
            pr_gfs = hourly.get('pressure_msl_gfs_seamless', [])[:rango]
            pr_icon = hourly.get('pressure_msl_icon_seamless', [])[:rango]

            # 6. NUBOSIDAD
            c_eu = hourly.get('cloud_cover_meteofrance_seamless', [])[:rango]
            c_gfs = hourly.get('cloud_cover_gfs_seamless', [])[:rango]
            c_icon = hourly.get('cloud_cover_icon_seamless', [])[:rango]
            
            # Calculamos confianza basándonos en Temperatura (Referencia principal)
            diferencias = []
            largo_seguro = min(len(t_eu), len(t_gfs), len(t_icon))
            for i in range(largo_seguro):
                vals = [x for x in [t_eu[i], t_gfs[i], t_icon[i]] if x is not None]
                if len(vals) > 1:
                    dif = max(vals) - min(vals)
                    diferencias.append(dif)
            
            if diferencias:
                promedio_dif = sum(diferencias) / len(diferencias)
                confianza_score = max(0, min(100, int(100 - (promedio_dif * 20))))
            else:
                confianza_score = 50 
            
            estado_confianza = "ALTA"; color_confianza = "#2ed573"
            if confianza_score < 75: estado_confianza = "MEDIA"; color_confianza = "#ffa502"
            if confianza_score < 50: estado_confianza = "BAJA"; color_confianza = "#ff4757"

    except Exception as e:
        print(f"Error modelos: {e}")

    return render(request, 'comparador.html', {
        'ciudad': ciudad, 'labels': json.dumps(labels),
        # Temp
        't_eu': json.dumps(t_eu), 't_gfs': json.dumps(t_gfs), 't_icon': json.dumps(t_icon),
        # Viento
        'w_eu': json.dumps(w_eu), 'w_gfs': json.dumps(w_gfs), 'w_icon': json.dumps(w_icon),
        # Lluvia
        'p_eu': json.dumps(p_eu), 'p_gfs': json.dumps(p_gfs), 'p_icon': json.dumps(p_icon),
        # Humedad
        'h_eu': json.dumps(h_eu), 'h_gfs': json.dumps(h_gfs), 'h_icon': json.dumps(h_icon),
        # Presion
        'pr_eu': json.dumps(pr_eu), 'pr_gfs': json.dumps(pr_gfs), 'pr_icon': json.dumps(pr_icon),
        # Nubosidad
        'c_eu': json.dumps(c_eu), 'c_gfs': json.dumps(c_gfs), 'c_icon': json.dumps(c_icon),
        
        'confianza': confianza_score, 'estado_confianza': estado_confianza, 'color_confianza': color_confianza,
        'lat': lat, 'lon': lon
    })



# ==============================================================================
#  MÓDULO ESPACIAL (NOAA SWPC)
# ==============================================================================
def meteorologia_espacial(request):
    # URLs Oficiales
    url_kp = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
    url_plasma = "https://services.swpc.noaa.gov/products/solar-wind/plasma-5-minute.json"
    url_mag = "https://services.swpc.noaa.gov/products/solar-wind/mag-5-minute.json" # <--- NUEVO: Magnetómetro
    url_xray = "https://services.swpc.noaa.gov/json/GOES/primary/xrays-6-hour.json" # <--- NUEVO: Rayos X
    url_nasa_earth = "https://epic.gsfc.nasa.gov/api/natural"
    
    # Inits seguros
    kp_actual = 0; kp_estado = "Datos no disponibles"; kp_color = "#64748b"
    viento_velocidad = 0; viento_densidad = 0
    bz = 0; bz_estado = "Cerrado"; bz_color = "#64748b" # Init Bz
    flare_class = "A"; flare_val = 0.0 # Init Rayos X
    proton_flux = 0.1 # Init Protones (Simulado base si no hay tormenta)

    labels_kp = []; data_kp = []
    img_tierra = "https://epic.gsfc.nasa.gov/archive/natural/2023/10/26/png/epic_1b_20231026003633.png"

    try:
        # 1. ÍNDICE KP
        try:
            resp_kp = requests.get(url_kp, timeout=3).json()
            ultimo_dato = resp_kp[-1]
            kp_actual = float(ultimo_dato[1])
            # Historial
            for fila in resp_kp[-24:]:
                labels_kp.append(fila[0].split(' ')[1][:5])
                data_kp.append(float(fila[1]))
            # Semáforo
            if kp_actual < 4: kp_estado = "Tranquilo"; kp_color = "#2ed573"
            elif kp_actual < 5: kp_estado = "Activo"; kp_color = "#ffa502"
            elif kp_actual == 5: kp_estado = "Tormenta G1"; kp_color = "#ff6b81"
            elif kp_actual == 6: kp_estado = "Tormenta G2"; kp_color = "#ff4757"
            elif kp_actual >= 7: kp_estado = "Tormenta G3+"; kp_color = "#ff0000"
        except: pass

        # 2. VIENTO SOLAR (Velocidad y Densidad)
        try:
            resp_plasma = requests.get(url_plasma, timeout=3).json()
            ultimo_plasma = resp_plasma[-1]
            viento_densidad = float(ultimo_plasma[1])
            viento_velocidad = float(ultimo_plasma[2])
        except: pass

        # 3. CAMPO MAGNÉTICO (Bz) - NUEVO
        try:
            resp_mag = requests.get(url_mag, timeout=3).json()
            ultimo_mag = resp_mag[-1]
            bz = float(ultimo_mag[3]) # La columna 3 suele ser Bz
            
            # Lógica: Si Bz es negativo, "se abre la puerta" a auroras
            if bz < 0: 
                bz_estado = "Sur (Abierto)"
                bz_color = "#ff4757" # Rojo alerta (bueno para auroras)
                if bz < -5: bz_estado = "Sur Profundo (Muy Abierto)"
            else:
                bz_estado = "Norte (Cerrado)"
                bz_color = "#2ed573" # Verde tranquilo
        except: pass

        # 4. RAYOS X (FLARES) - NUEVO
        try:
            resp_xray = requests.get(url_xray, timeout=3).json()
            # Buscamos el último valor 'flux'
            ultimo_xray = resp_xray[-1]['flux']
            flare_val = float(ultimo_xray)
            
            # Clasificación Científica (A, B, C, M, X)
            if flare_val < 1e-7: flare_class = "A (Mínima)"
            elif flare_val < 1e-6: flare_class = "B (Baja)"
            elif flare_val < 1e-5: flare_class = "C (Menor)"
            elif flare_val < 1e-4: flare_class = "M (Moderada)"
            else: flare_class = "X (Severa!)"
        except: pass

        # 5. NASA EPIC (Tierra)
        try:
            res_earth = requests.get(url_nasa_earth, timeout=3).json()
            if res_earth:
                latest = res_earth[-1]
                img_name = latest['image']
                date_path = latest['date'].split(' ')[0].replace('-', '/')
                img_tierra = f"https://epic.gsfc.nasa.gov/archive/natural/{date_path}/png/{img_name}.png"
        except: pass

    except Exception as e:
        print(f"Error Espacio: {e}")

    return render(request, 'espacio.html', {
        'kp': kp_actual, 'kp_estado': kp_estado, 'kp_color': kp_color,
        'velocidad': viento_velocidad, 'densidad': viento_densidad,
        'bz': bz, 'bz_estado': bz_estado, 'bz_color': bz_color, # Nuevos
        'flare_class': flare_class, 'flare_val': flare_val, # Nuevos
        'labels_kp': json.dumps(labels_kp), 'data_kp': json.dumps(data_kp),
        'img_aurora_sur': "https://services.swpc.noaa.gov/images/aurora-forecast-southern-hemisphere.jpg",
        'img_aurora_norte': "https://services.swpc.noaa.gov/images/aurora-forecast-northern-hemisphere.jpg",
        'img_sol': "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_0193.jpg",
        'img_tierra': img_tierra
    })







# ==========================================
# 5. SISTEMA DE PAGOS (PAYPAL)
# ==========================================

# Credenciales desde variables de entorno (nunca hardcodear en el código)
paypalrestsdk.configure({
    "mode": os.getenv('PAYPAL_MODE', 'sandbox'),  # 'sandbox' en dev, 'live' en producción
    "client_id": os.getenv('PAYPAL_CLIENT_ID', ''),
    "client_secret": os.getenv('PAYPAL_CLIENT_SECRET', '')
})

@login_required
def crear_pago_paypal(request):
    # El plan se pasa como query param (?plan=mensual o ?plan=anual)
    plan = request.GET.get('plan', 'mensual')
    if plan not in ('mensual', 'anual'):
        plan = 'mensual'

    # Guardar plan en sesión para recuperarlo al volver de PayPal
    request.session['plan_pago'] = plan

    if plan == 'anual':
        precio = '200.00'
        nombre_item = 'Suscripción Weather PRO Anual'
        sku = 'pro_anual'
        descripcion = 'Acceso anual a Weather Pro Suite (12 meses)'
    else:
        precio = '20.00'
        nombre_item = 'Suscripción Weather PRO Mensual'
        sku = 'pro_mensual'
        descripcion = 'Acceso mensual a Weather Pro Suite'

    # 1. Crear el objeto de pago
    site = settings.SITE_URL.rstrip('/')
    payment = paypalrestsdk.Payment({
        "intent": "sale",
        "payer": {
            "payment_method": "paypal"
        },
        "redirect_urls": {
            "return_url": f"{site}/paypal-retorno/",
            "cancel_url": f"{site}/pricing/"
        },
        "transactions": [{
            "item_list": {
                "items": [{
                    "name": nombre_item,
                    "sku": sku,
                    "price": precio,
                    "currency": "USD",
                    "quantity": 1
                }]
            },
            "amount": {
                "total": precio,
                "currency": "USD"
            },
            "description": descripcion
        }]
    })

    # 2. Enviar a PayPal
    if payment.create():
        for link in payment.links:
            if link.rel == "approval_url":
                return redirect(link.href)
    else:
        print(payment.error)
        return redirect('pricing')

@login_required
def paypal_retorno(request):
    # 3. El usuario volvió. Ahora EJECUTAMOS el cobro.
    payment_id = request.GET.get('paymentId')
    payer_id   = request.GET.get('PayerID')

    if payment_id and payer_id:
        payment = paypalrestsdk.Payment.find(payment_id)

        if payment.execute({"payer_id": payer_id}):
            plan = request.session.pop('plan_pago', 'mensual')
            dias = 365 if plan == 'anual' else 30
            activar_suscripcion_dias(request.user, dias, plan)
            return redirect('pago_exitoso_view')
        else:
            logger.error(f'[PAYPAL RETORNO] Error ejecutando pago: {payment.error}')

    # Si algo falló
    return redirect('pricing')


# ==========================================
# 5b. LEMON SQUEEZY
# ==========================================

@login_required
@login_required
def ls_checkout(request):
    """Crea una sesión de checkout en Lemon Squeezy via API y redirige a ella."""
    paquete_id = request.GET.get('paquete', '')
    paquete    = _PAQUETES_MAP.get(paquete_id)

    if not paquete or not paquete.get('ls_variant_id'):
        return redirect('recargar_tokens')

    api_key   = getattr(settings, 'LEMONSQUEEZY_API_KEY', '')
    store_id  = getattr(settings, 'LEMONSQUEEZY_STORE_ID', '')
    site      = settings.SITE_URL.rstrip('/')
    variant_id = paquete['ls_variant_id']

    # Si no hay store_id configurado (o es incorrecto), auto-detectarlo desde la API
    if api_key and not store_id:
        try:
            import urllib.request as _req2
            import json as _json2
            req2 = _req2.Request(
                'https://api.lemonsqueezy.com/v1/stores',
                headers={'Authorization': f'Bearer {api_key}', 'Accept': 'application/vnd.api+json'},
            )
            with _req2.urlopen(req2, timeout=8) as r2:
                stores_body = _json2.loads(r2.read().decode('utf-8'))
            store_id = stores_body['data'][0]['id']
            logger.info(f'[LS_CHECKOUT] Store ID auto-detectado: {store_id}')
        except Exception as e2:
            logger.error(f'[LS_CHECKOUT] Error obteniendo stores: {e2}')

    # Si la API key está configurada, crear checkout dinámico vía API (recomendado)
    if api_key and store_id:
        try:
            import urllib.request as _req
            import json as _json
            payload = _json.dumps({
                "data": {
                    "type": "checkouts",
                    "attributes": {
                        "checkout_data": {
                            "custom": {
                                "user_id": str(request.user.id),
                                "paquete_id": paquete_id,
                            }
                        },
                        "product_options": {
                            "redirect_url": f"{site}/ls-retorno/?paquete_id={paquete_id}",
                        },
                    },
                    "relationships": {
                        "store":   {"data": {"type": "stores",   "id": str(store_id)}},
                        "variant": {"data": {"type": "variants", "id": str(variant_id)}},
                    },
                }
            }).encode('utf-8')
            req = _req.Request(
                'https://api.lemonsqueezy.com/v1/checkouts',
                data=payload,
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Accept': 'application/vnd.api+json',
                    'Content-Type': 'application/vnd.api+json',
                },
                method='POST',
            )
            with _req.urlopen(req, timeout=8) as resp:
                body = _json.loads(resp.read().decode('utf-8'))
            checkout_url = body['data']['attributes']['url']
            return redirect(checkout_url)
        except Exception as e:
            logger.error(f'[LS_CHECKOUT] Error creando checkout vía API: {e}')
            from django.http import HttpResponse
            import urllib.error as _uerr
            detalle = str(e)
            if isinstance(e, _uerr.HTTPError):
                try:
                    detalle = e.read().decode('utf-8')
                except Exception:
                    pass
            return HttpResponse(
                f"<h2>Error en la API de Lemon Squeezy:</h2>"
                f"<p><b>store_id usado:</b> {store_id}</p>"
                f"<p><b>variant_id usado:</b> {variant_id}</p>"
                f"<pre>{detalle}</pre>"
            )


@login_required
def ls_retorno(request):
    """Página de retorno desde Lemon Squeezy. El webhook activa el plan en segundos."""
    # Intentar obtener el paquete del query param (viene del redirect_url de la API)
    paquete_id = request.GET.get('paquete_id', '')

    # Si no está en la URL, intentar recuperarlo de la sesión (fallback sin API)
    if not paquete_id:
        paquete_id = request.session.pop('ls_paquete_id_pendiente', '')
    else:
        request.session.pop('ls_paquete_id_pendiente', None)
    request.session.pop('ls_user_id_pendiente', None)

    paquete = _PAQUETES_MAP.get(paquete_id)
    return render(request, 'pago_exitoso_tokens.html', {
        'paquete':            paquete,
        'tokens_disponibles': request.user.perfil.tokens_disponibles,
    })


@csrf_exempt
def ls_webhook(request):
    """Webhook de Lemon Squeezy. Verifica HMAC-SHA256 y activa el plan de tokens."""
    if request.method != 'POST':
        return HttpResponse(status=200)

    # 1. Verificar firma
    secret = getattr(settings, 'LEMONSQUEEZY_WEBHOOK_SECRET', '').encode('utf-8')
    if secret:
        sig_header = request.headers.get('X-Signature', '')
        computed   = hmac.new(secret, request.body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(computed, sig_header):
            logger.warning('[LS WEBHOOK] Firma inválida')
            return HttpResponse(status=401)

    try:
        body  = json.loads(request.body.decode('utf-8'))
        event = body.get('meta', {}).get('event_name', '')

        if event != 'order_created':
            return HttpResponse(status=200)

        if body.get('data', {}).get('attributes', {}).get('status') != 'paid':
            return HttpResponse(status=200)

        custom     = body.get('meta', {}).get('custom_data', {})
        user_id    = custom.get('user_id')
        paquete_id = custom.get('paquete_id')

        if not user_id or not paquete_id:
            logger.warning(f'[LS WEBHOOK] Faltan custom_data: {custom}')
            return HttpResponse(status=200)

        paquete = _PAQUETES_MAP.get(paquete_id)
        if not paquete:
            logger.warning(f'[LS WEBHOOK] Paquete desconocido: {paquete_id}')
            return HttpResponse(status=200)

        user = User.objects.get(id=int(user_id))

        from .models import HistorialTokens
        ya_procesado = HistorialTokens.objects.filter(
            usuario=user,
            tipo='RECARGA',
            descripcion__icontains=paquete['nombre'],
            fecha__date=timezone.now().date(),
        ).exists()
        if not ya_procesado:
            meses_label = f"{paquete['meses']}m" + (f"+{paquete['regalo']}regalo" if paquete['regalo'] else '')
            user.perfil.activar_plan_tokens(
                paquete['tokens_dia'],
                paquete['dias'],
                f"Plan {paquete['nombre']} {meses_label} — {paquete['tokens_dia']:,} tokens/día",
            )
            logger.info(f"[LS WEBHOOK] Plan activado: {user.username} — {paquete_id}")

    except User.DoesNotExist:
        logger.error(f'[LS WEBHOOK] Usuario no encontrado: user_id={user_id}')
    except Exception as e:
        logger.error(f'[LS WEBHOOK] Error: {e}')

    return HttpResponse(status=200)


# ==========================================
# 6. SELECCIÓN DE PAGO Y TRANSFERENCIA
# ==========================================

@login_required
def metodos_pago(request):
    plan = request.GET.get('plan', 'mensual')
    if plan not in ('mensual', 'anual'):
        plan = 'mensual'
    precio = '200' if plan == 'anual' else '20'
    paypal_mode = os.getenv('PAYPAL_MODE', 'sandbox')
    return render(request, 'metodos_pago.html', {
        'plan': plan,
        'precio': precio,
        'paypal_sandbox': paypal_mode == 'sandbox',
    })

@login_required
def transferencia(request):
    plan = request.GET.get('plan', 'mensual')
    if plan not in ('mensual', 'anual'):
        plan = 'mensual'
    precio_usd = '200' if plan == 'anual' else '20'
    # Monto ARS referencial (el admin actualiza según cotización)
    monto_ars_brubank = '200000' if plan == 'anual' else '20000'
    monto_ars_mp = '200000' if plan == 'anual' else '20000'
    return render(request, 'transferencia.html', {
        'plan': plan,
        'precio_usd': precio_usd,
        'monto_ars_brubank': monto_ars_brubank,
        'monto_ars_mp': monto_ars_mp,
    })

@login_required
def confirmar_manual(request):
    # El usuario dice que ya hizo la transferencia.
    # No activamos todavía — le avisamos al admin por email.
    plan = request.GET.get('plan', 'mensual')
    precio = '$200 USD' if plan == 'anual' else '$20 USD'

    # Notificar al admin para que active manualmente
    try:
        send_mail(
            subject=f'[Weather PRO] Transferencia pendiente — {request.user.username}',
            message='',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=['climapro00@gmail.com'],
            fail_silently=True,
            html_message=f"""
            <div style="font-family:'Segoe UI',sans-serif;background:#0f172a;color:#fff;padding:30px;border-radius:12px;max-width:480px;margin:auto;">
                <h3 style="color:#f59e0b;">⏳ Transferencia pendiente de verificación</h3>
                <table style="width:100%;border-collapse:collapse;">
                    <tr><td style="color:#94a3b8;padding:6px 0;">Usuario</td><td style="color:#fff;font-weight:bold;">{request.user.username}</td></tr>
                    <tr><td style="color:#94a3b8;padding:6px 0;">Email</td><td style="color:#fff;">{request.user.email or '(sin email)'}</td></tr>
                    <tr><td style="color:#94a3b8;padding:6px 0;">Plan</td><td style="color:#fff;">{plan.capitalize()} — {precio}</td></tr>
                    <tr><td style="color:#94a3b8;padding:6px 0;">ID Usuario</td><td style="color:#fff;">{request.user.id}</td></tr>
                </table>
                <p style="margin-top:20px;color:#94a3b8;">Para activar ejecut\u00e1 en la shell:</p>
                <code style="background:#1e293b;color:#4ade80;padding:10px;display:block;border-radius:8px;font-size:0.85em;">
                    activar_suscripcion_dias(User.objects.get(id={request.user.id}), {'365' if plan == 'anual' else '30'}, '{plan}')
                </code>
            </div>
            """
        )
    except Exception as e:
        print(f"[CONFIRMAR_MANUAL] Error enviando mail admin: {e}")

    return render(request, 'pending.html', {'plan': plan})



def _enviar_mail_activacion(usuario, plan):
    """Envía un email de bienvenida/renovación al usuario tras activar su suscripción."""
    if not usuario.email:
        return
    plan_label = 'Anual (12 meses)' if plan == 'anual' else 'Mensual (30 días)'
    precio = '$200 USD' if plan == 'anual' else '$20 USD'
    try:
        send_mail(
            subject='✅ Tu suscripción Weather PRO está activa',
            message='',  # Usamos html_message
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[usuario.email],
            fail_silently=True,
            html_message=f"""
            <div style="font-family:'Segoe UI',sans-serif;background:#0f172a;color:#fff;padding:40px;border-radius:16px;max-width:500px;margin:auto;">
                <h2 style="color:#60a5fa;margin-bottom:4px;">Weather PRO</h2>
                <p style="color:#94a3b8;margin-top:0;">Plataforma Meteorológica Profesional</p>
                <hr style="border-color:#334155;">
                <h3 style="color:#4ade80;">✅ Suscripción Activada</h3>
                <p>Hola <strong>{usuario.username}</strong>, tu acceso PRO ya está disponible.</p>
                <table style="width:100%;border-collapse:collapse;margin:20px 0;">
                    <tr><td style="color:#94a3b8;padding:6px 0;">Plan</td><td style="color:#fff;font-weight:bold;">{plan_label}</td></tr>
                    <tr><td style="color:#94a3b8;padding:6px 0;">Precio</td><td style="color:#fff;">{precio}</td></tr>
                    <tr><td style="color:#94a3b8;padding:6px 0;">Acceso</td><td style="color:#4ade80;">Modo Agro · Aéreo · Naval · Energías + IA Gemini</td></tr>
                </table>
                <a href="{settings.SITE_URL}" style="display:inline-block;background:#3b82f6;color:#fff;padding:12px 28px;border-radius:10px;text-decoration:none;font-weight:bold;">Ir a la plataforma →</a>
                <p style="color:#475569;font-size:0.82em;margin-top:30px;">Si no realizaste este pago, contactanos en climapro00@gmail.com</p>
            </div>
            """
        )
    except Exception as e:
        print(f"[EMAIL] Error al enviar mail a {usuario.email}: {e}")


def activar_suscripcion_dias(usuario, dias, plan='mensual'):
    """Activa o extiende la suscripción del usuario por `dias` días."""
    from .models import TOKENS_DIARIOS_SUSCRIPCION
    perfil = usuario.perfil
    ahora = timezone.now()

    if perfil.fecha_vencimiento and perfil.fecha_vencimiento > ahora:
        perfil.fecha_vencimiento += timedelta(days=dias)
    else:
        perfil.fecha_vencimiento = ahora + timedelta(days=dias)

    perfil.plan_tipo = plan
    perfil.save()

    # Activar tokens diarios incluidos en el plan Pro
    perfil.activar_plan_tokens(
        TOKENS_DIARIOS_SUSCRIPCION,
        dias,
        f'Tokens incluidos en suscripción {plan} — {TOKENS_DIARIOS_SUSCRIPCION:,}/día'
    )

    _enviar_mail_activacion(usuario, plan)


def activar_30_dias(usuario):
    """Compatibilidad hacia atrás: activa plan mensual (30 días)."""
    activar_suscripcion_dias(usuario, 30, 'mensual')


# ============================================================
# MERCADOPAGO CHECKOUT PRO (pago automatizado)
# ============================================================

@login_required
def mp_crear_preferencia(request):
    """Crea una preferencia de pago en MP Checkout Pro y redirige al usuario."""
    plan = request.GET.get('plan', 'mensual')
    if plan not in ('mensual', 'anual'):
        plan = 'mensual'

    if plan == 'anual':
        titulo = 'Weather PRO — Plan Anual (12 meses)'
        precio = 200.0
    else:
        titulo = 'Weather PRO — Plan Mensual'
        precio = 20.0

    sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)
    site = settings.SITE_URL.rstrip('/')

    preference_data = {
        "items": [{
            "title": titulo,
            "quantity": 1,
            "unit_price": precio,
            "currency_id": "USD",
        }],
        "back_urls": {
            "success": f"{site}/mp-retorno/?plan={plan}&status=approved",
            "failure": f"{site}/pricing/",
            "pending": f"{site}/mp-retorno/?plan={plan}&status=pending",
        },
        "auto_return": "approved",
        # external_reference codifica usuario + plan para el webhook
        "external_reference": f"{request.user.id}_{plan}",
        "notification_url": f"{site}/mp-webhook/",
    }

    result = sdk.preference().create(preference_data)
    response = result.get("response", {})

    if result.get("status") in (200, 201) and "init_point" in response:
        return redirect(response["init_point"])

    # Si MP falla (ej: token no configurado), redirigir a transferencia manual
    print(f"[MP] Error creando preferencia: {result}")
    return redirect(f'/transferencia/?plan={plan}')


@csrf_exempt
def mp_webhook(request):
    """
    Webhook de MercadoPago. MP envía una notificación cuando un pago cambia de estado.
    Verifica el pago con la API de MP antes de activar la suscripción.
    """
    if request.method != 'POST':
        return HttpResponse(status=200)

    try:
        # MP puede enviar JSON en el body
        body = json.loads(request.body.decode('utf-8'))
        topic = body.get('type') or body.get('topic', '')
        payment_id = body.get('data', {}).get('id') or body.get('id')
    except Exception:
        topic = request.GET.get('topic', '')
        payment_id = request.GET.get('id')

    if topic not in ('payment', 'merchant_order') or not payment_id:
        return HttpResponse(status=200)

    try:
        sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)
        payment_info = sdk.payment().get(int(payment_id))

        if payment_info.get("status") != 200:
            return HttpResponse(status=200)

        payment = payment_info["response"]

        if payment.get("status") != "approved":
            return HttpResponse(status=200)

        external_ref = payment.get("external_reference", "")
        if not external_ref or "_" not in external_ref:
            return HttpResponse(status=200)

        partes = external_ref.split("_", 2)
        user_id_str = partes[0]
        user = User.objects.get(id=int(user_id_str))

        # ¿Es compra de tokens? (external_reference: "123_tk_tokens_estandar")
        if len(partes) >= 3 and partes[1] == 'tk':
            paquete_id = partes[2]
            paquete = _PAQUETES_MAP.get(paquete_id)
            if not paquete:
                return HttpResponse(status=200)
            from .models import HistorialTokens
            ya_procesado = HistorialTokens.objects.filter(
                usuario=user,
                tipo='RECARGA',
                descripcion__icontains=paquete['nombre'],
                fecha__date=timezone.now().date(),
            ).exists()
            if not ya_procesado:
                meses_label = f"{paquete['meses']}m" + (f"+{paquete['regalo']}regalo" if paquete['regalo'] else '')
                user.perfil.activar_plan_tokens(
                    paquete['tokens_dia'],
                    paquete['dias'],
                    f"Plan {paquete['nombre']} {meses_label} — {paquete['tokens_dia']:,} tokens/día",
                )
                logger.info(f"[MP WEBHOOK] Plan tokens activado: {user.username} — {paquete['nombre']} {meses_label}")
            return HttpResponse(status=200)

        # Es suscripción mensual/anual (external_reference: "123_mensual" o "123_anual")
        plan = partes[1]
        dias = 365 if plan == 'anual' else 30

        # Idempotencia: rechazamos si el payment_id ya fue procesado
        # (guardamos el id en la sesión no aplica en webhook; usamos fecha como proxy:
        # si el usuario ya tiene más de `dias` días desde ahora, probablemente ya se processó)
        # La forma más simple: activar_suscripcion_dias ya maneja la lógica de extensión correctamente,
        # así que una doble llamada solo extiende una vez más. Para evitar eso,
        # chequeamos si la fecha de vencimiento ya supera el tiempo esperado.
        perfil = user.perfil
        ahora = timezone.now()
        limite = ahora + timedelta(days=dias)
        if perfil.fecha_vencimiento and perfil.fecha_vencimiento >= limite:
            print(f"[MP WEBHOOK] Pago ya procesado para {user.username}, ignorando.")
            return HttpResponse(status=200)

        activar_suscripcion_dias(user, dias, plan)
        print(f"[MP WEBHOOK] Suscripción activada: {user.username} — plan {plan}")

    except User.DoesNotExist:
        print(f"[MP WEBHOOK] Usuario no encontrado para external_reference={external_ref}")
    except Exception as e:
        print(f"[MP WEBHOOK] Error: {e}")

    # Siempre responder 200 para que MP no reintente
    return HttpResponse(status=200)


@login_required
def mp_retorno(request):
    """Pantalla de retorno desde MP Checkout (fallback si el webhook tarda)."""
    status     = request.GET.get('status', '')
    plan       = request.GET.get('plan', 'mensual')
    payment_id = request.GET.get('payment_id') or request.GET.get('collection_id')

    if status == 'approved':
        # Verificar el pago directamente con la API de MP antes de activar
        pago_verificado = False
        if payment_id:
            try:
                sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)
                payment_info = sdk.payment().get(int(payment_id))
                if payment_info.get('status') == 200:
                    payment = payment_info['response']
                    ext_ref = payment.get('external_reference', '')
                    # Verificar que el pago es de este usuario y está realmente aprobado
                    if (payment.get('status') == 'approved'
                            and ext_ref.startswith(f"{request.user.id}_")):
                        pago_verificado = True
            except Exception as e:
                logger.error(f'[MP RETORNO] Error verificando pago {payment_id}: {e}')

        if pago_verificado:
            # Activar solo si el webhook todavía no lo hizo
            perfil = request.user.perfil
            ahora  = timezone.now()
            dias   = 365 if plan == 'anual' else 30
            limite = ahora + timedelta(days=dias - 1)  # margen de 1 día
            if not perfil.fecha_vencimiento or perfil.fecha_vencimiento < limite:
                activar_suscripcion_dias(request.user, dias, plan)
            return redirect('pago_exitoso_view')
        else:
            logger.warning(f'[MP RETORNO] Pago no verificado para usuario {request.user.id}, payment_id={payment_id}')
            return redirect('pricing')

    if status == 'pending':
        return render(request, 'pending.html', {'plan': plan, 'metodo': 'mercadopago'})

    return redirect('pricing')


@login_required
def pago_exitoso(request):
    # Fallback legacy para MercadoPago redirect con collection_status.
    # Verifica el pago con la API de MP antes de activar la suscripción.
    status     = request.GET.get('collection_status')
    payment_id = request.GET.get('collection_id') or request.GET.get('payment_id')
    plan       = request.GET.get('plan', request.session.get('plan_pago', 'mensual'))
    if plan not in ('mensual', 'anual'):
        plan = 'mensual'

    if status == 'approved' and payment_id:
        pago_verificado = False
        try:
            sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)
            payment_info = sdk.payment().get(int(payment_id))
            if payment_info.get('status') == 200:
                payment = payment_info['response']
                ext_ref = payment.get('external_reference', '')
                if (payment.get('status') == 'approved'
                        and ext_ref.startswith(f"{request.user.id}_")):
                    pago_verificado = True
        except Exception as e:
            logger.error(f'[PAGO_EXITOSO LEGACY] Error verificando pago {payment_id}: {e}')

        if pago_verificado:
            request.session.pop('plan_pago', None)
            dias = 365 if plan == 'anual' else 30
            perfil = request.user.perfil
            ahora  = timezone.now()
            limite = ahora + timedelta(days=dias - 1)
            if not perfil.fecha_vencimiento or perfil.fecha_vencimiento < limite:
                activar_suscripcion_dias(request.user, dias, plan)
            return redirect('pago_exitoso_view')
        else:
            logger.warning(f'[PAGO_EXITOSO LEGACY] Pago no verificado, usuario {request.user.id}, payment_id={payment_id}')

    return redirect('pricing')


@login_required
def pago_exitoso_view(request):
    """Pantalla de confirmación que se muestra tras cualquier pago aprobado."""
    perfil = request.user.perfil
    plan_label = 'Anual (12 meses)' if perfil.plan_tipo == 'anual' else 'Mensual (30 días)'
    vencimiento = perfil.fecha_vencimiento.strftime('%d/%m/%Y') if perfil.fecha_vencimiento else '—'
    return render(request, 'pago_exitoso.html', {
        'plan_label': plan_label,
        'vencimiento': vencimiento,
    })




# ==========================================
# 7. SISTEMA DE USUARIOS (LOGIN / REGISTRO)
# ==========================================

def registro(request):
    if request.method == 'POST':
        form = RegistroConEmailForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Guardar email en el modelo User
            user.email = form.cleaned_data['email']
            user.save()
            # Creamos el perfil vacio al registrarse
            PerfilUsuario.objects.create(user=user)
            login(request, user)
            return redirect('pricing')
    else:
        form = RegistroConEmailForm()
    return render(request, 'registro.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('home')





# VISTA GLOBAL PARA RECIBIR FEEDBACK
def procesar_reporte(request):
    if request.method == "POST" and request.user.is_authenticated:
        # 1. Obtenemos los datos
        tipo = request.POST.get('tipo_reporte')
        texto = request.POST.get('mensaje_reporte')
        
        # 2. Guardamos en la Base de Datos (Modelo Global)
        ReporteUsuario.objects.create(
            usuario=request.user,
            tipo=tipo,
            mensaje=texto
        )
        
        # 3. Redirección Inteligente:
        # Volvemos a la misma página desde donde vino el usuario (Standard o Pro)
        # y le agregamos una marca '?enviado=ok' para mostrar el cartel verde.
        referer = request.META.get('HTTP_REFERER', '/')
        if '?' in referer:
            return HttpResponseRedirect(referer + '&enviado=ok')
        else:
            return HttpResponseRedirect(referer + '?enviado=ok')
    
    # Si alguien intenta entrar por error, lo mandamos al inicio
    return redirect('home')


def ayuda(request):
    # Detectamos si viene con el mensaje de éxito (?enviado=ok)
    mostrar_exito = request.GET.get('enviado') == 'ok'
    
    context = {
        'mostrar_exito': mostrar_exito
    }
    return render(request, 'ayuda.html', context)


def ciencia(request):
    return render(request, 'ciencia.html')


def mapas(request):
    # Configuración Global
    context = {
        'lat': 20.0,   # Latitud central (Norte de África/Atlántico)
        'lon': -40.0,  # Longitud central (Entre América y Europa)
        'zoom': 3      # <--- Zoom 3: Ideal para ver continentes enteros
    }
    return render(request, 'mapas.html', context)




def legal(request):
    return render(request, 'legal.html')


# --- NUEVA FUNCIONALIDAD: PROCESAMIENTO MULTISECTORIAL ---

def detectar_sector_ia(contenido_archivo, nombre_archivo):
    """
    Detecta automáticamente el sector basándose en el contenido del archivo usando IA
    """
    try:
        # Configurar OpenAI (asegúrate de tener la API key en las variables de entorno)
        openai.api_key = os.getenv('OPENAI_API_KEY')
        
        # Prompt para clasificación sectorial
        prompt = f"""
        Analiza el siguiente contenido de archivo y determina a cuál de estos sectores pertenece:
        - NAVAL: Datos marítimos, oceanográficos, navegación, puertos
        - ENERGIA: Datos energéticos, eléctricos, renovables, consumo energético  
        - AEREO: Datos aeronáuticos, meteorológicos de aviación, tráfico aéreo
        - AGRO: Datos agrícolas, ganaderos, cultivos, suelos, clima rural
        
        Nombre del archivo: {nombre_archivo}
        
        Contenido (primeros 1000 caracteres):
        {contenido_archivo[:1000]}
        
        Responde ÚNICAMENTE con una de estas palabras: NAVAL, ENERGIA, AEREO, AGRO
        """
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0.1
        )
        
        sector_detectado = response.choices[0].message.content.strip().upper()
        
        # Validar que la respuesta esté en los sectores válidos
        sectores_validos = ['NAVAL', 'ENERGIA', 'AEREO', 'AGRO']
        if sector_detectado in sectores_validos:
            return sector_detectado
        else:
            # Si no puede detectar, usar lógica de palabras clave como fallback
            return detectar_sector_palabras_clave(contenido_archivo, nombre_archivo)
            
    except Exception as e:
        logger.error(f"Error en detección IA: {str(e)}")
        # Fallback a detección por palabras clave
        return detectar_sector_palabras_clave(contenido_archivo, nombre_archivo)


def detectar_sector_palabras_clave(contenido, nombre_archivo):
    """
    Detección de sector por palabras clave como fallback
    """
    contenido_lower = (contenido + " " + nombre_archivo).lower()
    
    # Palabras clave por sector
    palabras_naval = ['naval', 'mar', 'oceano', 'puerto', 'barco', 'navegacion', 'marea', 'ola', 'salinidad']
    palabras_energia = ['energia', 'electrico', 'voltaje', 'potencia', 'solar', 'eolico', 'kwh', 'consumo']
    palabras_aereo = ['aereo', 'avion', 'vuelo', 'altitud', 'presion', 'turbulencia', 'aeropuerto', 'meteorologia']
    palabras_agro = ['agro', 'cultivo', 'suelo', 'humedad', 'agricola', 'cosecha', 'ganado', 'rural', 'campo']
    
    # Contar coincidencias
    score_naval = sum(1 for palabra in palabras_naval if palabra in contenido_lower)
    score_energia = sum(1 for palabra in palabras_energia if palabra in contenido_lower)
    score_aereo = sum(1 for palabra in palabras_aereo if palabra in contenido_lower)
    score_agro = sum(1 for palabra in palabras_agro if palabra in contenido_lower)
    
    # Retornar el sector con mayor score
    scores = {'NAVAL': score_naval, 'ENERGIA': score_energia, 'AEREO': score_aereo, 'AGRO': score_agro}
    sector_detectado = max(scores, key=scores.get)
    
    # Si no hay coincidencias claras, defaultear a AGRO
    if scores[sector_detectado] == 0:
        return 'AGRO'
    
    return sector_detectado


def generar_analisis_ia(contenido, sector, metadatos):
    """
    Genera análisis con IA basado en el sector y contenido
    """
    try:
        openai.api_key = os.getenv('OPENAI_API_KEY')
        
        prompt = f"""
        Actúa como experto en el sector {sector}. Analiza los siguientes datos y proporciona un análisis detallado:
        
        Sector: {sector}
        Metadatos: {json.dumps(metadatos, indent=2)}
        
        Contenido del archivo (muestra):
        {contenido[:2000]}
        
        Proporciona un análisis de máximo 500 palabras que incluya:
        1. Resumen de los datos
        2. Tendencias identificadas
        3. Alertas o recomendaciones específicas del sector
        4. Impacto potencial
        """
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.3
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"Error generando análisis IA: {str(e)}")
        return f"Análisis automático para sector {sector}. Datos procesados correctamente. Revisar manualmente para análisis detallado."


def extraer_metadatos_por_sector(datos_df, sector):
    """
    Extrae metadatos específicos según el sector
    """
    metadatos = {}
    
    if sector == 'ENERGIA':
        metadatos.update({
            'voltaje': datos_df.get('voltaje', datos_df.get('voltage', None)),
            'frecuencia': datos_df.get('frecuencia', datos_df.get('frequency', None)),
            'potencia': datos_df.get('potencia', datos_df.get('power', None)),
            'factor_potencia': datos_df.get('factor_potencia', None)
        })
    elif sector == 'AEREO':
        metadatos.update({
            'altitud': datos_df.get('altitud', datos_df.get('altitude', None)),
            'presion_atmosferica': datos_df.get('presion', datos_df.get('pressure', None)),
            'visibilidad': datos_df.get('visibilidad', datos_df.get('visibility', None)),
            'turbulencia': datos_df.get('turbulencia', datos_df.get('turbulence', None))
        })
    elif sector == 'AGRO':
        metadatos.update({
            'humedad_suelo': datos_df.get('humedad_suelo', datos_df.get('soil_moisture', None)),
            'ph_suelo': datos_df.get('ph', datos_df.get('ph_suelo', None)),
            'nutrientes': datos_df.get('nutrientes', datos_df.get('nutrients', None)),
            'tipo_cultivo': datos_df.get('cultivo', datos_df.get('crop_type', None))
        })
    elif sector == 'NAVAL':
        metadatos.update({
            'altura_olas': datos_df.get('altura_olas', datos_df.get('wave_height', None)),
            'corriente_marina': datos_df.get('corriente', datos_df.get('current', None)),
            'salinidad': datos_df.get('salinidad', datos_df.get('salinity', None)),
            'marea': datos_df.get('marea', datos_df.get('tide', None))
        })
    
    # Limpiar valores None
    return {k: v for k, v in metadatos.items() if v is not None}


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def procesar_archivo_sectorial(request):
    """
    Vista principal para procesar archivos y detectar sector automáticamente
    """
    try:
        # --- Verificar permisos de plan ---
        if request.user.is_authenticated:
            perfil = request.user.perfil
            if not perfil.puede_devorador:
                return JsonResponse({
                    'error': 'plan_insuficiente',
                    'mensaje': 'La subida de archivos está disponible desde el plan Plus. Actualizá tu plan en /pricing/.',
                    'plan_nivel': perfil.plan_nivel,
                }, status=403)

        # --- Verificar tokens disponibles ---
        from .models import COSTO_TOKENS
        if request.user.is_authenticated:
            perfil = request.user.perfil
            costo = COSTO_TOKENS['ANALISIS_ARCHIVO']
            if not perfil.tiene_tokens(costo):
                return JsonResponse({
                    'error': 'tokens_insuficientes',
                    'mensaje': f'No tenés créditos suficientes para procesar un archivo ({costo:,} créditos requeridos). Podés recargar desde tu cuenta.',
                    'tokens_disponibles': perfil.tokens_disponibles,
                    'costo': costo,
                }, status=402)

        # Verificar que se enviñ un archivo
        if 'archivo' not in request.FILES:
            return JsonResponse({'error': 'No se proporcionó ningún archivo'}, status=400)
        
        archivo = request.FILES['archivo']
        
        # Validar tipo de archivo
        tipos_permitidos = ['.csv', '.json', '.txt', '.xlsx', '.xls']
        extension = os.path.splitext(archivo.name)[1].lower()
        if extension not in tipos_permitidos:
            return JsonResponse({'error': f'Tipo de archivo no permitido. Use: {tipos_permitidos}'}, status=400)
        
        # Leer contenido del archivo
        contenido = archivo.read().decode('utf-8')
        
        # Detectar sector automáticamente
        sector = detectar_sector_ia(contenido, archivo.name)
        
        # Procesar datos según tipo de archivo
        try:
            if extension == '.csv':
                df = pd.read_csv(io.StringIO(contenido))
                datos_dict = df.to_dict('records')[0] if not df.empty else {}
            elif extension == '.json':
                datos_dict = json.loads(contenido)
            else:
                # Para otros tipos, crear estructura básica
                datos_dict = {'contenido': contenido[:1000]}
            
            # Extraer valores principales
            valor_principal = 0
            valor_secundario = None
            ubicacion = "Sin especificar"
            
            # Buscar valores numéricos en los datos
            for key, value in datos_dict.items():
                if isinstance(value, (int, float)):
                    if valor_principal == 0:
                        valor_principal = value
                    elif valor_secundario is None:
                        valor_secundario = value
                
                # Buscar ubicación
                if 'ubicacion' in key.lower() or 'location' in key.lower() or 'lugar' in key.lower():
                    ubicacion = str(value)
            
            # Extraer metadatos específicos del sector
            metadatos = extraer_metadatos_por_sector(datos_dict, sector)
            metadatos['archivo_original'] = archivo.name
            metadatos['timestamp_procesamiento'] = timezone.now().isoformat()
            
            # Generar análisis con IA
            analisis_ia = generar_analisis_ia(contenido, sector, metadatos)
            
            # Crear registro en base de datos
            dato_sectorial = DatoSectorial.objects.create(
                sector=sector,
                valor_principal=valor_principal,
                valor_secundario=valor_secundario,
                ubicacion=ubicacion,
                analisis_ia=analisis_ia,
                metadatos=metadatos,
                archivo_origen=archivo.name,
                usuario_carga=request.user
            )
            
            # Enviar a BigQuery
            exito, mensaje = dato_sectorial.enviar_a_bigquery()

            # --- Descontar tokens tras procesamiento exitoso ---
            if request.user.is_authenticated:
                from .models import COSTO_TOKENS
                request.user.perfil.descontar_tokens(
                    COSTO_TOKENS['ANALISIS_ARCHIVO'],
                    f'Análisis archivo: {archivo.name} (sector {sector})'
                )

            return JsonResponse({
                'success': True,
                'id': dato_sectorial.id,
                'sector': sector,
                'analisis': analisis_ia,
                'bigquery_success': exito,
                'bigquery_mensaje': mensaje,
                'metadatos': metadatos,
                'tokens_restantes': request.user.perfil.tokens_disponibles if request.user.is_authenticated else None,
                'mensaje': f'Archivo procesado exitosamente. Sector detectado: {sector}'
            })
            
        except Exception as e:
            logger.error(f"Error procesando datos: {str(e)}")
            return JsonResponse({'error': f'Error procesando archivo: {str(e)}'}, status=500)
            
    except Exception as e:
        logger.error(f"Error en procesar_archivo_sectorial: {str(e)}")
        return JsonResponse({'error': f'Error general: {str(e)}'}, status=500)


@login_required  
def vista_carga_archivos(request):
    """
    Vista para renderizar la página de carga de archivos sectoriales
    """
    context = {
        'sectores': DatoSectorial.SECTORES,
        'usuarios_recientes': DatoSectorial.objects.filter(usuario_carga=request.user)[:10]
    }
    return render(request, 'carga_sectorial.html', context)


# --- FUNCIONES PARA ENVÍO A WEBHOOKS N8N ---

def enviar_a_webhook_n8n(sector, datos, user_id=None, session_id=None):
    """
    Envía datos a los webhooks de n8n según el sector
    """
    # URLs de webhooks desde variables de entorno
    urls_webhooks = {
        'NAVAL': os.getenv('N8N_WEBHOOK_NAVAL'),
        'AGRO': os.getenv('N8N_WEBHOOK_AGRO'),
        'AEREO': os.getenv('N8N_WEBHOOK_AEREO'),
        'ENERGIA': os.getenv('N8N_WEBHOOK_ENERGIA')
    }
    
    webhook_url = urls_webhooks.get(sector)
    if not webhook_url:
        logger.error(f"No hay URL de webhook configurada para sector: {sector}")
        return False, f"URL de webhook no configurada para {sector}"
    
    try:
        # Preparar payload
        payload = {
            'sector': sector,
            'timestamp': datetime.now().isoformat(),
            'source': 'django-app',
            'sessionId': session_id,
            'user_id': user_id,
            'data': datos
        }
        
        # Headers — incluye secreto compartido para que n8n rechace llamadas externas
        n8n_secret = os.getenv('N8N_WEBHOOK_SECRET', '')
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Django-ClimaApp/1.0',
            'X-N8N-Secret': n8n_secret,
        }
        
        # Enviar POST request
        response = requests.post(
            webhook_url,
            json=payload,
            headers=headers,
            timeout=30,
        )
        
        if response.status_code == 200:
            logger.info(f"Datos enviados exitosamente a webhook {sector}: {webhook_url}")
            return True, f"Enviado exitosamente a n8n {sector}"
        else:
            logger.error(f"Error HTTP {response.status_code} enviando a {sector}: {response.text}")
            return False, f"Error HTTP {response.status_code}: {response.text}"
            
    except requests.exceptions.Timeout:
        logger.error(f"Timeout enviando a webhook {sector}")
        return False, "Timeout en conexión con n8n"
    except requests.exceptions.ConnectionError:
        logger.error(f"Error de conexión con webhook {sector}")
        return False, "Error de conexión con n8n"
    except Exception as e:
        logger.error(f"Error inesperado enviando a webhook {sector}: {str(e)}")
        return False, f"Error inesperado: {str(e)}"


def probar_webhooks_n8n():
    """
    Función para probar conectividad con todos los webhooks
    """
    sectores = ['NAVAL', 'AGRO', 'AEREO', 'ENERGIA']
    resultados = {}
    
    for sector in sectores:
        # Datos de prueba por sector
        datos_prueba = generar_datos_prueba(sector)
        exito, mensaje = enviar_a_webhook_n8n(sector, datos_prueba)
        
        resultados[sector] = {
            'exito': exito,
            'mensaje': mensaje,
            'url': os.getenv(f'N8N_WEBHOOK_{sector}')
        }
    
    return resultados


def generar_datos_prueba(sector):
    """
    Genera datos de prueba específicos para cada sector
    """
    timestamp = datetime.now().isoformat()
    
    if sector == 'NAVAL':
        return {
            'ubicacion': 'Puerto de Prueba',
            'olas_altura': 2.5,
            'viento_velocidad': 15.5,
            'presion': 1013.25,
            'analisis_ia': 'Datos de prueba para sector naval generados desde Django',
            'modo_prueba': True
        }
    elif sector == 'AGRO':
        return {
            'ubicacion': 'Campo de Prueba',
            'humedad_suelo': 65.0,
            'ph_suelo': 6.8,
            'temperatura': 22.5,
            'analisis_ia': 'Datos de prueba para sector agrícola generados desde Django',
            'modo_prueba': True
        }
    elif sector == 'AEREO':
        return {
            'ubicacion': 'Aeropuerto de Prueba',
            'altitud': 10000,
            'presion_atmosferica': 1013.25,
            'visibilidad': '15 km',
            'analisis_ia': 'Datos de prueba para sector aéreo generados desde Django',
            'modo_prueba': True
        }
    elif sector == 'ENERGIA':
        return {
            'ubicacion': 'Central de Prueba',
            'voltaje': 220.0,
            'potencia': 1500.0,
            'frecuencia': 50.0,
            'analisis_ia': 'Datos de prueba para sector energético generados desde Django',
            'modo_prueba': True
        }
    
    return {'modo_prueba': True, 'timestamp': timestamp}


@csrf_exempt
@require_http_methods(["GET", "POST"])
@login_required
def probar_conexion_n8n(request):
    """
    Vista para probar conexión con todos los webhooks de n8n
    """
    if request.method == 'GET':
        # Renderizar página de prueba
        context = {
            'webhooks': {
                'NAVAL': os.getenv('N8N_WEBHOOK_NAVAL'),
                'AGRO': os.getenv('N8N_WEBHOOK_AGRO'),
                'AEREO': os.getenv('N8N_WEBHOOK_AEREO'),
                'ENERGIA': os.getenv('N8N_WEBHOOK_ENERGIA')
            }
        }
        return render(request, 'prueba_n8n.html', context)
    
    elif request.method == 'POST':
        # Ejecutar pruebas
        try:
            resultados = probar_webhooks_n8n()
            return JsonResponse({
                'success': True,
                'resultados': resultados,
                'mensaje': 'Pruebas de webhooks completadas'
            })
        except Exception as e:
            logger.error(f"Error en prueba de webhooks: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@csrf_exempt  
@require_http_methods(["POST"])
@login_required
def enviar_dato_sectorial_a_n8n(request):
    """
    Vista para enviar un DatoSectorial específico a n8n
    """
    try:
        # --- Verificar tokens disponibles ---
        from .models import COSTO_TOKENS
        if request.user.is_authenticated:
            perfil = request.user.perfil
            costo = COSTO_TOKENS['CHAT_N8N']
            if not perfil.tiene_tokens(costo):
                return JsonResponse({
                    'error': 'tokens_insuficientes',
                    'mensaje': f'No tenés créditos suficientes para consultar la IA ({costo:,} créditos requeridos). Podés recargar desde tu cuenta.',
                    'tokens_disponibles': perfil.tokens_disponibles,
                    'costo': costo,
                }, status=402)

        data = json.loads(request.body)
        dato_id = data.get('dato_id')
        
        if not dato_id:
            return JsonResponse({'error': 'ID de dato requerido'}, status=400)
        
        # Obtener el dato sectorial
        dato = DatoSectorial.objects.get(id=dato_id, usuario_carga=request.user)
        
        # Preparar datos para envío
        datos_envio = {
            'id': dato.id,
            'ubicacion': dato.ubicacion,
            'valor_principal': dato.valor_principal,
            'valor_secundario': dato.valor_secundario,
            'analisis_ia': dato.analisis_ia,
            'metadatos': dato.metadatos,
            'fecha_registro': dato.fecha_registro.isoformat(),
            'archivo_origen': dato.archivo_origen
        }
        
        # Enviar a webhook n8n
        exito, mensaje = enviar_a_webhook_n8n(
            dato.sector,
            datos_envio,
            user_id=request.user.id if request.user.is_authenticated else None,
            session_id=request.session.session_key,
        )
        
        # --- Descontar tokens tras envío exitoso ---
        if exito and request.user.is_authenticated:
            from .models import COSTO_TOKENS
            request.user.perfil.descontar_tokens(
                COSTO_TOKENS['CHAT_N8N'],
                f'Consulta IA n8n — sector {dato.sector}'
            )

        return JsonResponse({
            'success': exito,
            'mensaje': mensaje,
            'sector': dato.sector,
            'dato_id': dato.id,
            'tokens_restantes': request.user.perfil.tokens_disponibles if request.user.is_authenticated else None,
        })

    except DatoSectorial.DoesNotExist:
        return JsonResponse({'error': 'Dato no encontrado'}, status=404)
    except Exception as e:
        logger.error(f"Error enviando dato a n8n: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


# ==========================================
# SISTEMA DE TOKENS IA
# ==========================================

@login_required
def api_saldo_tokens(request):
    """Devuelve el saldo de tokens del usuario autenticado."""
    from .models import COSTO_TOKENS, HistorialTokens
    perfil = request.user.perfil
    perfil._reset_diario_si_necesario()
    historial = HistorialTokens.objects.filter(usuario=request.user)[:10]
    return JsonResponse({
        'tokens_disponibles': perfil.tokens_disponibles,
        'tokens_diarios_limite': perfil.tokens_diarios_limite,
        'tokens_usados_total': perfil.tokens_usados_total,
        'plan_activo': bool(perfil.tokens_diarios_limite),
        'fecha_vencimiento_tokens': perfil.fecha_vencimiento_tokens.strftime('%Y-%m-%d') if perfil.fecha_vencimiento_tokens else None,
        'costos': COSTO_TOKENS,
        'historial': [
            {
                'tipo': h.tipo,
                'cantidad': h.cantidad,
                'descripcion': h.descripcion,
                'tokens_restantes': h.tokens_restantes,
                'fecha': h.fecha.strftime('%Y-%m-%d %H:%M'),
            }
            for h in historial
        ],
    })


@login_required
def admin_recargar_tokens(request):
    """
    Vista exclusiva para staff/admin que otorga tokens a un usuario.
    POST: { "username": "...", "cantidad": 50000, "descripcion": "..." }
    """
    if not request.user.is_staff:
        return JsonResponse({'error': 'Acceso denegado'}, status=403)

    try:
        data = json.loads(request.body)
        username   = data.get('username')
        cantidad   = int(data.get('cantidad', 0))
        descripcion = data.get('descripcion', 'Recarga manual por administrador')

        if not username or cantidad <= 0:
            return JsonResponse({'error': 'Parámetros inválidos (username requerido, cantidad > 0)'}, status=400)

        target_user = User.objects.get(username=username)
        target_user.perfil.recargar_tokens(cantidad, descripcion)

        return JsonResponse({
            'success': True,
            'usuario': username,
            'tokens_agregados': cantidad,
            'tokens_disponibles': target_user.perfil.tokens_disponibles,
        })
    except User.DoesNotExist:
        return JsonResponse({'error': 'Usuario no encontrado'}, status=404)
    except Exception as e:
        logger.error(f"Error recargando tokens: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


# Planes de tokens con variantes de duración (1, 3 y 6 meses)
# Cada variante: meses pagados + meses de regalo = días de acceso total
PLANES_TOKENS = [
    {
        'id':          'starter',
        'nombre':      'Starter',
        'tokens_dia':  42_000,  # ~14 mensajes/día (chat normal)
        'icono':       '⚡',
        'icono_fa':    {'fa': 'bolt',   'color': '#f59e0b', 'color2': '#fb923c', 'bg': 'rgba(245,158,11,.12)'},
        'popular':     False,
        'descripcion': 'Para uso diario moderado',
        'variantes': [
            {'sufijo': '1m', 'meses': 1, 'regalo': 0, 'dias': 30,  'precio': 20.0,  'ls_variant_id': '1404219'},
            {'sufijo': '3m', 'meses': 3, 'regalo': 1, 'dias': 120, 'precio': 60.0,  'ls_variant_id': '1404160'},
            {'sufijo': '6m', 'meses': 6, 'regalo': 2, 'dias': 240, 'precio': 120.0, 'ls_variant_id': '1404236'},
        ],
    },
    {
        'id':          'plus',
        'nombre':      'Plus',
        'tokens_dia':  75_000,  # ~25 mensajes/día (chat normal)
        'icono':       '🚀',
        'icono_fa':    {'fa': 'rocket', 'color': '#3b82f6', 'color2': '#818cf8', 'bg': 'rgba(59,130,246,.12)'},
        'popular':     True,
        'descripcion': 'Ideal para análisis frecuentes',
        'variantes': [
            {'sufijo': '1m', 'meses': 1, 'regalo': 0, 'dias': 30,  'precio': 35.0,  'ls_variant_id': '1404246'},
            {'sufijo': '3m', 'meses': 3, 'regalo': 1, 'dias': 120, 'precio': 105.0, 'ls_variant_id': '1404247'},
            {'sufijo': '6m', 'meses': 6, 'regalo': 2, 'dias': 240, 'precio': 210.0, 'ls_variant_id': '1404252'},
        ],
    },
    {
        'id':          'pro_ia',
        'nombre':      'Pro IA',
        'tokens_dia':  150_000, # ~50 mensajes/día (chat normal)
        'icono':       '💎',
        'icono_fa':    {'fa': 'gem',    'color': '#a855f7', 'color2': '#ec4899', 'bg': 'rgba(168,85,247,.12)'},
        'popular':     False,
        'descripcion': 'Para usuarios intensivos',
        'variantes': [
            {'sufijo': '1m', 'meses': 1, 'regalo': 0, 'dias': 30,  'precio': 75.0,  'ls_variant_id': '1404261'},
            {'sufijo': '3m', 'meses': 3, 'regalo': 1, 'dias': 120, 'precio': 225.0, 'ls_variant_id': '1404272'},
            {'sufijo': '6m', 'meses': 6, 'regalo': 2, 'dias': 240, 'precio': 450.0, 'ls_variant_id': '1404275'},
        ],
    },
    {
        'id':          'power',
        'nombre':      'Power',
        'tokens_dia':  300_000, # ~100 mensajes/día (chat normal)
        'icono':       '🌟',
        'icono_fa':    {'fa': 'star',   'color': '#eab308', 'color2': '#f59e0b', 'bg': 'rgba(234,179,8,.12)'},
        'popular':     False,
        'descripcion': 'Máxima capacidad — ideal para empresas',
        'variantes': [
            {'sufijo': '1m', 'meses': 1, 'regalo': 0, 'dias': 30,  'precio': 150.0, 'ls_variant_id': '1404277'},
            {'sufijo': '3m', 'meses': 3, 'regalo': 1, 'dias': 120, 'precio': 450.0, 'ls_variant_id': '1404280'},
            {'sufijo': '6m', 'meses': 6, 'regalo': 2, 'dias': 240, 'precio': 900.0, 'ls_variant_id': '1404282'},
        ],
    },
]

# Mapa plano id → datos completos para lookup rápido en webhook/retorno
_PAQUETES_MAP = {}
for _plan in PLANES_TOKENS:
    for _v in _plan['variantes']:
        _key = f"{_plan['id']}_{_v['sufijo']}"
        _PAQUETES_MAP[_key] = {
            'id':            _key,
            'nombre':        _plan['nombre'],
            'tokens_dia':    _plan['tokens_dia'],
            'icono':         _plan['icono'],
            'icono_fa':      _plan['icono_fa'],
            'bg':            _plan['icono_fa']['bg'],
            'descripcion':   _plan['descripcion'],
            'meses':         _v['meses'],
            'regalo':        _v['regalo'],
            'dias':          _v['dias'],
            'precio':        _v['precio'],
            'ls_variant_id': _v.get('ls_variant_id', ''),
        }


@login_required
def seleccionar_pago_tokens(request):
    """Página de selección de método de pago para un plan de tokens."""
    paquete_id = request.GET.get('paquete', '')
    paquete    = _PAQUETES_MAP.get(paquete_id)
    if not paquete:
        return redirect('/pricing/#tokens')

    # Tipo de cambio referencial ARS (actualizar según cotización)
    ARS_POR_USD = 1000
    monto_ars = int(paquete['precio'] * ARS_POR_USD)
    monto_ars_fmt = f"{monto_ars:,}".replace(',', '.')

    meses_label = f"{paquete['meses']} mes{'es' if paquete['meses'] > 1 else ''}"
    regalo_label = f" + {paquete['regalo']} de regalo" if paquete['regalo'] else ''

    return render(request, 'pago_tokens.html', {
        'paquete':     paquete,
        'paquete_id':  paquete_id,
        'monto_ars':   monto_ars_fmt,
        'precio_usd':  int(paquete['precio']),
        'periodo':     meses_label + regalo_label,
    })


@login_required
def confirmar_manual_tokens(request):
    """El usuario declara haber transferido para un plan de tokens."""
    paquete_id = request.GET.get('paquete', '')
    paquete    = _PAQUETES_MAP.get(paquete_id)
    plan_label = paquete['nombre'] if paquete else 'tokens'
    precio     = f"${int(paquete['precio'])} USD" if paquete else '—'

    try:
        from django.core.mail import send_mail
        send_mail(
            subject=f'[Weather PRO] Transferencia TOKENS pendiente — {request.user.username}',
            message='',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=['climapro00@gmail.com'],
            fail_silently=True,
            html_message=f"""
            <div style="font-family:'Segoe UI',sans-serif;background:#0f172a;color:#fff;padding:30px;border-radius:12px;max-width:480px;margin:auto;">
                <h3 style="color:#f59e0b;">&#9203; Transferencia TOKENS pendiente</h3>
                <table style="width:100%;border-collapse:collapse;">
                    <tr><td style="color:#94a3b8;padding:6px 0;">Usuario</td><td style="color:#fff;font-weight:bold;">{request.user.username}</td></tr>
                    <tr><td style="color:#94a3b8;padding:6px 0;">Email</td><td style="color:#fff;">{request.user.email or '(sin email)'}</td></tr>
                    <tr><td style="color:#94a3b8;padding:6px 0;">Plan</td><td style="color:#fff;">{plan_label} &mdash; {precio}</td></tr>
                    <tr><td style="color:#94a3b8;padding:6px 0;">Paquete ID</td><td style="color:#fff;">{paquete_id}</td></tr>
                    <tr><td style="color:#94a3b8;padding:6px 0;">ID Usuario</td><td style="color:#fff;">{request.user.id}</td></tr>
                </table>
                <p style="margin-top:20px;color:#94a3b8;">Para activar en la shell de admin:</p>
                <code style="background:#1e293b;color:#4ade80;padding:10px;display:block;border-radius:8px;font-size:0.85em;">
                    user = User.objects.get(id={request.user.id})<br>
                    user.perfil.activar_plan_tokens({paquete['tokens_dia'] if paquete else 0}, {paquete['dias'] if paquete else 30}, "{plan_label}")
                </code>
            </div>
            """
        )
    except Exception as e:
        print(f"[CONFIRMAR_MANUAL_TOKENS] Error enviando mail admin: {e}")

    return render(request, 'pending.html', {
        'plan':   'tokens',
        'metodo': 'transferencia',
        'paquete': paquete,
    })


@login_required
def recargar_tokens_view(request):
    """Redirige a /pricing/#tokens — los planes de tokens están en la página de planes."""
    return redirect('/pricing/#tokens')


@login_required
def mp_crear_preferencia_tokens(request):
    """Crea una preferencia de pago en MP para un plan de tokens (con variante de duración)."""
    paquete_id = request.GET.get('paquete', '')
    paquete = _PAQUETES_MAP.get(paquete_id)

    if not paquete:
        return redirect('recargar_tokens')

    sdk  = mercadopago.SDK(settings.MP_ACCESS_TOKEN)
    site = settings.SITE_URL.rstrip('/')

    meses_label = f"{paquete['meses']} mes{'es' if paquete['meses'] > 1 else ''}"
    regalo_label = f" + {paquete['regalo']} de regalo" if paquete['regalo'] else ''

    preference_data = {
        "items": [{
            "title": f"Weather PRO — {paquete['nombre']} {paquete['tokens_dia']:,} tokens/día · {meses_label}{regalo_label}",
            "quantity": 1,
            "unit_price": paquete['precio'],
            "currency_id": "USD",
        }],
        "back_urls": {
            "success": f"{site}/tokens-retorno/?paquete={paquete_id}&status=approved",
            "failure": f"{site}/recargar-tokens/",
            "pending": f"{site}/tokens-retorno/?paquete={paquete_id}&status=pending",
        },
        "auto_return": "approved",
        "external_reference": f"{request.user.id}_tk_{paquete_id}",
        "notification_url": f"{site}/mp-webhook/",
    }

    result   = sdk.preference().create(preference_data)
    response = result.get("response", {})

    if result.get("status") in (200, 201) and "init_point" in response:
        return redirect(response["init_point"])

    logger.error(f"[MP Tokens] Error creando preferencia: {result}")
    return redirect('recargar_tokens')


@login_required
def tokens_retorno_view(request):
    """Pantalla de retorno de MP para compra de tokens (fallback al webhook)."""
    status     = request.GET.get('status', '')
    paquete_id = request.GET.get('paquete', '')
    payment_id = request.GET.get('payment_id') or request.GET.get('collection_id')
    paquete    = _PAQUETES_MAP.get(paquete_id)

    if status == 'approved' and paquete:
        # Verificar el pago con la API de MP antes de activar tokens
        pago_verificado = False
        if payment_id:
            try:
                sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)
                payment_info = sdk.payment().get(int(payment_id))
                if payment_info.get('status') == 200:
                    payment = payment_info['response']
                    ext_ref = payment.get('external_reference', '')
                    if (payment.get('status') == 'approved'
                            and ext_ref.startswith(f"{request.user.id}_tk_")):
                        pago_verificado = True
            except Exception as e:
                logger.error(f'[MP TOKENS RETORNO] Error verificando pago {payment_id}: {e}')

        if not pago_verificado:
            logger.warning(f'[MP TOKENS RETORNO] Pago no verificado para usuario {request.user.id}, payment_id={payment_id}')
            return redirect('recargar_tokens')

        from .models import HistorialTokens
        # Usar tipo 'RECARGA' (mismo que usa el webhook) para la verificación de idempotencia
        ya_procesado = HistorialTokens.objects.filter(
            usuario=request.user,
            tipo='RECARGA',
            descripcion__icontains=paquete['nombre'],
            fecha__date=timezone.now().date(),
        ).exists()
        if not ya_procesado:
            meses_label = f"{paquete['meses']}m" + (f"+{paquete['regalo']}regalo" if paquete['regalo'] else '')
            request.user.perfil.activar_plan_tokens(
                paquete['tokens_dia'],
                paquete['dias'],
                f"Plan {paquete['nombre']} {meses_label} — {paquete['tokens_dia']:,} tokens/día",
            )
        return render(request, 'pago_exitoso_tokens.html', {
            'paquete': paquete,
            'tokens_disponibles': request.user.perfil.tokens_disponibles,
        })

    if status == 'pending':
        return render(request, 'pending.html', {'plan': 'tokens', 'metodo': 'mercadopago'})

    return redirect('recargar_tokens')


# ==========================================
# VISTAS DE FEEDBACK IA
# ==========================================

@csrf_exempt
@require_http_methods(["POST"])
def guardar_feedback(request):
    """
    Endpoint para guardar feedback de usuario sobre respuestas de la IA
    Recibe: tipo_feedback, sector, mensaje_ia, comentario (opcional), session_id
    """
    try:
        # Importar el modelo aquí para evitar problemas circulares
        from .models import FeedbackIA
        
        # Obtener datos del request
        data = json.loads(request.body)
        
        tipo_feedback = data.get('tipo_feedback')  # LIKE, DISLIKE, COMENTARIO
        sector = data.get('sector')  # AGRO, NAVAL, AEREO, ENERGIA
        mensaje_ia = data.get('mensaje_ia', '')
        comentario = data.get('comentario', '')
        session_id = data.get('session_id', '')
        
        # Validaciones básicas
        if not tipo_feedback or not sector:
            return JsonResponse({
                'success': False,
                'error': 'Faltan campos obligatorios: tipo_feedback, sector'
            }, status=400)
        
        # Validar que el sector sea válido
        sectores_validos = ['AGRO', 'NAVAL', 'AEREO', 'ENERGIA']
        if sector.upper() not in sectores_validos:
            return JsonResponse({
                'success': False,
                'error': f'Sector inválido. Debe ser uno de: {", ".join(sectores_validos)}'
            }, status=400)
        
        # Validar tipo de feedback
        tipos_validos = ['LIKE', 'DISLIKE', 'COMENTARIO']
        if tipo_feedback.upper() not in tipos_validos:
            return JsonResponse({
                'success': False,
                'error': f'Tipo de feedback inválido. Debe ser uno de: {", ".join(tipos_validos)}'
            }, status=400)
        
        # Obtener IP del usuario
        ip_usuario = request.META.get('HTTP_X_FORWARDED_FOR')
        if ip_usuario:
            ip_usuario = ip_usuario.split(',')[0]
        else:
            ip_usuario = request.META.get('REMOTE_ADDR')
        
        # Crear registro de feedback
        feedback = FeedbackIA.objects.create(
            usuario=request.user if request.user.is_authenticated else None,
            sector=sector.upper(),
            tipo_feedback=tipo_feedback.upper(),
            mensaje_ia=mensaje_ia[:5000],  # Limitar a 5000 caracteres
            comentario=comentario[:1000] if comentario else None,  # Limitar a 1000 caracteres
            session_id=session_id[:100] if session_id else None,
            ip_usuario=ip_usuario
        )
        
        logger.info(f"Feedback guardado - ID: {feedback.id}, Tipo: {tipo_feedback}, Sector: {sector}")
        
        return JsonResponse({
            'success': True,
            'mensaje': 'Feedback guardado exitosamente',
            'feedback_id': feedback.id
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'JSON inválido en el cuerpo de la petición'
        }, status=400)
    except Exception as e:
        logger.error(f"Error guardando feedback: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Error interno del servidor: {str(e)}'
        }, status=500)


@login_required
def panel_feedback(request):
    """
    Panel de administración para ver todos los feedbacks recibidos
    Solo accesible para usuarios autenticados (staff)
    """
    # Verificar que el usuario es staff o superuser
    if not request.user.is_staff and not request.user.is_superuser:
        return redirect('home')
    
    from .models import FeedbackIA
    from django.db.models import Count, Q
    
    # Filtros
    sector_filter = request.GET.get('sector', '')
    tipo_filter = request.GET.get('tipo', '')
    revisado_filter = request.GET.get('revisado', '')
    
    # Query base
    feedbacks = FeedbackIA.objects.all()
    
    # Aplicar filtros
    if sector_filter:
        feedbacks = feedbacks.filter(sector=sector_filter)
    if tipo_filter:
        feedbacks = feedbacks.filter(tipo_feedback=tipo_filter)
    if revisado_filter == 'si':
        feedbacks = feedbacks.filter(revisado=True)
    elif revisado_filter == 'no':
        feedbacks = feedbacks.filter(revisado=False)
    
    # Estadísticas
    stats = {
        'total': FeedbackIA.objects.count(),
        'likes': FeedbackIA.objects.filter(tipo_feedback='LIKE').count(),
        'dislikes': FeedbackIA.objects.filter(tipo_feedback='DISLIKE').count(),
        'comentarios': FeedbackIA.objects.filter(tipo_feedback='COMENTARIO').count(),
        'no_revisados': FeedbackIA.objects.filter(revisado=False).count(),
        'por_sector': FeedbackIA.objects.values('sector').annotate(total=Count('id')),
    }
    
    context = {
        'feedbacks': feedbacks[:100],  # Limitar a 100 resultados
        'stats': stats,
        'sector_filter': sector_filter,
        'tipo_filter': tipo_filter,
        'revisado_filter': revisado_filter,
    }
    
    return render(request, 'panel_feedback.html', context)


# ==============================================================================
# DEVORADOR DE REPORTES — Procesamiento Documental con IA
# ==============================================================================

@login_required
def devorador_vista(request):
    """Renderiza la página del Devorador de Reportes."""
    if not request.user.is_authenticated:
        return redirect('login')
    if hasattr(request.user, 'perfil') and not request.user.perfil.suscripcion_activa:
        return redirect('pricing')
    if hasattr(request.user, 'perfil') and not request.user.perfil.puede_devorador:
        return render(request, 'sector_bloqueado.html', {
            'sector_bloqueado': 'Devorador de Reportes',
            'motivo': 'Esta función está disponible desde el plan <strong>Plus</strong> o superior.',
            'plan_nivel': request.user.perfil.plan_nivel,
        })
    return render(request, 'devorador_reporte.html')


@login_required
@require_http_methods(["POST"])
def devorador_api(request):
    """
    Recibe un PDF del frontend, lo reenvía al workflow n8n Devorador de Reportes
    y devuelve el análisis ejecutivo con 5 viñetas críticas.
    """
    if hasattr(request.user, 'perfil') and not request.user.perfil.suscripcion_activa:
        return JsonResponse({'error': 'Suscripción PRO requerida para usar el Devorador de Reportes.'}, status=403)

    # Gate por plan: solo pro_ia y power pueden usar el Devorador
    if hasattr(request.user, 'perfil') and not request.user.perfil.puede_devorador:
        return JsonResponse(
            {'error': 'El Devorador de Reportes está disponible desde el plan Pro IA. Actualizá tu plan en /pricing/.'},
            status=403
        )

    # Verificar tokens disponibles
    from .models import COSTO_TOKENS
    if hasattr(request.user, 'perfil'):
        costo = COSTO_TOKENS['DEVORADOR_REPORTE']
        if not request.user.perfil.tiene_tokens(costo):
            return JsonResponse(
                {'error': f'Tokens insuficientes. El Devorador de Reportes requiere {costo:,} tokens. Recargá tu plan para continuar.'},
                status=402
            )

    # Verificar que se recibió un archivo
    documento = request.FILES.get('documento')
    if not documento:
        return JsonResponse({'error': 'No se recibió ningún archivo. Por favor adjunta un PDF.'}, status=400)

    # Validar extensión (whitelist)
    nombre_lower = documento.name.lower()
    if not nombre_lower.endswith(('.pdf', '.txt', '.docx')):
        return JsonResponse({'error': 'Solo se aceptan archivos PDF, TXT o DOCX.'}, status=415)

    # Validar tamaño (50 MB máximo)
    tamano_mb = documento.size / (1024 * 1024)
    if tamano_mb > 50:
        return JsonResponse(
            {'error': f'El archivo supera el límite de 50MB ({tamano_mb:.1f}MB).'},
            status=400
        )

    # Sanitizar campos del formulario
    sector_raw = request.POST.get('sector', 'GENERAL').upper().strip()
    sectores_validos = ['AGRO', 'NAVAL', 'AEREO', 'ENERGIA', 'GENERAL']
    sector = sector_raw if sector_raw in sectores_validos else 'GENERAL'

    # Sanitizar nombre de empresa: solo alfanuméricos, espacios y guiones comunes
    import re as _re
    empresa_raw = request.POST.get('empresa', 'Empresa').strip()
    empresa = _re.sub(r'[^\w\sáéíóúÁÉÍÓÚñÑ.,\-]', '', empresa_raw)[:100] or 'Empresa'

    session_id = f"drc-{request.user.id}-{int(time.time())}"

    # URL del webhook n8n — usar variable de entorno, nunca hardcodear en producción
    n8n_base = os.getenv('N8N_BASE_URL', 'https://n8n-production-2651.up.railway.app')
    webhook_url = f"{n8n_base}/webhook/devorador-reportes"

    try:
        # Leer contenido del archivo en memoria y reenviar como multipart
        contenido = documento.read()
        mime_type = documento.content_type or 'application/pdf'

        files = {
            'documento': (documento.name, contenido, mime_type)
        }
        data = {
            'sector': sector,
            'empresa': empresa,
            'session_id': session_id,
        }

        respuesta = requests.post(
            webhook_url,
            files=files,
            data=data,
            timeout=120  # 2 minutos para documentos extensos
        )
        respuesta.raise_for_status()
        resultado = respuesta.json()

        # Descontar tokens solo si el análisis fue exitoso
        if resultado.get('success') and hasattr(request.user, 'perfil'):
            from .models import COSTO_TOKENS
            request.user.perfil.descontar_tokens(
                COSTO_TOKENS['DEVORADOR_REPORTE'],
                f'Devorador de Reportes — {sector} — {documento.name[:50]}'
            )

        return JsonResponse(resultado)

    except requests.exceptions.Timeout:
        logger.error(f'[DEVORADOR] Timeout en n8n para usuario {request.user.username}')
        return JsonResponse(
            {'error': 'El análisis tardó demasiado. Por favor intenta con un documento más pequeño o en formato TXT.'},
            status=504
        )
    except requests.exceptions.HTTPError as e:
        logger.error(f'[DEVORADOR] HTTP error de n8n: {e}')
        return JsonResponse(
            {'error': 'Error en el servicio de análisis. Reintente en unos minutos.'},
            status=502
        )
    except requests.exceptions.RequestException as e:
        logger.error(f'[DEVORADOR] Error de conexión n8n: {e}')
        return JsonResponse(
            {'error': 'No se pudo conectar al servicio de análisis. Reintente en unos minutos.'},
            status=503
        )


# ─────────────────────────────────────────────────────────────────────────────
# MULTI-UBICACIÓN
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def api_ubicaciones(request):
    """
    GET  → lista de ubicaciones guardadas del usuario (JSON)
    POST → crea una nueva ubicación (JSON) si no superó el límite del plan
    """
    perfil = getattr(request.user, 'perfil', None)
    nivel = perfil.plan_nivel if perfil else 'free'
    limite = UbicacionGuardada.limite_para_plan(nivel)

    if request.method == 'GET':
        qs = UbicacionGuardada.objects.filter(usuario=request.user).values(
            'id', 'nombre', 'lat', 'lon', 'sector', 'es_principal', 'creada'
        )
        return JsonResponse({
            'ubicaciones': list(qs),
            'limite': limite,
            'total': qs.count(),
        })

    if request.method == 'POST':
        try:
            datos = json.loads(request.body)
        except (json.JSONDecodeError, TypeError):
            datos = request.POST

        nombre = str(datos.get('nombre', '')).strip()[:100]
        try:
            lat = float(datos.get('lat', 0))
            lon = float(datos.get('lon', 0))
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Coordenadas inválidas.'}, status=400)

        if not nombre:
            return JsonResponse({'error': 'El nombre es obligatorio.'}, status=400)
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            return JsonResponse({'error': 'Coordenadas fuera de rango.'}, status=400)

        actual = UbicacionGuardada.objects.filter(usuario=request.user).count()
        if limite is not None and actual >= limite:
            return JsonResponse(
                {'error': f'Tu plan permite hasta {limite} ubicación(es). Mejora tu plan para agregar más.'},
                status=403
            )

        sector = str(datos.get('sector', '')).strip()[:10].lower()
        es_primera = (actual == 0)
        ub = UbicacionGuardada.objects.create(
            usuario=request.user,
            nombre=nombre,
            lat=lat,
            lon=lon,
            sector=sector,
            es_principal=es_primera,
        )
        return JsonResponse({'id': ub.id, 'nombre': ub.nombre, 'lat': ub.lat, 'lon': ub.lon,
                             'sector': ub.sector, 'es_principal': ub.es_principal}, status=201)

    return JsonResponse({'error': 'Método no permitido.'}, status=405)


@login_required
def api_ubicacion_delete(request, pk):
    """Elimina una ubicación guardada del usuario autenticado."""
    if request.method not in ('POST', 'DELETE'):
        return JsonResponse({'error': 'Método no permitido.'}, status=405)
    try:
        ub = UbicacionGuardada.objects.get(pk=pk, usuario=request.user)
    except UbicacionGuardada.DoesNotExist:
        return JsonResponse({'error': 'No encontrada.'}, status=404)

    ub.delete()
    return JsonResponse({'ok': True})


# ─────────────────────────────────────────────────────────────────────────────
# REPORTES PROGRAMADOS
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def reportes_programados(request):
    """
    GET  → página con lista de reportes programados
    POST → crea o elimina un reporte (campo 'accion': 'crear' | 'eliminar')
    """
    perfil = getattr(request.user, 'perfil', None)
    if not perfil or perfil.plan_nivel not in ('pro_ia', 'power'):
        return render(request, 'sector_bloqueado.html', {
            'mensaje': 'Los reportes programados están disponibles a partir del plan Pro IA.',
            'plan_requerido': 'pro_ia',
        })

    if request.method == 'POST':
        accion = request.POST.get('accion', 'crear')

        if accion == 'eliminar':
            pk = request.POST.get('pk', '')
            try:
                rep = ReporteProgramado.objects.get(pk=pk, usuario=request.user)
                rep.delete()
            except ReporteProgramado.DoesNotExist:
                pass
            return redirect('reportes_programados')

        sector = request.POST.get('sector', '')[:10].lower()
        frecuencia = request.POST.get('frecuencia', 'diario')
        try:
            hora_envio = int(request.POST.get('hora_envio', 8))
            hora_envio = max(0, min(23, hora_envio))
        except (ValueError, TypeError):
            hora_envio = 8
        email_destino = request.POST.get('email_destino', '').strip()[:254]

        sectores_validos = [s[0] for s in ReporteProgramado.SECTORES]
        frecuencias_validas = [f[0] for f in ReporteProgramado.FRECUENCIAS]
        if sector not in sectores_validos or frecuencia not in frecuencias_validas:
            return redirect('reportes_programados')

        # Máximo 5 reportes activos por usuario
        if ReporteProgramado.objects.filter(usuario=request.user, activo=True).count() >= 5:
            return render(request, 'reportes_programados.html', {
                'reportes': ReporteProgramado.objects.filter(usuario=request.user),
                'error': 'Máximo 5 reportes activos permitidos.',
            })

        ReporteProgramado.objects.create(
            usuario=request.user,
            sector=sector,
            frecuencia=frecuencia,
            hora_envio=hora_envio,
            email_destino=email_destino,
        )
        return redirect('reportes_programados')

    reportes = ReporteProgramado.objects.filter(usuario=request.user)
    return render(request, 'reportes_programados.html', {'reportes': reportes})


# ─────────────────────────────────────────────────────────────────────────────
# API KEY PERSONAL
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def api_key_personal(request):
    """
    Gestiona la API key personal del usuario.
    Plan requerido: Plus+
    POST 'accion=generar'  → genera (o regenera) la clave
    POST 'accion=revocar'  → desactiva la clave
    """
    perfil = getattr(request.user, 'perfil', None)
    if not perfil or perfil.plan_nivel not in ('plus', 'pro_ia', 'power'):
        return render(request, 'sector_bloqueado.html', {
            'mensaje': 'La API key personal está disponible a partir del plan Plus.',
            'plan_requerido': 'plus',
        })

    api_key, _ = ApiKeyPersonal.objects.get_or_create(
        usuario=request.user,
        defaults={'clave': uuid.uuid4().hex + uuid.uuid4().hex, 'activa': False},
    )

    if request.method == 'POST':
        accion = request.POST.get('accion', '')
        if accion == 'generar':
            api_key.clave = uuid.uuid4().hex + uuid.uuid4().hex
            api_key.activa = True
            api_key.save(update_fields=['clave', 'activa'])
        elif accion == 'revocar':
            api_key.activa = False
            api_key.save(update_fields=['activa'])
        return redirect('api_key_personal')

    return render(request, 'api_key_personal.html', {'api_key': api_key})


# ─────────────────────────────────────────────────────────────────────────────
# HISTORIAL DE ANOMALÍAS
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def historial_anomalias(request):
    """
    Muestra datos sectoriales históricos vinculados al usuario.
    El rango de días disponible depende del plan (dias_historial).
    """
    perfil = getattr(request.user, 'perfil', None)
    dias = perfil.dias_historial if perfil else 0
    if dias == 0:
        return render(request, 'sector_bloqueado.html', {
            'mensaje': 'El historial de anomalías requiere al menos el plan Starter.',
            'plan_requerido': 'starter',
        })

    sector_filtro = request.GET.get('sector', '').upper()
    sectores_validos = {'NAVAL', 'ENERGIA', 'AEREO', 'AGRO'}

    desde = timezone.now() - timedelta(days=dias)
    qs = DatoSectorial.objects.filter(
        usuario_carga=request.user,
        fecha_registro__gte=desde,
    ).order_by('-fecha_registro')

    if sector_filtro in sectores_validos:
        qs = qs.filter(sector=sector_filtro)

    # Paginación simple: últimos 50 registros
    registros = list(qs[:50])

    return render(request, 'historial_anomalias.html', {
        'registros': registros,
        'dias': dias,
        'sector_filtro': sector_filtro,
        'sectores': ['AGRO', 'NAVAL', 'AEREO', 'ENERGIA'],
    })


@login_required
@require_http_methods(["POST"])
def marcar_feedback_revisado(request, feedback_id):
    """
    Marca un feedback como revisado
    """
    if not request.user.is_staff and not request.user.is_superuser:
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    try:
        from .models import FeedbackIA
        
        feedback = FeedbackIA.objects.get(id=feedback_id)
        feedback.revisado = not feedback.revisado  # Toggle
        feedback.save()
        
        return JsonResponse({
            'success': True,
            'revisado': feedback.revisado
        })
    except FeedbackIA.DoesNotExist:
        return JsonResponse({'error': 'Feedback no encontrado'}, status=404)
    except Exception as e:
        logger.error(f"Error marcando feedback como revisado: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def admin_dashboard(request):
    """
    Panel de control administrativo completo
    Solo accesible para superusuarios
    """
    # Verificar que sea superusuario
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Acceso denegado. Solo superusuarios.'}, status=403)
    
    from .models import FeedbackIA, ReporteUsuario, DatoSectorial, PerfilUsuario
    from django.contrib.auth.models import User
    from datetime import datetime, timedelta
    
    # Fechas para filtros
    hoy = timezone.now()
    hace_30_dias = hoy - timedelta(days=30)
    hace_7_dias = hoy - timedelta(days=7)
    primer_dia_mes = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # ============ ESTADÍSTICAS GENERALES ============
    stats = {
        # Usuarios
        'total_usuarios': User.objects.count(),
        'usuarios_activos': PerfilUsuario.objects.filter(
            fecha_vencimiento__gt=hoy
        ).count(),
        'usuarios_nuevos_mes': User.objects.filter(
            date_joined__gte=primer_dia_mes
        ).count(),

        # Suscripciones por plan
        'usuarios_mensual': PerfilUsuario.objects.filter(
            fecha_vencimiento__gt=hoy, plan_tipo='mensual'
        ).count(),
        'usuarios_anual': PerfilUsuario.objects.filter(
            fecha_vencimiento__gt=hoy, plan_tipo='anual'
        ).count(),
        'vencen_7_dias': PerfilUsuario.objects.filter(
            fecha_vencimiento__gt=hoy,
            fecha_vencimiento__lt=hoy + timedelta(days=7)
        ).count(),
        'con_recordatorio': PerfilUsuario.objects.filter(
            renovacion_automatica=True, fecha_vencimiento__gt=hoy
        ).count(),
        'ingresos_estimados': (
            PerfilUsuario.objects.filter(fecha_vencimiento__gt=hoy, plan_tipo='mensual').count() * 20 +
            PerfilUsuario.objects.filter(fecha_vencimiento__gt=hoy, plan_tipo='anual').count() * 200
        ),

        # Feedback
        'total_feedback': FeedbackIA.objects.count(),
        'feedback_hoy': FeedbackIA.objects.filter(
            fecha_creacion__date=hoy.date()
        ).count(),
        'total_likes': FeedbackIA.objects.filter(tipo_feedback='LIKE').count(),
        'total_dislikes': FeedbackIA.objects.filter(tipo_feedback='DISLIKE').count(),
        'total_comentarios': FeedbackIA.objects.filter(tipo_feedback='COMENTARIO').count(),
        
        # Datos sectoriales
        'total_datos': DatoSectorial.objects.count(),
        'datos_mes': DatoSectorial.objects.filter(
            fecha_registro__gte=primer_dia_mes
        ).count(),
        
        # Reportes
        'reportes_pendientes': ReporteUsuario.objects.filter(
            fecha__gte=hace_7_dias
        ).count(),
    }
    
    # ============ DATOS PARA GRÁFICOS ============
    # Datos por sector (últimos 30 días)
    sectores_data = DatoSectorial.objects.filter(
        fecha_registro__gte=hace_30_dias
    ).values('sector').annotate(
        total=Count('id')
    ).order_by('sector')
    
    sectores_labels = [item['sector'] for item in sectores_data]
    sectores_values = [item['total'] for item in sectores_data]
    
    # Feedback por tipo
    feedback_likes = FeedbackIA.objects.filter(tipo_feedback='LIKE').count()
    feedback_dislikes = FeedbackIA.objects.filter(tipo_feedback='DISLIKE').count()
    feedback_comentarios = FeedbackIA.objects.filter(tipo_feedback='COMENTARIO').count()
    
    chart_data = {
        'sectores_labels': json.dumps(sectores_labels),
        'sectores_values': json.dumps(sectores_values),
        'feedback_values': json.dumps([feedback_likes, feedback_dislikes, feedback_comentarios]),
    }
    
    # ============ DATOS RECIENTES ============
    feedback_reciente = FeedbackIA.objects.select_related('usuario').order_by('-fecha_creacion')[:20]
    reportes = ReporteUsuario.objects.select_related('usuario').order_by('-fecha')[:15]
    datos_recientes = DatoSectorial.objects.select_related('usuario_carga').order_by('-fecha_registro')[:15]
    perfiles_suscripcion = PerfilUsuario.objects.select_related('user').order_by('-fecha_vencimiento')[:60]
    
    context = {
        'stats': stats,
        'chart_data': chart_data,
        'feedback_reciente': feedback_reciente,
        'reportes': reportes,
        'datos_recientes': datos_recientes,
        'perfiles_suscripcion': perfiles_suscripcion,
        'hoy': hoy,
    }
    
    return render(request, 'admin_dashboard.html', context)


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN — Activar/extender suscripción de un usuario desde el dashboard
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def admin_activar_usuario(request):
    """Endpoint AJAX: solo superusuarios. Extiende la suscripción de un usuario."""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Acceso denegado'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    from django.contrib.auth.models import User as AuthUser
    user_id = request.POST.get('user_id')
    dias = int(request.POST.get('dias', 30))
    plan = request.POST.get('plan', 'mensual')

    if dias not in (30, 365) or plan not in ('mensual', 'anual'):
        return JsonResponse({'error': 'Parámetros inválidos'}, status=400)

    try:
        usuario = AuthUser.objects.get(id=user_id)
    except AuthUser.DoesNotExist:
        return JsonResponse({'error': 'Usuario no encontrado'}, status=404)

    activar_suscripcion_dias(usuario, dias, plan)
    perfil = usuario.perfil
    return JsonResponse({
        'ok': True,
        'username': usuario.username,
        'vencimiento': perfil.fecha_vencimiento.strftime('%d/%m/%Y'),
        'plan': plan,
    })


@login_required
def admin_toggle_renovacion(request):
    """Endpoint AJAX: cambia renovacion_automatica de un usuario."""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Acceso denegado'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    from django.contrib.auth.models import User as AuthUser
    user_id = request.POST.get('user_id')

    try:
        usuario = AuthUser.objects.get(id=user_id)
        perfil = usuario.perfil
    except (AuthUser.DoesNotExist, PerfilUsuario.DoesNotExist):
        return JsonResponse({'error': 'Usuario no encontrado'}, status=404)

    perfil.renovacion_automatica = not perfil.renovacion_automatica
    perfil.save(update_fields=['renovacion_automatica'])
    return JsonResponse({'ok': True, 'renovacion_automatica': perfil.renovacion_automatica})


def obtener_noticias_clima(request):
    # Usamos una búsqueda limpia
    url = 'https://news.google.com/rss/search?q=clima+meteorologia+ambiente&hl=es-419&gl=AR'
    
    try:
        # Nos disfrazamos de navegador para que Google no nos bloquee
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
        
        # Leemos el XML nativo de Google
        root = ET.fromstring(xml_data)
        noticias = []
        
        for item in root.findall('.//item')[:20]: # Traemos las 20 más recientes
            noticias.append({
                'title': item.findtext('title', ''),
                'link': item.findtext('link', ''),
                'pubDate': item.findtext('pubDate', ''),
                'description': item.findtext('description', ''),
                'source': item.findtext('source', 'Google News'),
            })
            
        return JsonResponse({'success': True, 'items': noticias})
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def laboratorio(request):
    """Vista para el Laboratorio 3D del planeta."""
    return render(request, 'laboratorio.html')


# ─────────────────────────────────────────────────────────────────────────────
# PROXIES Open-Meteo para el Laboratorio 3D
# Los datos se cacheán en memoria durante 1 hora para que múltiples usuarios
# no consuman el límite gratuito de Open-Meteo.
# ─────────────────────────────────────────────────────────────────────────────
_lab_cache = {}   # { 'viento': (timestamp, data), 'eventos': (timestamp, data) }
LAB_CACHE_TTL = 3600  # segundos


def _lab_get_or_fetch(key, url):
    """Devuelve datos cacheados o los descarga de Open-Meteo."""
    now = time.time()
    if key in _lab_cache:
        ts, data = _lab_cache[key]
        if now - ts < LAB_CACHE_TTL:
            return data
    resp = pedir_datos_seguro(url)
    resp.raise_for_status()
    raw = resp.json()
    _lab_cache[key] = (now, raw)
    return raw


def api_viento_proxy(request):
    """Devuelve corrientes de viento (grid 7×12) cacheadas 1 h."""
    WIND_LATS = [-75, -50, -25, 0, 25, 50, 75]
    WIND_LONS = [-165,-135,-105,-75,-45,-15,15,45,75,105,135,165]
    lats, lons = [], []
    for la in WIND_LATS:
        for lo in WIND_LONS:
            lats.append(la); lons.append(lo)
    url = (
        'https://api.open-meteo.com/v1/forecast'
        f'?latitude={",".join(map(str,lats))}'
        f'&longitude={",".join(map(str,lons))}'
        '&current=wind_speed_10m,wind_direction_10m&wind_speed_unit=kmh&timezone=GMT'
    )
    try:
        raw = _lab_get_or_fetch('viento', url)
        pts = (raw if isinstance(raw, list) else [raw])
        result = [
            {
                'lat':   p['latitude'],
                'lon':   p['longitude'],
                'speed': (p.get('current') or {}).get('wind_speed_10m', 0),
                'dir':   (p.get('current') or {}).get('wind_direction_10m', 0),
            }
            for p in pts
        ]
        return JsonResponse(result, safe=False)
    except Exception as e:
        logger.error('api_viento_proxy error: %s', e)
        return JsonResponse([], safe=False)


def api_eventos_proxy(request):
    """Devuelve eventos climáticos severos clasificados (grid 9×11) cacheados 1 h."""
    SEV_LATS = [-55, -35, -20, -10, 0, 10, 20, 35, 55]
    SEV_LONS = [-150,-120,-90,-60,-30,0,30,60,90,120,150]
    lats, lons = [], []
    for la in SEV_LATS:
        for lo in SEV_LONS:
            lats.append(la); lons.append(lo)
    url = (
        'https://api.open-meteo.com/v1/forecast'
        f'?latitude={",".join(map(str,lats))}'
        f'&longitude={",".join(map(str,lons))}'
        '&current=weather_code,wind_gusts_10m,wind_speed_10m,temperature_2m'
        '&wind_speed_unit=kmh&timezone=GMT'
    )
    try:
        raw = _lab_get_or_fetch('eventos', url)
    except Exception as e:
        logger.error('api_eventos_proxy error: %s', e)
        return JsonResponse([], safe=False)

    def classify(wmo, gust, speed, temp, lat):
        tropical = abs(lat) <= 30
        if tropical  and gust > 118: return {'name':'Huracán / Ciclón',          'color':'#ef4444','severity':5,'icon':'🌀'}
        if tropical  and gust >  88: return {'name':'Tormenta tropical severa',   'color':'#f97316','severity':4,'icon':'🌀'}
        if tropical  and gust >  62: return {'name':'Depresión tropical',         'color':'#fb923c','severity':3,'icon':'🌀'}
        if not tropical and gust>90: return {'name':'Ciclón extratropical',       'color':'#ef4444','severity':4,'icon':'🌀'}
        if wmo == 99:                return {'name':'Tormenta eléctrica extrema', 'color':'#ef4444','severity':4,'icon':'⛈️'}
        if wmo == 96:                return {'name':'Tormenta con granizo severo','color':'#f97316','severity':3,'icon':'⛈️'}
        if wmo == 95:                return {'name':'Tormenta eléctrica',         'color':'#a78bfa','severity':3,'icon':'⛈️'}
        if gust > 75:                return {'name':'Vientos huracanados',        'color':'#f97316','severity':4,'icon':'💨'}
        if (wmo in (75,77)) and temp < -5: return {'name':'Ventisca / Blizzard', 'color':'#60a5fa','severity':3,'icon':'❄️'}
        if 71 <= wmo <= 77:          return {'name':'Tormenta de nieve',          'color':'#93c5fd','severity':2,'icon':'🌨️'}
        if wmo == 82 or (wmo == 81 and gust > 50): return {'name':'Chubascos intensos','color':'#818cf8','severity':2,'icon':'🌧️'}
        if wmo >= 80 and gust > 55:  return {'name':'Frente tormentoso',          'color':'#a78bfa','severity':2,'icon':'⛅'}
        return None

    def region(lat, lon):
        if -100<=lon<=-20 and  8<=lat<=35:  return 'Atlántico tropical'
        if -175<=lon<=-90 and  5<=lat<=30:  return 'Pacífico E. tropical'
        if   60<=lon<=120 and  5<=lat<=25:  return 'Océano Índico N.'
        if  100<=lon<=180 and -25<=lat<=20: return 'Pacífico Occidental'
        if  -30<=lon<=90 and -30<=lat<=-5:  return 'Índico Sur'
        if lat >  55: return 'Polar Norte'
        if lat < -55: return 'Polar Sur / Antártida'
        la = f"{abs(lat):.0f}°{'N' if lat>=0 else 'S'}"
        lo = f"{abs(lon):.0f}°{'E' if lon>=0 else 'O'}"
        return f"{la}, {lo}"

    raw_list = raw if isinstance(raw, list) else [raw]
    events = []
    for p in raw_list:
        cur   = p.get('current') or {}
        wmo   = cur.get('weather_code', 0)
        gust  = cur.get('wind_gusts_10m', 0)
        speed = cur.get('wind_speed_10m', 0)
        temp  = cur.get('temperature_2m', 20)
        lat   = p['latitude'];  lon = p['longitude']
        ev = classify(wmo, gust, speed, temp, lat)
        if ev:
            events.append({**ev, 'lat': lat, 'lon': lon,
                           'gust': gust, 'region': region(lat, lon)})

    # Deduplicar: mayor severidad por celda ~20°
    deduped = []
    for ev in events:
        close = next((e for e in deduped
                      if abs(e['lat']-ev['lat'])<20 and abs(e['lon']-ev['lon'])<20), None)
        if not close:
            deduped.append(ev)
        elif ev['severity'] > close['severity']:
            close.update(ev)

    deduped.sort(key=lambda e: -e['severity'])
    return JsonResponse(deduped, safe=False)


# ─────────────────────────────────────────────────────────────────────────────
# MI CUENTA — perfil y preferencia de renovación
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def mi_cuenta(request):
    perfil, _ = PerfilUsuario.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        accion = request.POST.get('accion', 'preferencias')
        if accion == 'alertas':
            # Solo pro_ia y power pueden activar alertas
            if perfil.puede_alertas_proactivas:
                perfil.alertas_activas = request.POST.get('alertas_activas') == 'on'
                sectores = request.POST.getlist('alertas_sectores')
                perfil.alertas_sectores = ','.join(s for s in sectores if s in ('agro', 'naval', 'aereo', 'energia'))
                try:
                    perfil.hora_alerta = max(0, min(23, int(request.POST.get('hora_alerta', 7))))
                except (ValueError, TypeError):
                    perfil.hora_alerta = 7
                perfil.ubicacion_nombre = request.POST.get('ubicacion_nombre', '').strip()[:100]
                perfil.save(update_fields=['alertas_activas', 'alertas_sectores', 'hora_alerta', 'ubicacion_nombre'])
        else:
            nuevo_valor = request.POST.get('renovacion_automatica') == 'on'
            perfil.renovacion_automatica = nuevo_valor
            perfil.save(update_fields=['renovacion_automatica'])
        return redirect('/mi-cuenta/?guardado=1')

    from .models import COSTO_TOKENS
    perfil._reset_diario_si_necesario()
    plan_tokens = None
    if (perfil.tokens_diarios_limite and perfil.fecha_vencimiento_tokens
            and perfil.fecha_vencimiento_tokens > timezone.now()):
        plan_tokens = {
            'limite_dia': perfil.tokens_diarios_limite,
            'vencimiento': perfil.fecha_vencimiento_tokens.strftime('%d/%m/%Y'),
        }

    from .models import HistorialTokens
    historial = (HistorialTokens.objects
                 .filter(usuario=request.user)
                 .order_by('-fecha')[:20])

    # Multi-ubicación
    ubicaciones = UbicacionGuardada.objects.filter(usuario=request.user)
    nivel = perfil.plan_nivel
    limite_ubicaciones = UbicacionGuardada.limite_para_plan(nivel)

    # API Key
    try:
        api_key_obj = request.user.api_key
    except ApiKeyPersonal.DoesNotExist:
        api_key_obj = None

    return render(request, 'mi_cuenta.html', {
        'perfil': perfil,
        'plan_nivel': perfil.plan_nivel,
        'puede_alertas': perfil.puede_alertas_proactivas,
        'plan_tokens': plan_tokens,
        'tokens_disponibles': perfil.tokens_disponibles,
        'costos': COSTO_TOKENS,
        'guardado': request.GET.get('guardado') == '1',
        'historial': historial,
        'sectores_alertas': [
            ('agro',    'Agro',    '\U0001f331'),
            ('naval',   'Naval',   '\u2693'),
            ('aereo',   'Aéreo',   '\u2708\ufe0f'),
            ('energia', 'Energía', '\u26a1'),
        ],
        'horas_alerta': list(range(5, 21)),
        'ubicaciones': ubicaciones,
        'limite_ubicaciones': limite_ubicaciones,
        'api_key_obj': api_key_obj,
        'dias_historial': perfil.dias_historial,
        'puede_api_key': nivel in ('plus', 'pro_ia', 'power'),
        'puede_reportes': nivel in ('pro_ia', 'power'),
    })


# ─────────────────────────────────────────────
# ALERTAS PROACTIVAS — endpoint para n8n
# ─────────────────────────────────────────────
def api_alertas_usuarios(request):
    """Endpoint interno para n8n: devuelve usuarios con alertas activas y suscripción vigente."""
    from django.conf import settings as django_settings
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    secret = request.headers.get('X-Alertas-Secret', '')
    if secret != getattr(django_settings, 'N8N_ALERTAS_SECRET', 'tuclima-alertas-2026'):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    usuarios = []
    for perfil in (PerfilUsuario.objects
                   .filter(alertas_activas=True, fecha_vencimiento__gt=timezone.now())
                   .select_related('user')):
        if not perfil.ubicacion_nombre or not perfil.user.email:
            continue
        usuarios.append({
            'id':              perfil.user.id,
            'email':           perfil.user.email,
            'nombre':          perfil.user.first_name or perfil.user.username,
            'sectores':        perfil.alertas_sectores or 'agro',
            'hora_alerta':     perfil.hora_alerta,
            'ubicacion_nombre': perfil.ubicacion_nombre,
        })
    return JsonResponse({'usuarios': usuarios, 'total': len(usuarios)})

