# 🚀 GUÍA COMPLETA: ACTIVAR POWER BI CON TUS WEBHOOKS N8N

## ✅ **ESTADO ACTUAL - Lo que YA TIENES CONFIGURADO**

### 🔗 **Webhooks N8N funcionando:**
- **Chatbot TuClima**: `https://n8n-production-2651.up.railway.app/webhook/chat` ✅
- **Agro_BI**: `https://n8n-production-2651.up.railway.app/webhook/Agro_BI` ✅  
- **Naval_BI**: `https://n8n-production-2651.up.railway.app/webhook/Naval_BI` ✅
- **Aereo_BI**: `https://n8n-production-2651.up.railway.app/webhook/Aereo_BI` ✅
- **Energia_BI**: `https://n8n-production-2651.up.railway.app/webhook/Energia_BI` ✅

### 📱 **Frontend ya listo:**
- Chat integrado en `agro.html`, `aereo.html`, `energia.html`, `naval.html`
- Detección automática de sectores funcionando
- JavaScript actualizado para usar tus webhooks específicos

---

## 🎯 **PASOS PARA ACTIVACIÓN COMPLETA**

### **PASO 1: Verificar Subworkflows en N8N** ⚙️

En tu N8N (que veo en las capturas), asegúrate de que cada subworkflow tenga:

1. **Webhook node** configurado con las URLs correspondientes
2. **Nodo de respuesta** que devuelva:
```json
{
  "output": "Aquí está tu visualización [MOSTRAR_GRAFICO]",
  "metadata": {
    "type": "graph_response", 
    "powerBiUrl": "https://app.powerbi.com/reportEmbed?reportId=TU_REPORT_ID&groupId=TU_WORKSPACE_ID"
  }
}
```

### **PASO 2: Configurar Power BI Desktop** 📊

**Para cada sector, crear un reporte:**

#### **A) Conectar a BigQuery:**
1. Abrir Power BI Desktop
2. Obtener datos → Google BigQuery
3. Usar credenciales del archivo: `credenciales/bigquery-credentials.json`
4. Conectar a tablas: `AGRO_BI`, `AEREO_BI`, `NAVAL_BI`, `ENERGIA_BI`

#### **B) Crear visualizaciones básicas:**
```
- Gráfico de temperatura por tiempo
- Mapa de ubicaciones  
- Tabla de datos recientes
- KPI cards principales
```

#### **C) Publicar en Power BI Service:**
1. Publicar cada reporte
2. Obtener URL de embed para cada uno
3. Copiar URLs para el siguiente paso

### **PASO 3: Actualizar N8N con URLs Power BI** 🔗

En cada subworkflow de N8N (Agro_BI, Aereo_BI, etc.), en el nodo de respuesta, reemplazar:

```javascript
// En el nodo "Respond to Webhook" de cada subworkflow:
{
  "output": "📊 Visualización generada [MOSTRAR_GRAFICO]",
  "metadata": {
    "type": "graph_response",
    "powerBiUrl": "TU_URL_POWER_BI_AQUI"
  }
}
```

**URLs por sector:**
- **Agro_BI**: URL del reporte agrícola
- **Aereo_BI**: URL del reporte aeronáutico  
- **Energia_BI**: URL del reporte energético
- **Naval_BI**: URL del reporte naval

### **PASO 4: Testing Final** 🧪

1. **Ir a cualquier página** (agro.html, aereo.html, etc.)
2. **Escribir en el chat:** "muestra gráfico de temperatura"
3. **Verificar que:**
   - Detecta la página correctamente
   - Envía request al webhook correcto
   - Recibe respuesta con `[MOSTRAR_GRAFICO]`
   - Se abre el Power BI automáticamente

---

## 📋 **CHECKLIST DE VERIFICACIÓN**

### ✅ **Frontend (ya listo):**
- [x] Chat integrado en 4 páginas
- [x] Detección automática de sectores  
- [x] Webhooks configurados correctamente
- [x] JavaScript optimizado

### ⏳ **Pendiente de configurar:**
- [ ] Reportes Power BI Desktop creados
- [ ] URLs Power BI en subworkflows N8N
- [ ] Testing end-to-end funcionando

---

## 🚀 **TESTING RÁPIDO**

**Para probar ahora mismo sin Power BI:**

1. Ve a `agro.html`
2. Escribe: "mostrar gráfico"
3. Verifica en **Console** (F12) que veas:
```
📊 Enviando solicitud Power BI: {sector: "agro", webhook: "...Agro_BI"}
✅ Respuesta recibida de N8N: {...}
```

**Si ves esos logs, el frontend está 100% funcional.**

---

## ❓ **PRÓXIMO PASO RECOMENDADO**

Te sugiero ejecutar el **TESTING RÁPIDO** primero para confirmar que los webhooks responden, y luego proceder con los reportes Power BI.

¿Quieres que probemos la conexión primero o prefieres que vayamos directo a configurar Power BI Desktop?