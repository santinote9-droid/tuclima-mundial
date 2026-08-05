"""Raise AI Agent maxIterations + anti-loop prompt + continueOnFail salvage."""
import json
from pathlib import Path

p = Path(__file__).resolve().parent / "chatbot_tuclima.json"
c = json.loads(p.read_text(encoding="utf-8"))

ANTI_LOOP = """

## Limite de pasos (CRITICO — evita Max iterations)
- Maximo 6 llamadas a tools por mensaje. Despues RESPONDE con lo que tengas.
- Cada tool: como mucho 1 vez (salvo que falle con error claro de ubicacion).
- NO reintentes la misma tool con los mismos argumentos.
- Orden tipico eficiente:
  1) obtener_clima (si hace falta)
  2) tool del sector (1 vez)
  3) opcional: Modulo_*_BI O Modulo_Generar_Reporte/Excel (1 vez)
  4) RESPUESTA FINAL al usuario (texto). Obligatorio cerrar.
- Si una tool falla o devuelve vacio: explica el problema y pedi ubicacion/aclaracion. No sigas llamando tools en bucle.
- PDF/reporte: el sistema tambien puede generar el archivo despues. Prioriza un resumen util en el chat; no gastes todas las iteraciones reintentando el PDF.
- Nunca digas que vas a llamar una tool "en el proximo mensaje": llama ahora o responde ya.
"""

for n in c["nodes"]:
    if n.get("name") != "AI Agent":
        continue
    opts = n.setdefault("parameters", {}).setdefault("options", {})
    # n8n Agent v3: maxIterations in options
    opts["maxIterations"] = 20
    sm = opts.get("systemMessage") or ""
    if "Limite de pasos" not in sm:
        opts["systemMessage"] = sm.rstrip() + ANTI_LOOP
        print("systemMessage: anti-loop appended")
    else:
        print("systemMessage: anti-loop already present")
    # Si igual se corta, no tumbar todo el webhook: Code 2 / IF PDF pueden salvar
    n["continueOnFail"] = True
    n["onError"] = "continueRegularOutput"
    print("maxIterations=20, continueOnFail=True")
    break
else:
    raise SystemExit("AI Agent not found")

# Code 2: si el Agent fallo por max iterations, armar respuesta util
for n in c["nodes"]:
    if n.get("name") != "Code 2":
        continue
    code = n["parameters"]["jsCode"]
    needle = 'let respuestaIA = aiNodeData.output || aiNodeData.text || aiNodeData.response || "";'
    if "Max iterations" in code or "max iterations" in code.lower():
        print("Code 2 already handles max iterations")
        break
    inject = r'''let respuestaIA = aiNodeData.output || aiNodeData.text || aiNodeData.response || "";
// Si el Agent corto por Max iterations / error, recuperar texto parcial
if (!String(respuestaIA).trim() || /Max iterations|could not complete the task/i.test(String(respuestaIA))) {
  const errMsg = String(aiNodeData.error?.message || aiNodeData.errorMessage || aiNodeData.message || respuestaIA || '');
  let partial = '';
  try {
    const steps = aiNodeData.intermediateSteps || aiNodeData.intermediate_steps || [];
    const bits = [];
    for (const step of (Array.isArray(steps) ? steps : [])) {
      let obs = step && (step.observation != null ? step.observation : null);
      if (obs == null) continue;
      if (typeof obs === 'object') {
        try { obs = JSON.stringify(obs); } catch (e) { obs = String(obs); }
      }
      obs = String(obs).trim();
      if (obs.length > 30) bits.push(obs.slice(0, 2500));
    }
    if (bits.length) partial = bits.slice(-3).join('\n\n');
  } catch (e) {}
  if (/Max iterations|could not complete the task/i.test(errMsg) || !String(respuestaIA).trim()) {
    respuestaIA = partial
      ? ('Alcance el limite de pasos del agente. Te dejo el resumen con los datos que si pude obtener:\n\n' + partial.slice(0, 3500))
      : 'La consulta pidio demasiados pasos al agente (limite interno). Reintentá pidiendo una cosa por vez: primero clima/datos, despues grafico o PDF.';
  }
}
'''
    if needle not in code:
        print("WARN: respuestaIA needle missing")
    else:
        # Replace first assignment only — inject already includes let respuestaIA
        code = code.replace(needle, inject, 1)
        n["parameters"]["jsCode"] = code
        print("Code 2: max-iterations salvage added")
    break

p.write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("saved")
