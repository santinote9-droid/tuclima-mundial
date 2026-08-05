"""
Stop AI Agent max-iterations loops on PDF/climate:
1) PDF: do NOT require Modulo_Generar_Reporte (forced later)
2) Disconnect SerpAPI (burns iterations)
3) Agent continueOnFail + Code 2 always reads webhook for pide_pdf
"""
import json
import re
from pathlib import Path

p = Path(__file__).resolve().parent / "chatbot_tuclima.json"
c = json.loads(p.read_text(encoding="utf-8"))

# New prompt text for AI Agent — PDF order no longer forces report tool
NEW_TEXT = r"""={{ $('Webhook').item.json.body.chatInput }}
{{ $json.contexto_memoria ? '\n[MEMORIA]\n' + String($json.contexto_memoria).substring(0, 4000) : '' }}
{{ $json.imageAnalysis ? '\n[VISION]\n' + String($json.imageAnalysis).substring(0, 4000) : '' }}
{{ $json.text ? '\n[DATOS COPIA]\n' + String($json.text).substring(0, 8000) : ($json.data ? '\n[DATOS COPIA]\n' + (typeof $json.data === 'string' ? String($json.data).substring(0, 8000) : JSON.stringify($json.data).substring(0, 8000)) : '') }}
{{ $('Webhook').item.json.body.sector ? '\n[SECTOR]\n' + $('Webhook').item.json.body.sector : '' }}
{{ (() => {
  const m = String($('Webhook').item.json.body.chatInput || $json.mensaje_actual || '').toLowerCase();
  if (m.includes('pdf') || m.includes('reporte') || m.includes('informe')) {
    return '\n[ORDEN SISTEMA — PDF]\n' +
      'El usuario pide un reporte/PDF. HACÉ ESTO Y CERRÁ:\n' +
      '1) Llamá obtener_clima UNA vez (ubicacion del mensaje).\n' +
      '2) Llamá SOLO la tool del sector UNA vez (agro→consultar_agro, aereo→consultar_aereo, naval→obtener_mar, energia→consultar_energia).\n' +
      '3) Escribí YA la respuesta final en español con resumen tecnico + datos numericos (HTML simple con h1/h2/p/table si podes).\n' +
      'PROHIBIDO: SerpAPI, buscar en web, consultar_perfil, Modulo_Generar_Reporte, Modulo_Generar_Excel, Modulo_*_BI, reintentar tools.\n' +
      'El archivo PDF lo genera el sistema DESPUES automaticamente. Tu trabajo es SOLO el texto/analisis y TERMINAR.';
  }
  if (m.includes('excel') || m.includes('planilla') || m.includes('spreadsheet')) {
    return '\n[ORDEN SISTEMA — EXCEL]\nPedí datos con 1-2 tools y llama Modulo_Generar_Excel una vez. Luego respuesta final. Sin SerpAPI.';
  }
  if (/gr[aá]fico|dashboard|visualiz/.test(m)) {
    return '\n[ORDEN SISTEMA — GRAFICO]\nDatos (1-2 tools) y LUEGO Modulo_*_BI del sector UNA vez. Sin SerpAPI. Cerrá con texto corto.';
  }
  return '';
})() }}
"""

ANTI = """

## Cierre obligatorio
- Despues de 1-3 tools utiles, DEBES emitir la respuesta final al usuario (texto).
- Si ya tenes datos suficientes, NO llames mas tools.
- SerpAPI / web search: PROHIBIDO para clima, PDF, reporte, grafico, agro, naval, aereo, energia.
- consultar_perfil / alertas / correo: solo si el usuario lo pide explicitamente.
- PDF/reporte: NUNCA llames Modulo_Generar_Reporte (el flujo principal lo fuerza). Solo analisis + respuesta final.
"""

for n in c["nodes"]:
    if n.get("name") != "AI Agent":
        continue
    n["parameters"]["text"] = NEW_TEXT.strip()
    opts = n["parameters"].setdefault("options", {})
    opts["maxIterations"] = 12  # fewer, but stop looping sooner with better prompt
    opts["returnIntermediateSteps"] = True
    sm = opts.get("systemMessage") or ""
    # Remove conflicting "OBLIGATORIO: llamar Modulo_Generar_Reporte" chunks if present
    sm = re.sub(
        r"## PDF[\s\S]*?(?=## |\Z)",
        "## PDF / reportes\n"
        "- Si piden PDF/reporte/informe: obtene datos (clima + sector) y responde con el analisis.\n"
        "- NO llames Modulo_Generar_Reporte: el sistema lo ejecuta despues solo.\n"
        "- No uses SerpAPI para esto.\n\n",
        sm,
        count=1,
    )
    if "Cierre obligatorio" not in sm:
        sm = sm.rstrip() + ANTI
    opts["systemMessage"] = sm
    n["continueOnFail"] = True
    n["onError"] = "continueRegularOutput"
    print("AI Agent prompt + options updated, maxIterations=12")
    break

# Disconnect SerpAPI from AI Agent (keep node, remove link)
serp = c["connections"].get("SerpAPI")
if serp and "ai_tool" in serp:
    del c["connections"]["SerpAPI"]
    print("SerpAPI disconnected from AI Agent")
else:
    print("SerpAPI already disconnected or missing")

# Also disconnect rarely needed tools that burn loops on PDF tasks
for tool in ("Tool_docs", "Tool_Reportes"):
    if tool in c["connections"] and "ai_tool" in c["connections"][tool]:
        # Keep connection — user may need them. Only SerpAPI removed.
        pass

# Harden Code 2: always derive pide_pdf from Webhook even if Agent hard-failed
for n in c["nodes"]:
    if n.get("name") != "Code 2":
        continue
    code = n["parameters"]["jsCode"]
    # Ensure catch / start always can set pide_pdf from webhook
    if "pide_pdf_webhook_force" in code:
        print("Code 2 already hardened")
        break
    marker = "const webhookData = $('Webhook').first()?.json?.body || {};"
    if marker not in code:
        print("WARN: webhookData marker missing in Code 2")
        break
    # After flags section, force pide_pdf from raw webhook if Agent returned error-only
    old_flags = "const pide_pdf = /\\b(pdf|reporte|informe)\\b/i.test(_msgUser);"
    new_flags = (
        "const pide_pdf = /\\b(pdf|reporte|informe)\\b/i.test(_msgUser) "
        "|| /\\b(pdf|reporte|informe)\\b/i.test(String(webhookData.chatInput || '')); "
        "// pide_pdf_webhook_force"
    )
    if old_flags in code:
        code = code.replace(old_flags, new_flags, 1)
        print("Code 2 pide_pdf hardened")
    else:
        print("WARN: pide_pdf flag line not found")

    # If Agent failed with empty output, still mark for PDF force path
    if "errorMessage" not in code[:800]:
        inject = """
// Si el Agent fallo (max iterations) y vino vacio/error, no tumbar el chat
const _agentErr = String(aiNodeData.error?.message || aiNodeData.errorMessage || aiNodeData.message || '');
if ((!String(respuestaIA).trim() || /Max iterations|could not complete/i.test(_agentErr + String(respuestaIA))) && !/Alcance el limite/i.test(String(respuestaIA))) {
  // leave respuestaIA; flags below will force PDF if asked
}
"""
        # already have max iterations salvage from before; skip duplicate
    n["parameters"]["jsCode"] = code
    break

# Ensure Adjuntar / IF still wired
assert "IF Forzar PDF" in {x["name"] for x in c["nodes"]}
assert "Forzar_Modulo_Generar_Reporte" in {x["name"] for x in c["nodes"]}
print("Force PDF nodes present")

p.write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("saved ok")
