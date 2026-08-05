"""Update Adjuntar_Link_PDF: no HTML dump, strip LaTeX, keep Drive/Docs link."""
import json
from pathlib import Path

p = Path(__file__).resolve().parent / "chatbot_tuclima.json"
c = json.loads(p.read_text(encoding="utf-8"))

JS = r"""
const prev = $('Code 2').first().json || {};
const sub = $input.first().json || {};
const link = sub.link_descarga || sub.url_reporte || '';
const msgTool = sub.mensaje_respuesta || '';
let output = String(prev.output || prev.texto_limpio || '');

// No volcar HTML crudo al chat
if (/<\s*(html|h1|table|body)\b/i.test(output) || (output.match(/<\w+[\s>]/g) || []).length > 8) {
  output = output
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/p>/gi, '\n')
    .replace(/<\/h[1-6]>/gi, '\n')
    .replace(/<\/li>/gi, '\n')
    .replace(/<\/tr>/gi, '\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
  if (output.length > 1200) output = output.slice(0, 1200).trim() + '\u2026';
}

// Limpiar LaTeX
output = output.replace(/\$([^$]+)\$/g, (_, inner) => String(inner)
  .replace(/\\%/g, '%').replace(/\\circ/g, '\u00b0')
  .replace(/\\text\{([^}]*)\}/g, '$1')
  .replace(/\\mathrm\{([^}]*)\}/g, '$1')
  .replace(/\\sim/g, '~').replace(/\\times/g, '\u00d7')
  .replace(/\\,/g, ' ').replace(/[{}]/g, '').replace(/\^/g, '').replace(/\\/g, '')
);

const already = /drive\.google\.com\/file|docs\.google\.com\/document|Abrir reporte/i.test(output);
if (msgTool && !already) {
  output = (output && !/Sin respuesta/i.test(output) ? output.trim() + '\n\n' : '') + msgTool;
} else if (link && !already) {
  output = (output && !/Sin respuesta/i.test(output) ? output.trim() + '\n\n' : '') +
    '\u2705 Reporte listo:\n\n[Abrir reporte TuClima](' + link + ')';
} else if (!output.trim() || /Sin respuesta/i.test(output)) {
  output = msgTool || (link ? '[Abrir reporte TuClima](' + link + ')' : 'No pude generar el archivo. Revis\u00e1 que Modulo_Generar_Reporte est\u00e9 activo.');
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

for n in c["nodes"]:
    if n.get("name") == "Adjuntar_Link_PDF":
        n["parameters"]["jsCode"] = JS
        print("Adjuntar_Link_PDF updated")
        break
else:
    print("WARN: Adjuntar_Link_PDF not found")

p.write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("saved")
