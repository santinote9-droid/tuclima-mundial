"""Harden IF + ExecuteWorkflow + Code 2 contenido for forced PDF path."""
import json
import re
from pathlib import Path

chat_path = Path(__file__).resolve().parent / "chatbot_tuclima.json"
chat = json.loads(chat_path.read_text(encoding="utf-8"))

for node in chat["nodes"]:
    if node.get("name") == "IF Forzar PDF":
        node["parameters"] = {
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "loose",
                    "version": 2,
                },
                "conditions": [
                    {
                        "id": "cond-pdf-1",
                        "leftValue": "={{ $json.pide_pdf }}",
                        "rightValue": True,
                        "operator": {
                            "type": "boolean",
                            "operation": "true",
                            "singleValue": True,
                        },
                    },
                    {
                        "id": "cond-pdf-2",
                        "leftValue": "={{ $json.ya_tiene_link }}",
                        "rightValue": True,
                        "operator": {
                            "type": "boolean",
                            "operation": "false",
                            "singleValue": True,
                        },
                    },
                ],
                "combinator": "and",
            },
            "options": {},
        }
        print("IF updated")

    if node.get("name") == "Forzar_Modulo_Generar_Reporte":
        node["parameters"] = {
            "source": "database",
            "workflowId": {
                "__rl": True,
                "value": "Modulo_Generar_Reporte",
                "mode": "name",
                "cachedResultName": "Modulo_Generar_Reporte",
            },
            "workflowInputs": {
                "mappingMode": "defineBelow",
                "value": {
                    "contenido_reporte": (
                        "={{ $json.contenido_reporte_forzado || "
                        "$json.output || $json.texto_limpio || '' }}"
                    )
                },
            },
            "options": {},
        }
        node["continueOnFail"] = True
        print("ExecuteWorkflow updated")

NEW_CONTENIDO = r"""let contenido_reporte_forzado = String(respuestaIA || '').replace(/\[MOSTRAR_GRAFICO\][\s\S]*/i, '').trim();
// Si la IA solo dijo 'Sin respuesta', armar HTML con observaciones de tools
if (pide_pdf && (/Sin respuesta de la IA/i.test(contenido_reporte_forzado) || contenido_reporte_forzado.length < 80)) {
  const bits = [];
  try {
    const steps = aiNodeData.intermediateSteps || aiNodeData.intermediate_steps || [];
    for (const step of (Array.isArray(steps) ? steps : [])) {
      let obs = step && (step.observation != null ? step.observation : null);
      if (obs == null) continue;
      if (typeof obs === 'object') {
        try { obs = JSON.stringify(obs, null, 2); } catch (e) { obs = String(obs); }
      }
      obs = String(obs).trim();
      if (obs && obs.length > 20 && !/drive\.google\.com/i.test(obs)) bits.push(obs.slice(0, 4000));
    }
  } catch (e) {}
  const body = bits.length
    ? bits.map(b => '<pre style="white-space:pre-wrap;font-size:12px">' + String(b).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') + '</pre>').join('<hr/>')
    : '<p>' + String(contenido_reporte_forzado || 'Sin analisis').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') + '</p>';
  contenido_reporte_forzado = '<h1>Reporte TuClima IA</h1><p><b>Pedido:</b> ' +
    String(userMessage || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') +
    '</p>' + body;
}
"""

NEW_CATCH = r"""} catch (err) {
  const fallback = ($input.first()?.json?.output || $input.first()?.json?.text || 'Error procesando la respuesta de la IA. Reintentá.');
  let wb = {};
  try { wb = $('Webhook').first()?.json?.body || {}; } catch (e) {}
  const um = String(wb.chatInput || wb.message || '');
  const pide = /\b(pdf|reporte|informe)\b/i.test(um);
  return [{
    json: {
      output: String(fallback),
      texto_limpio: String(fallback),
      chart_block: '',
      powerbi_url: null,
      session_id: 'error',
      user_id: null,
      user_message: um,
      ai_response: String(fallback),
      sector: null,
      es_respuesta_climatica: false,
      pide_pdf: pide,
      pide_excel: false,
      ya_tiene_link: false,
      contenido_reporte_forzado: '<h1>Reporte TuClima</h1><p>' + um.replace(/[<>&"]/g,'') + '</p><p>' + String(fallback).replace(/[<>&"]/g,'') + '</p>',
      _code2_error: String(err && err.message ? err.message : err)
    }
  }];
}
"""

for node in chat["nodes"]:
    if node.get("name") != "Code 2":
        continue
    code = node["parameters"]["jsCode"]
    m = re.search(
        r"let contenido_reporte_forzado = String\(respuestaIA[\s\S]*?"
        r"Reintentá pidiendo el reporte con ubicacion\.</p>';\n\}",
        code,
    )
    if m:
        code = code[: m.start()] + NEW_CONTENIDO + code[m.end() :]
        print("Code 2 contenido replaced")
    else:
        print("WARN: contenido block not found")

    m2 = re.search(r"\} catch \(err\) \{[\s\S]*\}\s*$", code)
    if m2:
        code = code[: m2.start()] + NEW_CATCH
        print("catch updated")
    else:
        print("WARN catch not found")
    node["parameters"]["jsCode"] = code
    break

chat_path.write_text(json.dumps(chat, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("saved ok")
