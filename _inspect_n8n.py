import urllib.request, json

BASE = 'https://n8n-production-2651.up.railway.app'
API_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyZGM0OTg0Yi1jOTcxLTRjNDgtYTFiYy01ZDg5YzgzNWY2YTUiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiMzM3YTdmNTEtNzkwNS00NGMyLTk2NmUtMzRiMjRjNjY2ODA5IiwiaWF0IjoxNzczNzAxNTgxfQ.xE8qglbhADjieJBQ9SN6l9KGQ5tYKcTfbnOPfD6DxyM'
WF_ID = 'VWiz2ijo1LhgSrm6'

req = urllib.request.Request(f'{BASE}/api/v1/workflows/{WF_ID}', headers={'X-N8N-API-KEY': API_KEY})
with urllib.request.urlopen(req) as r:
    wf = json.loads(r.read())

for node in wf['nodes']:
    if node.get('type') == '@n8n/n8n-nodes-langchain.agent':
        sm = node['parameters']['options']['systemMessage']

        # Buscar texto exacto alrededor de Modulo_Energia_BI en PRIORIDAD 2
        idx = sm.find('Modulo_Energia_BI`')
        print('=== Contexto exacto (80 chars antes y 150 despues) ===')
        print(repr(sm[idx-80:idx+150]))
        print()
        
        # Buscar texto alrededor de "NUNCA mezcles"
        idx2 = sm.find('NUNCA mezcles ambas acciones')
        print('=== Contexto NUNCA mezcles ===')
        print(repr(sm[idx2:idx2+200]))
        break
