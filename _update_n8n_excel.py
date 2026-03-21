import urllib.request, json

# v3 - strings exactos confirmados por _inspect_n8n.py

BASE = 'https://n8n-production-2651.up.railway.app'
API_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyZGM0OTg0Yi1jOTcxLTRjNDgtYTFiYy01ZDg5YzgzNWY2YTUiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiMzM3YTdmNTEtNzkwNS00NGMyLTk2NmUtMzRiMjRjNjY2ODA5IiwiaWF0IjoxNzczNzAxNTgxfQ.xE8qglbhADjieJBQ9SN6l9KGQ5tYKcTfbnOPfD6DxyM'
WF_ID = 'VWiz2ijo1LhgSrm6'

req = urllib.request.Request(f'{BASE}/api/v1/workflows/{WF_ID}', headers={'X-N8N-API-KEY': API_KEY})
with urllib.request.urlopen(req) as r:
    wf = json.loads(r.read())

for node in wf['nodes']:
    if node.get('type') == '@n8n/n8n-nodes-langchain.agent':
        sm = node['parameters']['options']['systemMessage']

        # 1. Insertar linea Excel despues de Modulo_Energia_BI (texto exacto confirmado)
        # Texto confirmado: 'Modulo_Energia_BI`\n\n   **\U0001f4cb PALABRAS CLAVE...'
        INSERT_AFTER = 'Modulo_Energia_BI`'
        INSERT_TEXT = '\n   - **\U0001f4ca Excel/Planilla:** Usuario pide Excel, planilla, spreadsheet, tabla descargable o exportar datos \u2192 USA SIEMPRE `Modulo_Generar_Excel`'
        KEYWORDS_OLD = '\n   - "trending", "comparativa visual", "gr\u00e1fico de tendencias", "modelo"'
        KEYWORDS_NEW = '\n   - "trending", "comparativa visual", "gr\u00e1fico de tendencias", "modelo"\n   - "Excel", "planilla", "spreadsheet", ".xlsx", "tabla para descargar", "exportar datos"'

        # Encontrar la primera ocurrencia de Modulo_Energia_BI` en PRIORIDAD 2
        idx = sm.find(INSERT_AFTER)
        if idx >= 0:
            sm = sm[:idx + len(INSERT_AFTER)] + INSERT_TEXT + sm[idx + len(INSERT_AFTER):]
            sm = sm.replace(KEYWORDS_OLD, KEYWORDS_NEW, 1)
            print('Paso 1 OK: Excel agregado a PRIORIDAD 2')
        else:
            print('Paso 1 FAIL: Modulo_Energia_BI` no encontrado')

        # 2. Agregar regla dura en sección NUNCA mezcles
        old2 = 'NUNCA mezcles ambas acciones. NUNCA ofrezcas un PDF si el usuario te pidi\u00f3 un gr\u00e1fico interactivo.'
        new2 = (
            'NUNCA mezcles ambas acciones. NUNCA ofrezcas un PDF si el usuario te pidi\u00f3 un gr\u00e1fico interactivo.\n\n'
            '\ud83d\udea8 REGLA EXCEL ABSOLUTA: Si el usuario pide un Excel, planilla o spreadsheet, DEBES usar `Modulo_Generar_Excel` SIN EXCEPCI\u00d3N. '
            'NUNCA devuelvas los datos en texto plano ni como JSON en el chat. '
            'La respuesta al usuario SIEMPRE debe ser el link de descarga generado por el m\u00f3dulo.'
        )
        if old2 in sm:
            sm = sm.replace(old2, new2, 1)
            print('Paso 2 OK: Regla Excel dura agregada')
        else:
            print('Paso 2 FAIL: frase no encontrada')

        node['parameters']['options']['systemMessage'] = sm
        break

# Guardar workflow - limpiar settings para pasar validacion
allowed_settings_keys = {'executionOrder', 'saveManualExecutions', 'callerPolicy', 'errorWorkflow', 'timezone', 'saveDataErrorExecution', 'saveDataSuccessExecution', 'saveExecutionProgress', 'executionTimeout'}
raw_settings = wf.get('settings', {}) or {}
clean_settings = {k: v for k, v in raw_settings.items() if k in allowed_settings_keys}

data = json.dumps({
    'name': wf['name'],
    'nodes': wf['nodes'],
    'connections': wf['connections'],
    'settings': clean_settings,
    'staticData': wf.get('staticData'),
}).encode('utf-8')

req2 = urllib.request.Request(
    f'{BASE}/api/v1/workflows/{WF_ID}',
    data=data,
    headers={'X-N8N-API-KEY': API_KEY, 'Content-Type': 'application/json'},
    method='PUT'
)
try:
    with urllib.request.urlopen(req2) as r:
        result = json.loads(r.read())
        print(f'Workflow guardado OK: id={result.get("id")} | activo={result.get("active")}')
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f'HTTP {e.code}: {body[:500]}')
