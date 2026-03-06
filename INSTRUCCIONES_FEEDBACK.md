# 📊 Sistema de Feedback IA - Instrucciones de Instalación

## ✅ Implementación Completada

Se ha implementado un sistema completo para recopilar y analizar el feedback de usuarios sobre las respuestas de la IA.

## 🔧 Componentes Instalados

### 1. **Modelo de Base de Datos** (`FeedbackIA`)
   - Almacena likes, dislikes y comentarios
   - Incluye información del sector, usuario, sesión, IP
   - Campo para marcar como revisado

### 2. **API Backend** (3 endpoints)
   - `POST /api/guardar-feedback/` - Guarda feedback desde el frontend
   - `GET /panel-feedback/` - Panel de administración para ver feedbacks
   - `POST /api/marcar-feedback-revisado/<id>/` - Marcar como revisado

### 3. **Panel de Administración Web**
   - Interfaz moderna para ver todos los feedbacks
   - Filtros por sector, tipo, estado de revisión
   - Estadísticas en tiempo real
   - Acceso: http://localhost:8000/panel-feedback/

### 4. **Integración Frontend**
   - Botones de like/dislike funcionales en los 4 sectores
   - Sistema de comentarios con textarea y guardado
   - Envío automático al backend vía AJAX

### 5. **Admin de Django**
   - FeedbackIA visible en /admin/
   - Acciones masivas para marcar como revisado
   - Búsqueda y filtros avanzados

---

## 📦 Pasos de Instalación

### 1. **Crear las migraciones**
```bash
python manage.py makemigrations
```

Esto detectará el nuevo modelo `FeedbackIA` y creará el archivo de migración.

### 2. **Aplicar las migraciones**
```bash
python manage.py migrate
```

Esto creará la tabla `mundo_feedbackia` en la base de datos.

### 3. **Verificar instalación**
```bash
python manage.py runserver
```

---

## 🎯 Cómo Usar el Sistema

### **Para usuarios (Frontend)**
1. Los usuarios interactúan con el chat normalmente
2. Al recibir una respuesta de la IA, aparecen los botones al pasar el mouse:
   - 👍 Me gusta
   - 👎 No me gusta
   - 💬 Comentarios
   - 📋 Copiar
   - 🔄 Regenerar

3. Al hacer clic en like/dislike o escribir un comentario, se guarda automáticamente

### **Para administradores (Panel Web)**

#### Opción 1: Panel Personalizado
1. Acceder a: `http://localhost:8000/panel-feedback/`
2. Ver estadísticas generales
3. Filtrar por sector, tipo o estado
4. Marcar feedbacks como revisados

#### Opción 2: Admin de Django
1. Acceder a: `http://localhost:8000/admin/`
2. Ir a "Feedbacks IA"
3. Ver, buscar y editar feedbacks
4. Usar acciones masivas

---

## 📊 Estructura de Datos Guardados

Cada feedback incluye:
- **Tipo**: LIKE, DISLIKE o COMENTARIO
- **Sector**: AGRO, NAVAL, AEREO, ENERGIA
- **Mensaje de la IA**: El texto completo de la respuesta comentada
- **Comentario del usuario**: Si dejó un comentario (opcional)
- **Usuario**: Si está autenticado (opcional, puede ser anónimo)
- **Metadatos**: Session ID, IP, fecha y hora
- **Estado**: Revisado / No revisado

---

## 🔍 Consultas Útiles

### Ver todos los feedbacks en consola de Django:
```python
from mundo.models import FeedbackIA

# Ver todos
FeedbackIA.objects.all()

# Filtrar por sector
FeedbackIA.objects.filter(sector='AGRO')

# Ver comentarios
FeedbackIA.objects.filter(tipo_feedback='COMENTARIO')

# Ver feedbacks no revisados
FeedbackIA.objects.filter(revisado=False)

# Contar likes vs dislikes
print(f"Likes: {FeedbackIA.objects.filter(tipo_feedback='LIKE').count()}")
print(f"Dislikes: {FeedbackIA.objects.filter(tipo_feedback='DISLIKE').count()}")
```

---

## 📈 Exportar Datos para Análisis

### Desde Django Shell:
```python
import pandas as pd
from mundo.models import FeedbackIA

# Convertir a DataFrame
feedbacks = FeedbackIA.objects.all().values()
df = pd.DataFrame(feedbacks)

# Exportar a CSV
df.to_csv('feedbacks_export.csv', index=False)

# Exportar a Excel
df.to_excel('feedbacks_export.xlsx', index=False)
```

### Desde el Panel Web:
- En desarrollo futuro se puede agregar botón de exportación

---

## 🛡️ Seguridad

- El endpoint `guardar_feedback` usa `@csrf_exempt` para permitir llamadas AJAX
- IP del usuario se registra automáticamente
- Session ID se guarda para tracking sin cookies
- Límites de caracteres: mensaje_ia (5000), comentario (1000)

---

## 🎨 Personalización

### Cambiar sectores válidos:
Editar `views.py` línea ~2255:
```python
sectores_validos = ['AGRO', 'NAVAL', 'AEREO', 'ENERGIA', 'NUEVO_SECTOR']
```

### Agregar campos adicionales:
1. Editar `models.py` - Modelo `FeedbackIA`
2. Crear nueva migración: `python manage.py makemigrations`
3. Aplicar: `python manage.py migrate`

---

## ✨ Funcionalidades Futuras Sugeridas

- [ ] Gráficos de tendencias de likes/dislikes
- [ ] Exportación automática a CSV/Excel
- [ ] Notificaciones por email cuando hay feedback negativo
- [ ] Sistema de respuestas a comentarios
- [ ] Análisis de sentimiento con IA
- [ ] Dashboard con métricas en tiempo real
- [ ] Integración con n8n para automatización
- [ ] API para consultar feedbacks por fecha

---

## 🆘 Solución de Problemas

### Error: "Table doesn't exist"
```bash
python manage.py migrate --run-syncdb
```

### Error: "No module named FeedbackIA"
```bash
python manage.py makemigrations mundo
python manage.py migrate mundo
```

### No aparecen los botones en el frontend:
- Verificar que sessionId esté definido en el JavaScript
- Revisar consola del navegador para errores
- Confirmar que las rutas estén correctas en urls.py

---

## 📞 URLs del Sistema

- Panel de Feedback: `/panel-feedback/`
- API Guardar Feedback: `/api/guardar-feedback/` (POST)
- API Marcar Revisado: `/api/marcar-feedback-revisado/<id>/` (POST)
- Admin Django: `/admin/` → Feedbacks IA

---

**¡Sistema listo para usar! 🎉**
Los comentarios de los usuarios ahora se guardan automáticamente en la base de datos y puedes analizarlos desde el panel web o el admin de Django.
