"""Upload report as convertible Google Doc (not raw HTML source preview)."""
import json
from pathlib import Path

path = Path(__file__).resolve().parent / "modulo_generar_reporte.json"
rep = json.loads(path.read_text(encoding="utf-8"))
rep["name"] = "Modulo_Generar_Reporte"

SAFE_CODE = r"""
const trigger = $('Execute Workflow Trigger').first().json || {};
let htmlContent = trigger.contenido_reporte || trigger.html || trigger.texto || trigger.output || '';
htmlContent = String(htmlContent || '').trim();

// Limpiar LaTeX crudo de Gemini
htmlContent = htmlContent.replace(/\$([^$]+)\$/g, (_, inner) => String(inner)
  .replace(/\\%/g, '%')
  .replace(/\\circ/g, '°')
  .replace(/\\text\{([^}]*)\}/g, '$1')
  .replace(/\\mathrm\{([^}]*)\}/g, '$1')
  .replace(/\\sim/g, '~')
  .replace(/\\times/g, '×')
  .replace(/\\,/g, ' ')
  .replace(/[{}]/g, '')
  .replace(/\^/g, '')
  .replace(/\\/g, '')
);

if (!htmlContent || htmlContent.length < 20) {
  htmlContent = '<h1>Reporte TuClima</h1><p>No se recibio contenido suficiente del analisis. Pedi el PDF de nuevo.</p>';
}

// Si viene markdown/texto plano, convertir a HTML simple
if (!/<\s*(h1|h2|p|table|div|html|body)\b/i.test(htmlContent)) {
  const esc = htmlContent
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\n/g, '<br/>');
  htmlContent = '<h1>Reporte TuClima IA</h1><div>' + esc + '</div>';
}

// Documento HTML completo → Google Docs lo importa bien al convertir
const docHtml = '<!DOCTYPE html><html><head><meta charset="utf-8">'
  + '<title>Reporte TuClima</title>'
  + '<style>body{font-family:Arial,sans-serif;line-height:1.45;color:#111;max-width:800px;margin:24px auto;padding:0 16px}'
  + 'h1{font-size:22px;border-bottom:2px solid #1e3a8a;padding-bottom:8px}h2{font-size:16px;color:#1e3a8a;margin-top:22px}'
  + 'table{border-collapse:collapse;width:100%;margin:12px 0}th,td{border:1px solid #cbd5e1;padding:8px;text-align:left;font-size:13px}'
  + 'th{background:#e2e8f0}strong{color:#0f172a}</style></head><body>'
  + htmlContent.replace(/^[\s\S]*?<body[^>]*>/i, '').replace(/<\/body>[\s\S]*$/i, '')
  + '</body></html>';

const stamp = new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14);
// .doc + msword: Drive convierte a Google Doc (preview legible, no codigo fuente)
return [{
  json: { _ok: true, _stamp: stamp },
  binary: {
    data: {
      data: Buffer.from(docHtml, 'utf8').toString('base64'),
      mimeType: 'application/msword',
      fileName: 'Reporte_TuClima_' + stamp + '.doc',
      fileExtension: 'doc'
    }
  }
}];
""".strip()

for node in rep["nodes"]:
    if node.get("name") == "Code in JavaScript":
        node["parameters"]["jsCode"] = SAFE_CODE
        print("Code updated")
    if node.get("name") == "Upload file":
        node["parameters"]["name"] = '=Reporte_TuClima_{{$now.format("yyyyMMdd_HHmm")}}'
        # Pedir conversion a Google Doc si el nodo lo soporta
        opts = node["parameters"].setdefault("options", {})
        opts["convertToGoogleDocument"] = True
        node["continueOnFail"] = True
        print("Upload updated convertToGoogleDocument")
    if node.get("name") == "Edit Fields":
        assigns = node["parameters"]["assignments"]["assignments"]
        for a in assigns:
            if a.get("name") == "link_descarga":
                # Preferir link de Google Doc (tras conversion) con fallback Drive
                a["value"] = (
                    "=https://docs.google.com/document/d/"
                    "{{ $('Capturar File ID').item.json.file_id }}/edit?usp=sharing"
                )
            if a.get("name") == "mensaje_respuesta":
                a["value"] = (
                    "=✅ Reporte listo:\n\n"
                    "[Abrir reporte TuClima](https://docs.google.com/document/d/"
                    "{{ $('Capturar File ID').item.json.file_id }}/edit?usp=sharing)"
                )
        print("Edit Fields links -> docs.google.com/document")

path.write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("saved ok")
