"""Force Modulo_Generar_Reporte on main path when user asks PDF (like chart salvage)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# ── Fix subworkflow: name + safe code + mensaje_respuesta ───────────────────
rep_path = ROOT / "modulo_generar_reporte.json"
rep = json.loads(rep_path.read_text(encoding="utf-8"))
rep["name"] = "Modulo_Generar_Reporte"

SAFE_CODE = r"""
const trigger = $('Execute Workflow Trigger').first().json || {};
let htmlContent = trigger.contenido_reporte || trigger.html || trigger.texto || trigger.output || '';
htmlContent = String(htmlContent || '').trim();
if (!htmlContent || htmlContent.length < 20) {
  htmlContent = '<h1>Reporte TuClima</h1><p>No se recibio contenido suficiente del analisis. Pedi el PDF de nuevo.</p>';
}
// Si viene texto plano, envolver
if (!/<\s*(h1|h2|p|table|div|html)\b/i.test(htmlContent)) {
  const esc = htmlContent
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\n/g, '<br/>');
  htmlContent = '<h1>Reporte TuClima IA</h1><div>' + esc + '</div>';
}
const stamp = new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14);
return [{
  json: { _ok: true },
  binary: {
    data: {
      data: Buffer.from(htmlContent, 'utf8').toString('base64'),
      mimeType: 'text/html',
      fileName: 'Reporte_TuClima_' + stamp + '.html',
      fileExtension: 'html'
    }
  }
}];
""".strip()

for node in rep["nodes"]:
    if node.get("name") == "Code in JavaScript":
        node["parameters"]["jsCode"] = SAFE_CODE
    if node.get("name") == "Edit Fields":
        # Keep their Capturar File ID expression if present, add mensaje_respuesta
        assigns = node["parameters"]["assignments"]["assignments"]
        # Ensure link_descarga exists
        names = {a["name"] for a in assigns}
        if "link_descarga" not in names:
            assigns.append({
                "id": "link-dl-001",
                "name": "link_descarga",
                "value": "=https://drive.google.com/file/d/{{ $('Capturar File ID').item.json.file_id }}/view?usp=sharing",
                "type": "string",
            })
        if "mensaje_respuesta" not in names:
            assigns.append({
                "id": "msg-resp-001",
                "name": "mensaje_respuesta",
                "value": "=✅ Reporte listo:\n\n[Abrir reporte TuClima](https://drive.google.com/file/d/{{ $('Capturar File ID').item.json.file_id }}/view?usp=sharing)",
                "type": "string",
            })
        # Fix link if it still references Capturar File ID - keep as is
        print("Edit Fields: mensaje_respuesta ok")

# Upload continueOnFail
for node in rep["nodes"]:
    if node.get("name") in ("Upload file", "Share File (Public)", "Share public"):
        node["continueOnFail"] = True

rep_path.write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("modulo_generar_reporte.json fixed, name=", rep["name"])

# ── Patch chatbot: Code 2 flags + IF + Execute Workflow + merge link ────────
chat_path = ROOT / "chatbot_tuclima.json"
chat = json.loads(chat_path.read_text(encoding="utf-8"))

# Patch Code 2 to set pide_pdf / contenido_reporte / ya_tiene_link
for node in chat["nodes"]:
    if node.get("name") != "Code 2":
        continue
    code = node["parameters"]["jsCode"]
    if "pide_pdf" in code and "contenido_reporte_forzado" in code:
        print("Code 2 already has force flags")
        break
    inject_flags = r"""
// Flags para forzar PDF/Excel en el flujo principal (no depender del Agent tool call)
const _msgUser = String(userMessage || webhookData.chatInput || '').toLowerCase();
const pide_pdf = /\b(pdf|reporte|informe)\b/i.test(_msgUser);
const pide_excel = /\b(excel|planilla|spreadsheet|sheets)\b/i.test(_msgUser);
const ya_tiene_link = /drive\.google\.com\/file|docs\.google\.com\/spreadsheets|Abrir reporte|Abrir planilla/i.test(String(respuestaIA));
let contenido_reporte_forzado = String(respuestaIA || '').replace(/\[MOSTRAR_GRAFICO\][\s\S]*/i, '').trim();
if (pide_pdf && contenido_reporte_forzado.length < 40) {
  contenido_reporte_forzado = '<h1>Reporte TuClima IA</h1><p>Pedido: ' +
    String(userMessage || '').replace(/[<>]/g, '') +
    '</p><p>La IA no devolvio analisis suficiente. Reintentá pidiendo el reporte con ubicacion.</p>';
}
"""
    # Insert before outputCompleto
    marker = "const outputCompleto = {"
    if marker not in code:
        print("ERROR: outputCompleto marker missing")
        break
    code = code.replace(marker, inject_flags + "\n" + marker, 1)
    # Add fields to outputCompleto
    code = code.replace(
        "chart_block: (typeof chart_block !== 'undefined' ? chart_block : ''),",
        "chart_block: (typeof chart_block !== 'undefined' ? chart_block : ''),\n"
        "    pide_pdf: typeof pide_pdf !== 'undefined' ? pide_pdf : false,\n"
        "    pide_excel: typeof pide_excel !== 'undefined' ? pide_excel : false,\n"
        "    ya_tiene_link: typeof ya_tiene_link !== 'undefined' ? ya_tiene_link : false,\n"
        "    contenido_reporte_forzado: typeof contenido_reporte_forzado !== 'undefined' ? contenido_reporte_forzado : '',",
        1,
    )
    node["parameters"]["jsCode"] = code
    print("Code 2: force flags added")
    break

# Add new nodes if missing
existing = {n["name"] for n in chat["nodes"]}

IF_NODE = {
    "parameters": {
        "conditions": {
            "options": {
                "caseSensitive": True,
                "leftValue": "",
                "typeValidation": "loose",
                "version": 2,
            },
            "conditions": [
                {
                    "id": "cond-pdf-force-001",
                    "leftValue": "={{ $json.pide_pdf === true && $json.ya_tiene_link !== true }}",
                    "rightValue": True,
                    "operator": {
                        "type": "boolean",
                        "operation": "true",
                        "singleValue": True,
                    },
                }
            ],
            "combinator": "and",
        },
        "options": {},
    },
    "type": "n8n-nodes-base.if",
    "typeVersion": 2.2,
    "position": [5488, 32],
    "id": "if-force-pdf-001",
    "name": "IF Forzar PDF",
}

EXEC_NODE = {
    "parameters": {
        "workflowId": {
            "__rl": True,
            "value": "Modulo_Generar_Reporte",
            "mode": "name",
            "cachedResultName": "Modulo_Generar_Reporte",
        },
        "workflowInputs": {
            "mappingMode": "defineBelow",
            "value": {
                "contenido_reporte": "={{ $json.contenido_reporte_forzado || $json.output || $json.texto_limpio || '' }}"
            },
        },
        "options": {},
    },
    "type": "n8n-nodes-base.executeWorkflow",
    "typeVersion": 1.2,
    "position": [5680, -80],
    "id": "exec-force-pdf-001",
    "name": "Forzar_Modulo_Generar_Reporte",
    "continueOnFail": True,
}

MERGE_LINK = {
    "parameters": {
        "jsCode": r"""
const prev = $('Code 2').first().json || {};
const sub = $input.first().json || {};
const link = sub.link_descarga || sub.url_reporte || '';
const msgTool = sub.mensaje_respuesta || '';
let output = String(prev.output || prev.texto_limpio || '');
const already = /drive\.google\.com\/file/i.test(output);
if (msgTool && !already) {
  output = (output && !/Sin respuesta/i.test(output) ? output.trim() + '\n\n' : '') + msgTool;
} else if (link && !already) {
  output = (output && !/Sin respuesta/i.test(output) ? output.trim() + '\n\n' : '') +
    '✅ Reporte listo:\n\n[Abrir reporte TuClima](' + link + ')';
} else if (!output.trim() || /Sin respuesta/i.test(output)) {
  output = msgTool || (link ? '[Abrir reporte TuClima](' + link + ')' : 'No pude generar el archivo PDF. Revisá que el workflow Modulo_Generar_Reporte esté activo.');
}
return [{
  json: {
    ...prev,
    output,
    texto_limpio: output.replace(/\[MOSTRAR_GRAFICO\][\s\S]*/i, '').trim(),
    chart_block: prev.chart_block || '',
    link_descarga: link || prev.link_descarga || '',
    pide_pdf: false,
    ya_tiene_link: true
  }
}];
""".strip()
    },
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [5888, -80],
    "id": "merge-pdf-link-001",
    "name": "Adjuntar_Link_PDF",
}

if "IF Forzar PDF" not in existing:
    chat["nodes"].extend([IF_NODE, EXEC_NODE, MERGE_LINK])
    print("Added IF + Execute + Adjuntar nodes")
else:
    print("Force PDF nodes already exist — updating params")
    for node in chat["nodes"]:
        if node["name"] == "Forzar_Modulo_Generar_Reporte":
            node["parameters"] = EXEC_NODE["parameters"]
            node["continueOnFail"] = True
        if node["name"] == "Adjuntar_Link_PDF":
            node["parameters"] = MERGE_LINK["parameters"]
        if node["name"] == "IF Forzar PDF":
            node["parameters"] = IF_NODE["parameters"]

# Rewire connections:
# Code 2 → Create a row (keep)
# Code 2 → IF Forzar PDF (instead of direct Edit Fields)
# IF true → Forzar_Modulo → Adjuntar → Edit Fields
# IF false → Edit Fields
conns = chat["connections"]
conns["Code 2"] = {
    "main": [
        [
            {"node": "Create a row", "type": "main", "index": 0},
            {"node": "IF Forzar PDF", "type": "main", "index": 0},
        ]
    ]
}
conns["IF Forzar PDF"] = {
    "main": [
        [{"node": "Forzar_Modulo_Generar_Reporte", "type": "main", "index": 0}],  # true
        [{"node": "Edit Fields", "type": "main", "index": 0}],  # false
    ]
}
conns["Forzar_Modulo_Generar_Reporte"] = {
    "main": [[{"node": "Adjuntar_Link_PDF", "type": "main", "index": 0}]]
}
conns["Adjuntar_Link_PDF"] = {
    "main": [[{"node": "Edit Fields", "type": "main", "index": 0}]]
}
print("Connections rewired")

chat_path.write_text(json.dumps(chat, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("chatbot saved")
