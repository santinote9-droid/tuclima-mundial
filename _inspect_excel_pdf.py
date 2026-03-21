import urllib.request, json

BASE = "https://n8n-production-2651.up.railway.app"
KEY  = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyZGM0OTg0Yi1jOTcxLTRjNDgtYTFiYy01ZDg5YzgzNWY2YTUiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiMzM3YTdmNTEtNzkwNS00NGMyLTk2NmUtMzRiMjRjNjY2ODA5IiwiaWF0IjoxNzczNzAxNTgxfQ.xE8qglbhADjieJBQ9SN6l9KGQ5tYKcTfbnOPfD6DxyM"

# Workflows conocidos
EXCEL_ID  = "rgrG5plnyuZkNg80"  # Modulo_Generar_Excel
REPORT_ID = "AOjex81dUN9cod1j"  # Modulo_Generar_Reporte (PDF)

def api_get(path):
    req = urllib.request.Request(f"{BASE}{path}", headers={"X-N8N-API-KEY": KEY})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

for wf_id, label in [(EXCEL_ID, "EXCEL"), (REPORT_ID, "PDF")]:
    wf = api_get(f"/api/v1/workflows/{wf_id}")
    print(f"\n{'='*60}")
    print(f"=== {label}: {wf['name']} ===")
    print(f"{'='*60}")
    for i, node in enumerate(wf["nodes"]):
        ntype = node.get("type","")
        nname = node.get("name","")
        params = node.get("parameters",{})
        print(f"\n[{i}] {ntype} | {nname}")
        
        # Mostrar JS de nodos Code
        if ntype == "n8n-nodes-base.code":
            js = params.get("jsCode","")
            print(f"  JS ({len(js)} chars):")
            print(f"  {js[:600]}")
        
        # Mostrar parámetros clave de Google Sheets
        if "sheet" in ntype.lower() or "spreadsheet" in ntype.lower():
            print(f"  params: {json.dumps(params)[:400]}")
        
        # Mostrar parámetros de HTTP Request
        if "httpRequest" in ntype or "http" in ntype.lower():
            print(f"  url: {params.get('url','')}")
            body = params.get('body','') or params.get('jsonBody','')
            print(f"  body: {str(body)[:300]}")
        
        # Mostrar Set/EditFields
        if ntype in ("n8n-nodes-base.set", "n8n-nodes-base.editFields"):
            assignments = params.get("assignments",{}).get("assignments",[])
            for a in assignments:
                print(f"  field: {a.get('name')} = {str(a.get('value',''))[:80]}")
