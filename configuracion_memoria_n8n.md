# 🔧 CONFIGURACIÓN COMPLETA N8N CON MEMORIA

## 🏗️ FLUJO COMPLETO (7 NODOS):

```
[1] WEBHOOK TRIGGER 
    ↓
[2] SUPABASE GET (recuperar memoria)
    ↓  
[3] CODE NODE (procesar memoria)
    ↓
[4] IA NODE (OpenAI/Claude con contexto)
    ↓
[5] CODE NODE (preparar guardado)
    ↓
[6] SUPABASE CREATE (guardar conversación)
    ↓
[7] WEBHOOK RESPONSE (responder)
```

---

---

## 🔄 **ORDEN CORRECTO PARA TU WORKFLOW ACTUAL:**

Basado en tu workflow que ya tiene Merge, Edit Fields, etc.:

```
[1] Webhook Trigger (tu existing)
    ↓
[2] Get many rows (Supabase) - recuperar memoria
    ↓
[3] 🆕 CODE NODE (procesar memoria) ← ANTES del Merge
    ↓  
[4] Merge (combinar input + memoria procesada)
    ↓
[5] AI Agent (con contexto completo)
    ↓
[6] 🆕 CODE NODE (preparar guardado) ← DESPUÉS de AI Agent, ANTES de Edit Fields
    ↓
[7] Edit Fields (tu nodo actual)
    ↓
[8] Respond to Webhook (tu nodo actual)
    +
[9] 🆕 SUPABASE CREATE (en paralelo, guardar conversación)
```

### 🔧 **CONFIGURACIÓN DEL MERGE NODE:**

Tu Merge node debe combinar:
- **Input 1**: Datos del webhook original  
- **Input 2**: Contexto procesado del Code Node #1

**Configuración Merge:**
- **Mode**: "Combine by Index" o "Append"
- **Include all fields**: ✅ ON

---

## 📋 CONFIGURACIÓN DETALLADA NODO POR NODO:

### [1] WEBHOOK TRIGGER
- **Método**: POST
- **URL**: Tu webhook URL actual
- **Body esperado**:
```json
{
  "chatInput": "mensaje del usuario",
  "sessionId": "session_123456", 
  "userId": "opcional",
  "currentPage": "naval|agro|aereo|energia"
}
```

### [2] SUPABASE GET MANY ROWS  
- **Tabla**: `conversaciones_memoria`
- **Operation**: `Get Many`
- **Filters**:
  - **Field**: `session_id`
  - **Condition**: `Equals`  
  - **Value**: `{{ $json.sessionId }}` 
- **Limit**: `10`
- **Additional Options**: 
  - Si hay **Sort/Order**: `created_at DESC`
  - Si hay **Select**: Dejar vacío para traer todas las columnas
- **Return All**: ✅ ON

💡 **Nota**: Si no hay opción Order/Sort, n8n traerá los registros en order natural. El Code Node después se encargará de ordenarlos por fecha.

### [3] CODE NODE: Procesar Memoria
- **Código**: Usar [n8n_memoria_ia_node.js](n8n_memoria_ia_node.js)
- **Input**: Data from Supabase GET + Webhook
- **Output**: Contexto formateado para IA
- **Language**: JavaScript

### [4] IA NODE (OpenAI/Claude)
- **Model**: gpt-4 o claude-3
- **System Message**: Usar [system_message_con_memoria.txt](system_message_con_memoria.txt)
- **User Message**: 
```
Contexto de memoria anterior: {{ $json.contexto_memoria }}

Usuario actual: {{ $json.user_message }}
Sector: {{ $json.sector_actual }}
Ubicación: {{ JSON.stringify($json.ubicacion) }}
Instrucciones: {{ $json.instrucciones_memoria }}

Primera vez: {{ $json.es_primera_vez }}
Intercambios previos: {{ $json.numero_intercambios_previos }}
```
- **Temperature**: 0.7
- **Max Tokens**: 2000

### [5] CODE NODE: Preparar Guardado  
- **Código**: Usar [n8n_guardar_respuesta_node.js](n8n_guardar_respuesta_node.js)
- **Input**: Respuesta de IA + datos anteriores
- **Output**: Datos para Supabase + respuesta final
- **Language**: JavaScript

### [6] SUPABASE CREATE
- **Tabla**: `conversaciones_memoria`
- **Operation**: `Create` 
- **Data**: `{{ $json.supabase_insert }}`
- **Return Data**: ✅ ON (opcional)

### [7] WEBHOOK RESPONSE
- **Respond With**: `JSON` (NO "First Incoming Item")
- **Response Body**: `{{ $json.webhook_response }}` 
- **Status Code**: 200 (automático)
- **Headers**: Content-Type se setea automáticamente como `application/json`

---

## ⚙️ CONFIGURACIONES CRÍTICAS:

### 🔐 Variables de Entorno en n8n:
```env
SUPABASE_URL=tu_supabase_url
SUPABASE_ANON_KEY=tu_anon_key
OPENAI_API_KEY=tu_openai_key
```

### 🎯 Filtro Correcto en Supabase GET:
**IMPORTANTE**: En el nodo Supabase GET, verifica que:
- [ ] Tabla = `conversaciones_memoria` (no `usuarios`)
- [ ] Filter Value = `{{ $json.sessionId }}` (con llaves dobles)
- [ ] Condition = `Equals` (no `In` ni `Contains`)
- [ ] Field = `session_id` (exactamente como en la tabla)

### 🧪 Testing del Flujo:
```json
// 1. Test con sesión nueva:
{
  "chatInput": "Hola, ¿cómo están las condiciones navales?",
  "sessionId": "test_session_1"
}

// 2. Test con sesión existente:  
{
  "chatInput": "¿Y cómo sigue el viento?",
  "sessionId": "test_session_1"  // Mismo sessionId
}
```

---

## 🚨 ERRORES COMUNES Y SOLUCIONES:

### ❌ "No se guarda memoria"
- **Verificar**: Tabla `conversaciones_memoria` existe en Supabase
- **Verificar**: RLS policies permiten CREATE/SELECT
- **Verificar**: Nodo CREATE tiene datos correctos

### ❌ "IA no recuerda conversaciones anteriores"  
- **Verificar**: Nodo GET recupera registros (test con Execute)
- **Verificar**: Code Node procesa memoria correctamente
- **Verificar**: System message incluye contexto de memoria

### ❌ "SessionId no funciona"
- **Verificar**: Frontend envía sessionId consistente
- **Verificar**: Filter en Supabase usa `{{ $json.sessionId }}`
- **Verificar**: Campo en tabla es `session_id` (con underscore)

### ❌ "Timeout o error 500"
- **Verificar**: Limits en nodo GET (no más de 50)
- **Verificar**: Code Node no tiene loops infinitos
- **Verificar**: Respuesta IA no excede límites

---

## ✅ VERIFICACIÓN FINAL:

1. **Ejecuta SQL**: [crear_tabla_memoria_supabase.sql](crear_tabla_memoria_supabase.sql)
2. **Configura nodos**: Sigue orden 1→2→3→4→5→6→7
3. **Copia códigos**: [memoria](n8n_memoria_ia_node.js) y [guardado](n8n_guardar_respuesta_node.js) en Code Nodes
4. **Actualiza system message**: [system_message_con_memoria.txt](system_message_con_memoria.txt)  
5. **Testa flujo**: Primera interacción → Segunda interacción → Verificar continuidad

**🎯 RESULTADO**: IA que mantiene memoria perfecta entre conversaciones y proporciona respuestas contextualizadas e inteligentes.