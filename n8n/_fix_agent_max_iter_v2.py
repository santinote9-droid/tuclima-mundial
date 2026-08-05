"""Bump maxIterations + block SerpAPI loops on climate/PDF tasks."""
import json
from pathlib import Path

p = Path(__file__).resolve().parent / "chatbot_tuclima.json"
c = json.loads(p.read_text(encoding="utf-8"))

EXTRA = """

## Anti-bucle tools (importante)
- Para clima/reporte/PDF/grafico: NUNCA uses SerpAPI ni buscar en web. Usa obtener_clima + tool del sector.
- No llames consultar_perfil salvo que el usuario pida su cuenta/perfil.
- Simple Memory ya viene inyectada: no la uses como tool repetida.
- Pedido de PDF/reporte: maximo 2 tools de datos (clima + sector), luego RESUME en texto. El sistema genera el archivo despues si hace falta.
"""

for n in c["nodes"]:
    if n.get("name") != "AI Agent":
        continue
    opts = n.setdefault("parameters", {}).setdefault("options", {})
    opts["maxIterations"] = 25
    opts["returnIntermediateSteps"] = True
    sm = opts.get("systemMessage") or ""
    if "Anti-bucle tools" not in sm:
        opts["systemMessage"] = sm.rstrip() + EXTRA
    n["continueOnFail"] = True
    n["onError"] = "continueRegularOutput"
    print("AI Agent: maxIterations=25, returnIntermediateSteps=True")
    break

p.write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("saved")
print("VERIFY_IN_RAILWAY: open AI Agent > Options > Max Iterations must show 25")
