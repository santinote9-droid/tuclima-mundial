"""Reconnect Supabase memory read (Get many rows) into Code 1."""
import json
from pathlib import Path

path = Path(__file__).resolve().parent / "chatbot_tuclima.json"
data = json.loads(path.read_text(encoding="utf-8"))

session_expr = (
    "={{ $json.body?.sessionId || $json.body?.session_id || "
    "$('Webhook').item.json.body?.sessionId || "
    "$('Webhook').item.json.body?.userId || 'default' }}"
)

for n in data["nodes"]:
    if n.get("name") == "Get many rows":
        n["disabled"] = False
        conds = n["parameters"].setdefault("filters", {}).setdefault("conditions", [])
        if conds:
            conds[0]["keyValue"] = session_expr
        print("enabled Get many rows")
    if n.get("name") == "Execute a SQL query":
        # Legacy Postgres SELECT — avoid double-read; writes still use Supabase
        n["disabled"] = True
        print("disabled Execute a SQL query (legacy postgres read)")

data["connections"]["Validar Secreto"] = {
    "main": [[
        {"node": "Switch", "type": "main", "index": 0},
        {"node": "Get many rows", "type": "main", "index": 0},
    ]]
}
data["connections"]["Get many rows"] = {
    "main": [[{"node": "Code 1", "type": "main", "index": 0}]]
}
data["connections"]["Execute a SQL query"] = {"main": [[]]}

path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

data2 = json.loads(path.read_text(encoding="utf-8"))
for n in data2["nodes"]:
    if n.get("name") in ("Get many rows", "Execute a SQL query"):
        print(n["name"], "disabled=", n.get("disabled", False))
print("Validar Secreto ->", data2["connections"]["Validar Secreto"])
print("Get many rows ->", data2["connections"]["Get many rows"])
