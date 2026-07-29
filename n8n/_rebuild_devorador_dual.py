"""
Devorador dual-entry:
- Webhook (Django UI PDF) → Validar → Extraer → Normalizar → Preparar Prompt
- Execute Workflow Trigger (Agente) → Normalizar → Preparar Prompt
- Nucleo: Preparar → Gemini → Formatear
- Solo path webhook: Formatear → Responder Exito
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
path = ROOT / "devorador_reportes.json"
data = json.loads(path.read_text(encoding="utf-8"))

# --- helpers: find / replace nodes by name ---
nodes_by_name = {n["name"]: n for n in data["nodes"]}

SECRET_CODE = nodes_by_name["Validar Secreto"]["parameters"]["jsCode"]
VALIDAR_ARCHIVO = nodes_by_name["Validar Archivo"]["parameters"]["jsCode"]
PREPARAR_OLD = nodes_by_name["Preparar Prompt Sectorial"]["parameters"]["jsCode"]
FORMATEAR = nodes_by_name["Formatear Respuesta"]["parameters"]["jsCode"]
GEMINI = nodes_by_name["Llamar Gemini API"]["parameters"]
RESPONDER = nodes_by_name["Responder Exito"]["parameters"]
WEBHOOK = nodes_by_name["Webhook Devorador"]["parameters"]

# New Preparar Prompt: unified input from Normalizar Entrada
PREPARAR_NEW = r"""// Entrada unificada (webhook PDF o sub-workflow del Agente)
const inputData = $input.first().json || {};
const textoExtraido = (inputData.texto_documento || inputData.text || inputData.data || '').toString();

const sector = (inputData.sector || 'GENERAL').toUpperCase().trim();
const empresa = (inputData.empresa || 'Empresa').toString().trim();
const sessionId = inputData.session_id || `drc-${Date.now()}`;
const nombreArchivo = inputData.nombre_archivo || 'Documento_Analizado_por_IA';
const tamanioMB = Number(inputData.tamano_mb || 0);
const origen = inputData.origen || 'subworkflow';

// Verificar que hay texto extraible
if (!textoExtraido || textoExtraido.trim().length < 50) {
  throw new Error('422 Unprocessable Entity: El documento no contiene texto extraible suficiente (<50 chars). Si es PDF escaneado, usá OCR primero.');
}

// Mapa de variables criticas por sector
const variablesPorSector = {
  AGRO: [
    '- Precipitacion acumulada y proyectada (mm)',
    '- Temperaturas maximas, minimas y medias del suelo y del aire (°C)',
    '- Humedad relativa y deficit de presion de vapor (%)',
    '- Alertas de heladas, granizo, sequia o inundacion',
    '- Indices agroclimaticos: ETo, GDD, estres hidrico',
    '- Ventanas optimas de siembra, cosecha o aplicacion de agroquimicos',
    '- Fases lunares y su impacto en ciclos vegetativos'
  ].join('\n'),
  NAVAL: [
    '- Velocidad y direccion del viento en zona de operacion (nudos/grados)',
    '- Altura significativa de olas y periodo de pico (metros/seg)',
    '- Visibilidad maritima y presencia de neblina (km)',
    '- Estado de mareas, corrientes y surgencias costeras',
    '- Ventanas operativas seguras (fechas y horas)',
    '- Alertas de temporal, ciclon, tsunami o condiciones adversas',
    '- Puerto de refugio recomendado y restricciones de zarpe'
  ].join('\n'),
  AEREO: [
    '- Condiciones METAR/TAF vigentes: visibilidad, techo de nubes, QNH',
    '- Turbulencias reportadas o pronosticadas (nivel CAT y severidad)',
    '- Alertas SIGMET/AIRMET activas en la region',
    '- Vientos en altura, tropopausa y jet stream relevantes',
    '- Riesgos de engelamiento (icing) en ruta o destino',
    '- Tormentas eléctricas y cizalladura del viento (wind shear)',
    '- Ventanas optimas de operacion VFR/IFR y alternativas de desvio'
  ].join('\n'),
  ENERGIA: [
    '- Generacion total y desglose por fuente (GWh/MWh: solar, eolica, termica)',
    '- Demanda pico, valle y promedio del periodo analizado',
    '- Precio spot y precio del mercado energetico mayorista ($/MWh)',
    '- Porcentaje de penetracion de energias renovables en la matriz',
    '- Temperatura ambiental promedio y correlacion con demanda',
    '- Proyeccion de generacion/demanda para el siguiente periodo',
    '- Restricciones de red, cortes programados o situaciones de emergencia'
  ].join('\n'),
  GENERAL: [
    '- Variables cuantitativas mas importantes del documento',
    '- Indicadores de riesgo, alertas criticas o situaciones de emergencia',
    '- Tendencias principales y anomalias detectadas',
    '- Recomendaciones operativas inmediatas y de corto plazo',
    '- Proyecciones, estimaciones o datos prospectivos clave',
    '- Cualquier valor fuera de rango normal que requiera accion'
  ].join('\n')
};

const variables = variablesPorSector[sector] || variablesPorSector.GENERAL;

// Limitar texto a 80.000 chars para no exceder tokens de Gemini Flash
const LIMITE_CHARS = 80000;
const textoCortado = textoExtraido.length > LIMITE_CHARS;
const textoFinal = textoCortado
  ? textoExtraido.substring(0, LIMITE_CHARS) + '\n\n[--- DOCUMENTO TRUNCADO POR LONGITUD: se procesaron los primeros 80.000 caracteres ---]'
  : textoExtraido;

const esquemaRespuesta = JSON.stringify({
  empresa: empresa,
  sector: sector,
  documento_procesado: '<tipo o nombre del documento analizado>',
  periodo_cubierto: '<periodo temporal del reporte, ej: Febrero 2026, o null>',
  resumen_ejecutivo: [
    '<viñeta 1 con emoji de urgencia>',
    '<viñeta 2 con emoji de urgencia>',
    '<viñeta 3 con emoji de urgencia>',
    '<viñeta 4 con emoji de urgencia>',
    '<viñeta 5 con emoji de urgencia>'
  ],
  alerta_critica: '<descripcion de la alerta mas urgente del documento, o null si no hay alertas>',
  proxima_accion: '<la accion operativa inmediata mas importante que debe tomar la empresa>',
  confianza_extraccion: 'alta|media|baja'
}, null, 2);

const prompt = `Eres un analista experto en meteorologia operativa y gestion de riesgos para el sector ${sector}, trabajando para la empresa "${empresa}".

Tu tarea: leer el siguiente documento tecnico completo y extraer UNICAMENTE las variables criticas de mayor impacto operativo para las actividades diarias de la empresa.

== VARIABLES PRIORITARIAS A IDENTIFICAR ==
${variables}

== DOCUMENTO A ANALIZAR ==
---
${textoFinal}
---
== FIN DEL DOCUMENTO ==

== INSTRUCCIONES ESTRICTAS ==
1. Genera EXACTAMENTE 5 vinetas ejecutivas en "resumen_ejecutivo"
2. Cada vineta debe ser: concisa (maximo 2 oraciones), 100% accionable, con valores numericos concretos cuando esten disponibles
3. Usa SIEMPRE estos prefijos de urgencia al inicio de cada vineta:
   - 🔴 CRITICO: requiere accion inmediata (alertas, valores extremos)
   - 🟡 ATENCION: requiere monitoreo proximo (valores en limite, tendencias)
   - 🟢 NORMAL: condicion dentro de parametros (informacion favorable)
   - 🔵 INFO: dato relevante sin urgencia operativa
4. Prioriza alertas y valores que requieran accion en las proximas 24-72 horas
5. Si no hay suficientes datos para una vineta, escribe exactamente: "🔵 INFO: Sin datos suficientes en el documento para esta categoria"
6. El campo "alerta_critica" debe ser null (sin comillas) si no hay alertas 🔴
7. Sé especifico: menciona fechas, horas, coordenadas o regiones geograficas si el documento las incluye

RESPONDE SOLAMENTE CON EL SIGUIENTE JSON (absolutamente sin markdown, sin bloques de codigo, sin texto adicional antes o despues):
${esquemaRespuesta}`;

const requestBody = {
  contents: [{
    role: 'user',
    parts: [{ text: prompt }]
  }],
  generationConfig: {
    temperature: 0.15,
    maxOutputTokens: 2048,
    topP: 0.8,
    topK: 40
  },
  safetySettings: [
    { category: 'HARM_CATEGORY_HARASSMENT', threshold: 'BLOCK_NONE' },
    { category: 'HARM_CATEGORY_HATE_SPEECH', threshold: 'BLOCK_NONE' },
    { category: 'HARM_CATEGORY_SEXUALLY_EXPLICIT', threshold: 'BLOCK_NONE' },
    { category: 'HARM_CATEGORY_DANGEROUS_CONTENT', threshold: 'BLOCK_NONE' }
  ]
};

return [{
  json: {
    requestBody: requestBody,
    sector: sector,
    empresa: empresa,
    session_id: sessionId,
    nombre_archivo: nombreArchivo,
    texto_chars: textoFinal.length,
    texto_truncado: textoCortado,
    tamano_mb: tamanioMB,
    origen: origen
  }
}];
"""

NORMALIZAR_PDF = r"""// Une extract PDF + metadata de Validar Archivo → forma canónica
const extract = $input.first().json || {};
const meta = $('Validar Archivo').item.json || {};
const texto = (extract.text || extract.data || '').toString();

return [{
  json: {
    texto_documento: texto,
    sector: meta.sector || 'GENERAL',
    empresa: meta.empresa || 'Empresa',
    session_id: meta.session_id || `drc-${Date.now()}`,
    nombre_archivo: meta.nombre_archivo || 'documento.pdf',
    tamano_mb: meta.tamano_mb || 0,
    origen: 'webhook'
  }
}];
"""

NORMALIZAR_TRIGGER = r"""// Entrada del Agente Principal (Tool Workflow)
const inputData = $input.first().json || {};
const texto = (inputData.texto_documento || inputData.text || '').toString();
const sector = (inputData.sector || 'GENERAL').toString().toUpperCase().trim();
const empresa = (inputData.empresa || 'Empresa').toString().trim();
const sessionId = inputData.session_id || `drc-agent-${Date.now()}`;

const sectoresValidos = ['AGRO', 'NAVAL', 'AEREO', 'ENERGIA', 'GENERAL'];
const sectorFinal = sectoresValidos.includes(sector) ? sector : 'GENERAL';

return [{
  json: {
    texto_documento: texto,
    sector: sectorFinal,
    empresa: empresa.replace(/[^\w\sáéíóúÁÉÍÓÚñÑ.,\-]/g, '').substring(0, 100) || 'Empresa',
    session_id: sessionId,
    nombre_archivo: inputData.nombre_archivo || 'Documento_Analizado_por_IA',
    tamano_mb: 0,
    origen: 'subworkflow'
  }
}];
"""

# Update Formatear to keep origen in metadata
FORMATEAR_NEW = FORMATEAR.replace(
    "modelo_ia: 'gemini-2.0-flash',\n      parse_exitoso: parseExitoso,\n      timestamp: new Date().toISOString()",
    "modelo_ia: 'gemini-2.0-flash',\n      parse_exitoso: parseExitoso,\n      origen: promptData.origen || 'subworkflow',\n      timestamp: new Date().toISOString()",
)

new_nodes = [
    {
        "parameters": WEBHOOK,
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2.1,
        "position": [200, 480],
        "id": "drc001-4f8a-4b2c-9e1d-a3b7c8d9e0f1",
        "name": "Webhook Devorador",
        "webhookId": "devorador-reportes-2026-v1",
    },
    {
        "parameters": {"jsCode": SECRET_CODE},
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [420, 480],
        "id": "drc002-5a9b-4c3d-8f2e-b4c8d9e0f1a2",
        "name": "Validar Secreto",
    },
    {
        "parameters": {"jsCode": VALIDAR_ARCHIVO},
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [640, 480],
        "id": "drc003-6b0c-4d4e-7a3f-c5d9e0f1a2b3",
        "name": "Validar Archivo",
    },
    {
        "parameters": {
            "operation": "text",
            "binaryPropertyName": "data0",
        },
        "type": "n8n-nodes-base.extractFromFile",
        "typeVersion": 1,
        "position": [860, 480],
        "id": "drc004-7c1d-4e5f-6b4a-d6e0f1a2b3c4",
        "name": "Extraer Texto PDF",
    },
    {
        "parameters": {"jsCode": NORMALIZAR_PDF},
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1080, 480],
        "id": "drc009-norm-pdf-0001",
        "name": "Normalizar Entrada PDF",
    },
    {
        "parameters": {
            "workflowInputs": {
                "values": [
                    {"name": "texto_documento"},
                    {"name": "sector"},
                    {"name": "empresa"},
                    {"name": "session_id"},
                ]
            }
        },
        "type": "n8n-nodes-base.executeWorkflowTrigger",
        "typeVersion": 1.1,
        "position": [200, 160],
        "id": "drc010-exec-trigger-0001",
        "name": "Execute Workflow Trigger",
    },
    {
        "parameters": {"jsCode": NORMALIZAR_TRIGGER},
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [480, 160],
        "id": "drc011-norm-trigger-0001",
        "name": "Normalizar Entrada Agente",
    },
    {
        "parameters": {"jsCode": PREPARAR_NEW},
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1320, 320],
        "id": "drc005-8d2e-4f6a-5c5b-e7f1a2b3c4d5",
        "name": "Preparar Prompt Sectorial",
    },
    {
        "parameters": GEMINI,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [1540, 320],
        "id": "drc006-9e3f-4a7b-4d6c-f8a2b3c4d5e6",
        "name": "Llamar Gemini API",
    },
    {
        "parameters": {"jsCode": FORMATEAR_NEW},
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1760, 320],
        "id": "drc007-0f4a-4b8c-3e7d-a9b3c4d5e6f7",
        "name": "Formatear Respuesta",
    },
    {
        "parameters": {
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "strict",
                    "version": 2,
                },
                "conditions": [
                    {
                        "id": "cond-webhook-origen",
                        "leftValue": "={{ $json.metadata.origen }}",
                        "rightValue": "webhook",
                        "operator": {
                            "type": "string",
                            "operation": "equals",
                        },
                    }
                ],
                "combinator": "and",
            },
            "options": {},
        },
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [1980, 320],
        "id": "drc012-if-webhook-0001",
        "name": "¿Viene de Webhook?",
    },
    {
        "parameters": RESPONDER,
        "type": "n8n-nodes-base.respondToWebhook",
        "typeVersion": 1.1,
        "position": [2220, 200],
        "id": "drc008-1a5b-4c9d-2f8e-b0c4d5e6f7a8",
        "name": "Responder Exito",
    },
]

connections = {
    "Webhook Devorador": {
        "main": [[{"node": "Validar Secreto", "type": "main", "index": 0}]]
    },
    "Validar Secreto": {
        "main": [[{"node": "Validar Archivo", "type": "main", "index": 0}]]
    },
    "Validar Archivo": {
        "main": [[{"node": "Extraer Texto PDF", "type": "main", "index": 0}]]
    },
    "Extraer Texto PDF": {
        "main": [[{"node": "Normalizar Entrada PDF", "type": "main", "index": 0}]]
    },
    "Normalizar Entrada PDF": {
        "main": [[{"node": "Preparar Prompt Sectorial", "type": "main", "index": 0}]]
    },
    "Execute Workflow Trigger": {
        "main": [[{"node": "Normalizar Entrada Agente", "type": "main", "index": 0}]]
    },
    "Normalizar Entrada Agente": {
        "main": [[{"node": "Preparar Prompt Sectorial", "type": "main", "index": 0}]]
    },
    "Preparar Prompt Sectorial": {
        "main": [[{"node": "Llamar Gemini API", "type": "main", "index": 0}]]
    },
    "Llamar Gemini API": {
        "main": [[{"node": "Formatear Respuesta", "type": "main", "index": 0}]]
    },
    "Formatear Respuesta": {
        "main": [[{"node": "¿Viene de Webhook?", "type": "main", "index": 0}]]
    },
    "¿Viene de Webhook?": {
        "main": [
            [{"node": "Responder Exito", "type": "main", "index": 0}],
            [],  # false: fin del sub-workflow → salida = Formatear (via IF pass-through)
        ]
    },
}

# For sub-workflow return value: n8n returns last node output on the executed branch.
# Empty false branch may return IF output. Safer: add passthrough "Salida Agente" on false.
salida_agente = {
    "parameters": {
        "assignments": {
            "assignments": [
                {
                    "id": "keep-success",
                    "name": "success",
                    "value": "={{ $json.success }}",
                    "type": "boolean",
                },
                {
                    "id": "keep-analisis",
                    "name": "analisis",
                    "value": "={{ $json.analisis }}",
                    "type": "object",
                },
                {
                    "id": "keep-metadata",
                    "name": "metadata",
                    "value": "={{ $json.metadata }}",
                    "type": "object",
                },
            ]
        },
        "options": {},
    },
    "type": "n8n-nodes-base.set",
    "typeVersion": 3.4,
    "position": [2220, 440],
    "id": "drc013-salida-agente-0001",
    "name": "Salida Agente",
}
new_nodes.append(salida_agente)
connections["¿Viene de Webhook?"]["main"][1] = [
    {"node": "Salida Agente", "type": "main", "index": 0}
]

out = {
    "name": "Devorador de Reportes — Procesamiento Documental",
    "nodes": new_nodes,
    "connections": connections,
    "settings": {
        "executionOrder": "v1",
        "saveManualExecutions": True,
        "callerPolicy": "workflowsFromSameOwner",
        "errorWorkflow": "",
    },
    "staticData": None,
    "tags": [],
    "pinData": {},
}

path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("Wrote", path)
print("nodes:", [n["name"] for n in new_nodes])
