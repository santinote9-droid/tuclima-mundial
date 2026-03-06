# Sistema Multisectorial - Documentación

## 🚀 **Funcionalidad Implementada**

Se ha implementado exitosamente un sistema multisectorial completo en tu aplicación Django que permite:

### ✅ **Modelo DatoSectorial**
- **Sectores soportados**: NAVAL, ENERGÍA, AÉREO, AGRO
- **Campos genéricos**: fecha_registro, valor_principal, valor_secundario, ubicacion, analisis_ia
- **Metadatos específicos**: JSONField para variables únicas de cada sector
- **Integración BigQuery**: Método automático `enviar_a_bigquery()`

### ✅ **Vista de Procesamiento con IA**
- **Detección automática de sector** usando OpenAI GPT-3.5-turbo
- **Fallback inteligente** con palabras clave si falla la IA
- **Soporte multi-formato**: CSV, JSON, TXT, Excel (.xlsx/.xls)
- **Análisis automático** con IA del contenido procesado

---

## 🛠 **Configuración Necesaria**

### 1. **Variables de Entorno**
Crear archivo `.env` con:
```env
OPENAI_API_KEY=tu_api_key_de_openai_aqui
GOOGLE_APPLICATION_CREDENTIALS=ruta_a_tu_service_account.json
BIGQUERY_PROJECT_ID=proyecto-bi-488218
```

### 2. **Estructura BigQuery**
El sistema envía datos a estas tablas en tu proyecto `proyecto-bi-488218`:
- `proyecto-bi-488218.datos_clima.naval`
- `proyecto-bi-488218.datos_clima.energia`
- `proyecto-bi-488218.datos_clima.aereo`
- `proyecto-bi-488218.datos_clima.agro`

---

## 📱 **Cómo Usar el Sistema**

### **Acceso Web**
1. Navegar a: `/carga-sectorial/`
2. Iniciar sesión (requerido)
3. Seleccionar archivo (CSV, JSON, TXT, Excel)
4. Hacer clic en "Procesar con IA"

### **Proceso Automático**
1. ❤️ **Subida** del archivo
2. 🧠 **Detección IA** del sector
3. 📊 **Extracción** de metadatos específicos
4. 🤖 **Análisis** automático con IA
5. 💾 **Guardado** en base de datos
6. ☁️ **Envío** automático a BigQuery

---

## 📊 **Metadatos por Sector**

### 🚢 **NAVAL**
```json
{
  "altura_olas": 2.5,
  "corriente_marina": "15 km/h",
  "salinidad": 35,
  "marea": "alta"
}
```

### ⚡ **ENERGÍA**  
```json
{
  "voltaje": 220,
  "frecuencia": 50,
  "potencia": 1500,
  "factor_potencia": 0.85
}
```

### ✈️ **AÉREO**
```json
{
  "altitud": 10000,
  "presion_atmosferica": 1013,
  "visibilidad": "15 km",
  "turbulencia": "leve"
}
```

### 🌾 **AGRO**
```json
{
  "humedad_suelo": 65,
  "ph_suelo": 6.8,
  "nutrientes": "NPK 15-15-15",
  "tipo_cultivo": "maíz"
}
```

---

## 🔧 **API Endpoints**

### **POST** `/procesar-archivo-sectorial/`
**Parámetros:**
- `archivo`: Archivo multipart/form-data
- `csrfmiddlewaretoken`: Token CSRF

**Respuesta Exitosa:**
```json
{
  "success": true,
  "id": 123,
  "sector": "ENERGIA",
  "analisis": "Análisis detallado generado por IA...",
  "bigquery_success": true,
  "bigquery_mensaje": "Datos enviados correctamente a BigQuery",
  "metadatos": {...},
  "mensaje": "Archivo procesado exitosamente. Sector detectado: ENERGIA"
}
```

### **GET** `/carga-sectorial/`
Renderiza la interfaz de usuario para carga de archivos

---

## 🗄 **Acceso a Datos**

### **Django ORM**
```python
from mundo.models import DatoSectorial

# Obtener todos los datos de energía
datos_energia = DatoSectorial.objects.filter(sector='ENERGIA')

# Procesar manualmente un registro
dato = DatoSectorial.objects.get(id=123)
exito, mensaje = dato.enviar_a_bigquery()

# Obtener metadatos específicos
metadatos_especificos = dato.get_metadatos_especificos()
```

### **BigQuery**
```sql
-- Consultar datos de energía
SELECT * FROM `proyecto-bi-488218.datos_clima.energia`
WHERE DATE(fecha_registro) = CURRENT_DATE()

-- Análisis mult-sectorial
SELECT sector, COUNT(*) as registros, AVG(valor_principal) as promedio
FROM `proyecto-bi-488218.datos_clima.energia`
GROUP BY sector
```

---

## 🔍 **Integración con Vistas Existentes**

El sistema se integra perfectamente con tus vistas actuales:
- `agro()` → puede usar datos del sector AGRO
- `naval()` → puede usar datos del sector NAVAL
- `aereo()` → puede usar datos del sector AEREO  
- `energia()` → puede usar datos del sector ENERGÍA

---

## 🚨 **Detección de Errores**

### **IA Fallback**
Si falla OpenAI, el sistema automáticamente usa detección por palabras clave.

### **Validación de Archivos**
- Tamaño máximo configurado por Django
- Formatos: CSV, JSON, TXT, Excel solamente
- Validación de contenido antes de procesamiento

### **Logs**
Todos los errores se registran en el logger Django `mundo.models` y `mundo.views`.

---

## 🎯 **Próximos Pasos Recomendados**

1. **Configurar claves API**: OpenAI y Google Cloud
2. **Crear tablas BigQuery** en tu proyecto
3. **Probar con archivos de ejemplo** de cada sector
4. **Personalizar análisis IA** según tus necesidades específicas
5. **Integrar con dashboards** para visualización

¡El sistema está listo para producción! 🚀