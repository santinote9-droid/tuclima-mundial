"""Add Modulo_Devorador_Reportes toolWorkflow to chatbot_tuclima.json."""
import json
from pathlib import Path

path = Path(__file__).resolve().parent / "chatbot_tuclima.json"
data = json.loads(path.read_text(encoding="utf-8"))

if any(n.get("name") == "Modulo_Devorador_Reportes" for n in data["nodes"]):
    print("tool already exists")
else:
    tool = {
        "parameters": {
            "description": (
                "Analiza un DOCUMENTO TECNICO ya extraido como TEXTO (PDF/informe). "
                "NO envies archivos binarios: envia el texto plano completo. "
                "Usa cuando el usuario subio un PDF/informe y pide resumen ejecutivo, "
                "alertas criticas o proximas acciones. "
                "Parametros: texto_documento (string), sector (AGRO|NAVAL|AEREO|ENERGIA|GENERAL), empresa (string)."
            ),
            "workflowId": {
                "__rl": True,
                "value": "Devorador de Reportes — Procesamiento Documental",
                "mode": "name",
                "cachedResultName": "Devorador de Reportes — Procesamiento Documental",
            },
            "workflowInputs": {
                "mappingMode": "defineBelow",
                "value": {
                    "texto_documento": (
                        "={{ $fromAI('texto_documento', "
                        "'Texto completo extraido del PDF o informe.', 'string') }}"
                    ),
                    "sector": (
                        "={{ $fromAI('sector', "
                        "'AGRO, NAVAL, AEREO, ENERGIA o GENERAL', 'string') }}"
                    ),
                    "empresa": (
                        "={{ $fromAI('empresa', "
                        "'Nombre de empresa o Cliente; si no, Empresa', 'string') }}"
                    ),
                    "session_id": (
                        "={{ $('Webhook').item.json.body?.sessionId "
                        "?? $('Webhook').item.json.body?.userId ?? 'chat' }}"
                    ),
                },
                "matchingColumns": [
                    "texto_documento",
                    "sector",
                    "empresa",
                    "session_id",
                ],
                "schema": [
                    {
                        "id": "texto_documento",
                        "displayName": "texto_documento",
                        "required": True,
                        "defaultMatch": False,
                        "display": True,
                        "canBeUsedToMatch": True,
                        "type": "string",
                        "removed": False,
                    },
                    {
                        "id": "sector",
                        "displayName": "sector",
                        "required": False,
                        "defaultMatch": False,
                        "display": True,
                        "canBeUsedToMatch": True,
                        "type": "string",
                        "removed": False,
                    },
                    {
                        "id": "empresa",
                        "displayName": "empresa",
                        "required": False,
                        "defaultMatch": False,
                        "display": True,
                        "canBeUsedToMatch": True,
                        "type": "string",
                        "removed": False,
                    },
                    {
                        "id": "session_id",
                        "displayName": "session_id",
                        "required": False,
                        "defaultMatch": False,
                        "display": True,
                        "canBeUsedToMatch": True,
                        "type": "string",
                        "removed": False,
                    },
                ],
                "attemptToConvertTypes": False,
                "convertFieldsToString": False,
            },
        },
        "type": "@n8n/n8n-nodes-langchain.toolWorkflow",
        "typeVersion": 2.2,
        "position": [5760, 640],
        "id": "drc-tool-devorador-001",
        "name": "Modulo_Devorador_Reportes",
    }
    data["nodes"].append(tool)
    data["connections"]["Modulo_Devorador_Reportes"] = {
        "ai_tool": [[{"node": "AI Agent", "type": "ai_tool", "index": 0}]]
    }
    print("added tool node")

for n in data["nodes"]:
    if n.get("name") != "AI Agent":
        continue
    sm = n["parameters"]["options"].get("systemMessage", "")
    if "Modulo_Devorador_Reportes" not in sm:
        sm += (
            "\n\n## Devorador de reportes\n"
            "Si el usuario adjunta un PDF/informe y pide analisis ejecutivo, usa "
            "Modulo_Devorador_Reportes con texto_documento (texto ya extraido), "
            "sector y empresa. No reenvies el binario."
        )
        n["parameters"]["options"]["systemMessage"] = sm
        print("system prompt updated, len", len(sm))

path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print("OK")
