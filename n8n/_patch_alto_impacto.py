"""
Parche de alto impacto para workflows n8n (ejecutar una vez desde repo root).
- Secreto webhook desde $vars.N8N_WEBHOOK_SECRET
- BI + email → Gemini 2.0 Flash
- Descripciones BI sectoriales correctas
- Prompt chatbot compacto + input sin dump completo de $json
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SECRET_CODE = r"""// Validacion de origen — secreto compartido Django ↔ n8n
// Configurar en n8n: Settings → Variables → N8N_WEBHOOK_SECRET
let secretEsperado = '';
try { secretEsperado = String($vars['N8N_WEBHOOK_SECRET'] || '').trim(); } catch (e) {}

const headers = $input.first().json.headers || {};
const secretRecibido = String(
  headers['x-n8n-secret'] || headers['X-N8N-Secret'] || ''
).trim();

if (secretEsperado && secretRecibido !== secretEsperado) {
  throw new Error('401 Unauthorized: X-N8N-Secret invalido o ausente');
}

return $input.all();
"""

COMPACT_SYSTEM = """Sos TuClima IA (Gemini). Asistente técnico operativo para Agro, Naval, Aéreo y Energías.
Respondé en español, claro y accionable. No inventes clima ni datos: usá herramientas.

## Contexto de sesión
- El body trae `sector` (agro|naval|aereo|energia). Priorizá tools de ese sector.
- Si hay bloque [MEMORIA], usalo para continuidad.
- Si hay [VISION] / análisis visual, presentalo y cruzalo con clima real del lugar.
- Si hay [DATOS]/IA] (Excel/PDF), analizá eso primero.

## Jerarquía de tools
1) Datos: `obtener_clima` + tool sectorial (`consultar_agro` / `obtener_mar` / `consultar_aereo` / `consultar_energia`).
2) Gráficos/dashboard/visualización: primero datos reales, luego SOLO el módulo BI del sector:
   - agro → Modulo_Agro_BI
   - naval → Modulo_Naval_BI
   - aereo → Modulo_Aereo_BI
   - energia → Modulo_Energia_BI
   Nunca llames un BI de otro sector. No menciones Power BI ni links: el front dibuja el gráfico.
3) PDF/informe descargable: solo si el usuario lo pide explícitamente (módulo reporte / Docs).
4) Excel: tool Excel cuando pidan planilla/export.
5) Web search: último recurso (noticias o teoría).

## Secuencia gráficos (obligatoria)
PASO 1: obtener_clima + tool del sector.
PASO 2: pasar esos datos al Modulo_*_BI correspondiente.
Prohibido BI sin datos previos.

## Visión
Si hay análisis visual preprocesado: resumí hallazgos → tools de clima/sector → riesgos + recomendaciones.

## Estilo
- Sé breve salvo reportes pedidos.
- Unidades claras (nudos, hPa, mm, kW, GDD, etc.).
- Si faltan datos de tool, decilo y pedí ubicación.
"""

AGENT_TEXT = (
    "={{ $('Webhook').item.json.body.chatInput }}\n"
    "{{ $json.contexto_memoria ? '\\n[MEMORIA]\\n' + String($json.contexto_memoria).substring(0, 4000) : '' }}\n"
    "{{ $json.imageAnalysis ? '\\n[VISION]\\n' + String($json.imageAnalysis).substring(0, 4000) : '' }}\n"
    "{{ $json.text ? '\\n[DATOS COPIA]\\n' + String($json.text).substring(0, 8000) "
    ": ($json.data ? '\\n[DATOS COPIA]\\n' + (typeof $json.data === 'string' "
    "? String($json.data).substring(0, 8000) : JSON.stringify($json.data).substring(0, 8000)) : '') }}\n"
    "{{ $('Webhook').item.json.body.sector ? '\\n[SECTOR]\\n' + $('Webhook').item.json.body.sector : '' }}"
)

BI_DESC_PREFIX = {
    "Modulo_Naval_BI": (
        "ÚSALA ÚNICAMENTE PARA DIBUJAR GRÁFICOS NAVALES (mar, oleaje, puertos, navegación). "
        "🚨 ADVERTENCIA CRÍTICA:"
    ),
    "Modulo_Agro_BI": (
        "ÚSALA ÚNICAMENTE PARA DIBUJAR GRÁFICOS AGRÍCOLAS (cultivos, suelo, pulverización, GDD). "
        "🚨 ADVERTENCIA CRÍTICA:"
    ),
    "Modulo_Energia_BI": (
        "ÚSALA ÚNICAMENTE PARA DIBUJAR GRÁFICOS ENERGÉTICOS (solar, eólica, generación, ROI). "
        "🚨 ADVERTENCIA CRÍTICA:"
    ),
    "Modulo_Aereo_BI": (
        "ÚSALA ÚNICAMENTE PARA DIBUJAR GRÁFICOS AERONÁUTICOS (VFR/IFR, METAR, vuelo). "
        "🚨 ADVERTENCIA CRÍTICA:"
    ),
}

WRONG_PREFIX = (
    "ÚSALA ÚNICAMENTE PARA DIBUJAR GRÁFICOS AERONÁUTICOS. 🚨 ADVERTENCIA CRÍTICA:"
)


def patch_chatbot():
    path = ROOT / "chatbot_tuclima.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    for node in data["nodes"]:
        name = node.get("name")
        params = node.setdefault("parameters", {})

        if name == "Validar Secreto":
            params["jsCode"] = SECRET_CODE

        if name == "Webhook":
            opts = params.setdefault("options", {})
            # Tras proxy Django ya no hace falta CORS abierto
            headers = opts.get("responseHeaders", {}).get("entries", [])
            new_entries = []
            for h in headers:
                if (h.get("name") or "").lower() == "access-control-allow-origin":
                    continue
                new_entries.append(h)
            opts.setdefault("responseHeaders", {})["entries"] = new_entries
            opts["allowedOrigins"] = "https://tuclima-mundial.onrender.com"

        if name == "AI Agent":
            opts = params.setdefault("options", {})
            opts["systemMessage"] = COMPACT_SYSTEM
            params["text"] = AGENT_TEXT

        if name == "Google Gemini Chat Model":
            params["modelName"] = "models/gemini-3.1-pro-preview-customtools"
            opts = params.setdefault("options", {})
            opts["maxOutputTokens"] = 2500

        if name in BI_DESC_PREFIX and "description" in params:
            desc = params["description"]
            if desc.startswith(WRONG_PREFIX):
                params["description"] = BI_DESC_PREFIX[name] + desc[len(WRONG_PREFIX) :]
            elif "AERONÁUTICOS" in desc[:80] and name != "Modulo_Aereo_BI":
                # fallback: force correct first sentence
                rest = desc.split("🚨 ADVERTENCIA CRÍTICA:", 1)
                tail = rest[1] if len(rest) == 2 else desc
                params["description"] = BI_DESC_PREFIX[name] + tail

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("patched", path.name)


def patch_devorador():
    path = ROOT / "devorador_reportes.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for node in data["nodes"]:
        if node.get("name") == "Validar Secreto":
            node["parameters"]["jsCode"] = SECRET_CODE
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("patched", path.name)


def patch_flash(files: list[str]):
    for fname in files:
        path = ROOT / fname
        data = json.loads(path.read_text(encoding="utf-8"))
        changed = 0
        for node in data["nodes"]:
            params = node.get("parameters") or {}
            model = params.get("modelName", "")
            if "gemini-3.1-pro" in model or model.endswith("pro-preview-customtools"):
                params["modelName"] = "models/gemini-2.0-flash"
                opts = params.setdefault("options", {})
                # keep existing maxOutputTokens if present
                changed += 1
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"patched {fname}: {changed} model node(s) -> flash")


if __name__ == "__main__":
    patch_chatbot()
    patch_devorador()
    patch_flash(
        [
            "aereo_BI.json",
            "agro_BI.json",
            "naval_BI.json",
            "energia_BI.json",
            "email_n8n.json",
        ]
    )
    print("OK")
