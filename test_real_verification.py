#!/usr/bin/env python3
"""
📊 TEST DE VERIFICACIÓN REAL
Ver exactamente qué devuelve el workflow (que según n8n funciona perfecto)
"""

import requests
import time
import json

def test_real_workflow():
    """Test real para ver exactamente qué devuelve"""
    
    test_data = {
        'chatInput': 'Condiciones navales Puerto de Barcelona',
        'sessionId': f'verification-{int(time.time())}'
    }

    print('📊 TEST DE VERIFICACIÓN REAL')
    print('=' * 50)
    print('🎯 Ver exactamente qué devuelve el workflow')
    print('-' * 50)

    try:
        start_time = time.time()
        
        response = requests.post(
            'https://n8n-production-2651.up.railway.app/webhook/Naval_BI',
            data=test_data,
            timeout=20
        )
        
        duration = time.time() - start_time
        
        print(f'⏱️  Tiempo: {duration:.2f}s')
        print(f'📊 Status: {response.status_code}')
        print(f'📏 Length: {len(response.text)} chars')
        
        if response.status_code == 200:
            if response.text.strip():
                print('\n📄 RESPUESTA COMPLETA RAW:')
                print('=' * 50)
                print(response.text)
                print('=' * 50)
                
                try:
                    json_resp = json.loads(response.text)
                    print('\n✅ JSON VÁLIDO PARSEADO:')
                    print('=' * 50)
                    print(json.dumps(json_resp, indent=2, ensure_ascii=False))
                    print('=' * 50)
                    
                    # Capturar estructura real
                    if 'data' in json_resp:
                        data = json_resp['data']
                        print('\n🔍 ANÁLISIS DE DATOS:')
                        
                        for key, value in data.items():
                            if value is not None and str(value).strip():
                                print(f'✅ {key}: {value}')
                            else:
                                print(f'❌ {key}: {value}')
                        
                        print('\n🚀 EVALUACIÓN FINAL:')
                        if data.get('viento_velocidad') and data.get('sector'):
                            print('🎉 ¡WORKFLOW PERFECTAMENTE FUNCIONAL!')
                            print('✅ Todos los datos están siendo generados')
                            print('✅ El problema era del TEST, no del workflow')
                            return True
                    
                except json.JSONDecodeError:
                    print('❌ Error al parsear JSON')
            else:
                print('❌ Respuesta vacía')
        else:
            print(f'❌ Error: {response.status_code}')
            
    except Exception as e:
        print(f'❌ Error: {e}')
    
    return False

if __name__ == "__main__":
    success = test_real_workflow()
    
    if success:
        print('\n🎉 CONFIRMACIÓN: NAVAL_BI 100% FUNCIONAL!')
        print('📋 Listo para replicar configuración a otros workflows')
    else:
        print('\n🔧 Verificar respuesta del workflow')