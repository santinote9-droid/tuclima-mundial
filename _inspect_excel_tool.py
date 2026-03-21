import urllib.request, json

BASE = "https://n8n-production-2651.up.railway.app"
KEY  = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyZGM0OTg0Yi1jOTcxLTRjNDgtYTFiYy01ZDg5YzgzNWY2YTUiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiMzM3YTdmNTEtNzkwNS00NGMyLTk2NmUtMzRiMjRjNjY2ODA5IiwiaWF0IjoxNzczNzAxNTgxfQ.xE8qglbhADjieJBQ9SN6l9KGQ5tYKcTfbnOPfD6DxyM"

def api_get(path):
    req = urllib.request.Request(f"{BASE}{path}", headers={"X-N8N-API-KEY": KEY})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

wf = api_get("/api/v1/workflows/VWiz2ijo1LhgSrm6")  # Chatbot TuClima
for node in wf["nodes"]:
    if node.get("name") == "Modulo_Generar_Excel":
        print("=== Modulo_Generar_Excel tool en Chatbot ===")
        print("description:", node.get("parameters",{}).get("description",""))
        print()
        print("workflowValues:", json.dumps(node.get("parameters",{}).get("workflowValues",{}), indent=2)[:1000])
