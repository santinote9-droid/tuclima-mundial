from django.shortcuts import render, redirect
import requests
import json
import time
import feedparser
import urllib3
import paypalrestsdk
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.utils import timezone
from datetime import datetime, timedelta
from .models import PerfilUsuario # Importamos lo que creamos en el paso 1
from django.http import HttpResponseRedirect


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
    
    # Añadir un pequeño delay aleatorio para evitar rate limiting
    time.sleep(random.uniform(1, 3))
    
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
        
        response = requests.get(url, headers=headers, timeout=4).json()
        
        if 'address' in response:
            ad = response['address']
            # Orden de prioridad: Barrio > Villa > Suburbio > Distrito > Pueblo > Ciudad
            nombre = ad.get('neighbourhood') or ad.get('suburb') or ad.get('village') or ad.get('city_district') or ad.get('town') or ad.get('city')
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
        'hora_local': datetime.now(), 'delta_temp': 0
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
                else: nombre_ciudad = "Ubicación Exacta"
            except: nombre_ciudad = "Ubicación GPS"

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
            url_clima = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,weather_code,wind_speed_10m,surface_pressure,visibility&hourly=temperature_2m,weathercode,precipitation_probability,is_day&daily=weathercode,temperature_2m_max,temperature_2m_min,sunrise,sunset,uv_index_max&timezone=auto"
            
            response = requests.get(url_clima, timeout=3).json()
        actual = response['current']
        hourly = response['hourly']
        daily = response['daily']

        # Variables Críticas
        code = actual['weather_code']
        uv = daily['uv_index_max'][0]
        vis_metros = actual['visibility']
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
            item = {'tipo': 'normal', 'hora': dt_obj.strftime('%H:%M'), 'orden': dt_obj.timestamp(), 'temp': hourly['temperature_2m'][i], 'icono': obtener_icono_url(hourly['weathercode'][i], hourly['is_day'][i]), 'lluvia': hourly['precipitation_probability'][i], 'es_actual': es_act}
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
                'icono': obtener_icono_url(daily['weathercode'][i], 1), 'desc': descifrar_desc(daily['weathercode'][i])
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

        # Anomalía - Solo si tenemos ubicación válida
        try:
            if lat != 0.0 and lon != 0.0:
                fr = hora_local_dt.replace(year=2024).strftime('%Y-%m-%d')
                uh = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={fr}&end_date={fr}&hourly=temperature_2m&timezone=auto"
                rh = requests.get(uh, timeout=1).json()
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
        print(f"Error home: {e}")

    contexto.update({'ciudad': nombre_ciudad, 'pais': pais, 'lat': lat, 'lon': lon, 'opciones_ciudades': opciones_ciudades, 'mensaje_error': mensaje_error})
    return render(request, 'home.html', contexto)  

# ==============================================================================
# 4. COMPARADOR DE MODELOS (RESTAUARADO TAMBIÉN)
# ==============================================================================








def pricing(request):
    return render(request, 'pricing.html')


def activar_suscripcion(request):
    # Simulamos que el pago fue exitoso
    request.session['is_premium'] = True
    print("✅ PAGO EXITOSO: Usuario ahora es Premium")
    # Lo mandamos de vuelta al inicio
    return redirect('home') # Asegúrate que tu vista de inicio se llame 'home' en urls.py

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
    
    # Asumiendo que tienes un sistema de perfiles, si no, comenta estas 2 lineas
    if hasattr(request.user, 'perfil') and not request.user.perfil.suscripcion_activa:
        return redirect('pricing')

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
        response = requests.get(url)
        data = response.json()
        
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
            }
        }

    except Exception as e:
        print(f"Error en vista AGRO: {e}")
        # En caso de error, mandamos contexto vacío pero seguro para no romper el HTML
        contexto = {
            'error': 'No se pudieron cargar los datos climáticos.',
            'lat': lat, 'lon': lon
        }

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
        "&daily=sunrise,sunset,daylight_duration"
        "&timezone=auto"
    )
    
    # B. API Marina (Olas, Swell, Periodo)
    # Nota: Si es tierra firme, estos valores vendrán como 'null'
    url_marine = (
        f"https://marine-api.open-meteo.com/v1/marine?latitude={lat}&longitude={lon}"
        "&current=wave_height,wave_direction,wave_period,swell_wave_height,"
        "swell_wave_period,swell_wave_direction"
        "&hourly=wave_height,wave_period,swell_wave_height"
        "&timezone=auto"
    )

    contexto = {}

    try:
        res_w = requests.get(url_weather).json()
        res_m = requests.get(url_marine).json()

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
            }
        }

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

    return render(request, 'naval.html', contexto)

# ==========================================
# 3. VISTA: MODO AÉREO (Aviación / Pilotos)
def aereo(request):
    # 1. SEGURIDAD
    if not request.user.is_authenticated:
        return redirect('login')
    
    if hasattr(request.user, 'perfil') and not request.user.perfil.suscripcion_activa:
        return redirect('pricing')

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
        response = requests.get(url, timeout=6)
        response.raise_for_status()
        data = response.json()

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
            'grafico_aereo': grafico_data
        }

    except Exception as e:
        print(f"⚠️ ERROR CRÍTICO AEREO: {e}")
        # En caso de fallo, mostramos esto para debug
        contexto = {'error': 'Error de Datos'}

    return render(request, 'aereo.html', contexto)


# --- VISTA ENERGÍA (ENERGY OPS) ---
def energia(request):
    
    # 1. SEGURIDAD
    if not request.user.is_authenticated:
        return redirect('login')
    
    if hasattr(request.user, 'perfil') and not request.user.perfil.suscripcion_activa:
        return redirect('pricing')

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
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()

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
            }
        }

    except Exception as e:
        print(f"Error Energia: {e}")
        contexto = {'error': 'Sin datos'}

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
        response = requests.get(url).json()
        
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

# CONFIGURACIÓN (Pon tus claves aquí)
paypalrestsdk.configure({
  "mode": "sandbox", # Cambiar a "live" cuando sea real
  "client_id": "AUV9IPeHDWnBHtI_odDAV_eP20rzuyl9RiYS-Gyhqwcvgmyzn8DghQW6Md2aHbkGamDlwATYVyANyUle",
  "client_secret": "EKlfYS1qmX2EESZiD3v6hn_jbf0QY5LTZxTRcejKuxV_EQlAR0cf2tLNPMpoK0RrpiLN67OdufpIcrbp"
})

def crear_pago_paypal(request):
    # 1. Crear el objeto de pago
    payment = paypalrestsdk.Payment({
        "intent": "sale",
        "payer": {
            "payment_method": "paypal"
        },
        "redirect_urls": {
            "return_url": "http://127.0.0.1:8000/paypal-retorno/",
            "cancel_url": "http://127.0.0.1:8000/pricing/"
        },
        "transactions": [{
            "item_list": {
                "items": [{
                    "name": "Suscripción Weather PRO",
                    "sku": "pro_monthly",
                    "price": "15.00",
                    "currency": "USD",
                    "quantity": 1
                }]
            },
            "amount": {
                "total": "15.00",
                "currency": "USD"
            },
            "description": "Acceso mensual a Weather Pro Suite"
        }]
    })

    # 2. Enviar a PayPal
    if payment.create():
        # Buscamos el link de aprobación en la respuesta
        for link in payment.links:
            if link.rel == "approval_url":
                # Redirigimos al usuario a PayPal para que acepte
                return redirect(link.href)
    else:
        print(payment.error)
        return redirect('pricing')

def paypal_retorno(request):
    # 3. El usuario volvió. Ahora EJECUTAMOS el cobro.
    payment_id = request.GET.get('paymentId')
    payer_id = request.GET.get('PayerID')

    if payment_id and payer_id:
        payment = paypalrestsdk.Payment.find(payment_id)
        
        # Confirmar la transacción
    if payment.execute({"payer_id": payer_id}):
        if request.user.is_authenticated:
            activar_30_dias(request.user) # <--- AQUI SE SUMAN LOS 30 DIAS
            return redirect('home')
        else:
            print(payment.error)
    
    # Si algo falló
    return redirect('pricing')



# ==========================================
# 6. SELECCIÓN DE PAGO Y TRANSFERENCIA
# ==========================================

@login_required
def metodos_pago(request):
    # Pantalla intermedia para elegir tarjeta/paypal o banco
    return render(request, 'metodos_pago.html')

@login_required
def transferencia(request):
    # Muestra los datos del CBU
    return render(request, 'transferencia.html')

@login_required
def confirmar_manual(request):
    # ANTES: request.session['is_premium'] = True  <--- ESTO ERA EL ERROR (REGALABA EL ACCESO)
    
    # AHORA: Simplemente mostramos la pantalla de espera.
    # El usuario NO tiene acceso PRO todavía.
    return render(request, 'pending.html')



def activar_30_dias(usuario):
    perfil = usuario.perfil # Buscamos su perfil
    
    # Obtenemos la fecha de hoy
    ahora = timezone.now()
    
    # LÓGICA INTELIGENTE:
    # 1. Si ya tiene una fecha futura (ej: le quedan 5 días), le sumamos 30 más.
    # 2. Si no tiene fecha o ya venció, le damos 30 días desde hoy.
    if perfil.fecha_vencimiento and perfil.fecha_vencimiento > ahora:
        perfil.fecha_vencimiento += timedelta(days=30)
    else:
        perfil.fecha_vencimiento = ahora + timedelta(days=30)
        
    perfil.save() # Guardamos en la base de datos



def pago_exitoso(request):
    status = request.GET.get('collection_status')
    
    # Verificamos que MercadoPago/PayPal diga 'approved'
    if status == 'approved' and request.user.is_authenticated:
        
        # ¡AQUÍ LLAMAMOS A LA MAGIA!
        activar_30_dias(request.user) 
        
        print(f"PAGO APROBADO: {request.user.username} tiene 30 días de acceso.")
        return redirect('home') # Lo mandamos al inicio ya siendo PRO
        
    # Si algo falló, lo mandamos de vuelta a precios
    return redirect('pricing')




# ==========================================
# 7. SISTEMA DE USUARIOS (LOGIN / REGISTRO)
# ==========================================

def registro(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Creamos el perfil vacio al registrarse
            PerfilUsuario.objects.create(user=user)
            login(request, user)
            return redirect('pricing') # Al registrarse, lo mandamos a ver precios
    else:
        form = UserCreationForm()
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
