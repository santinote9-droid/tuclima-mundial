#!/usr/bin/env python3
"""
🧪 TEST SIMPLE PROMPT ACTUALIZADO
Verificar si el AI Agent ahora genera datos en lugar de pedir ubicación
"""

import requests
import time
import json

print('🧪 TEST SIMPLE - PROMPT AI AGENT ACTUALIZADO')
print('=' * 50)
print('🎯 Verificar que AI ya no pida ubicación geográfica')
print('-' * 50)

test_data = {
    'chatInput': 'Condiciones navales Puerto de Barcelona',
    'sessionId': f'prompt-test-{int(time.time())}'
}

print(f'📤 Enviando: {test_data["chatInput"]}')

try:
    start_time = time.time()
    
    response = requests.post(
        'https://n8n-production-2651.up.railway.app/webhook/Naval_BI',
        data=test_data,
        timeout=15
    )
    
    duration = time.time() - start_time
    
    print(f'⏱️  Tiempo: {duration:.2f}s')
    print(f'📊 Status: {response.status_code}')
    print(f'📏 Length: {len(response.text)}')
    
    if response.status_code == 200:
        if response.text.strip():
            print('✅ HAY RESPUESTA')
            print(f'📄 Respuesta (primeros 200 chars):')
            print(response.text[:200])
            print('...')
            
            # Verificar si NO pide más ubicación
            response_lower = response.text.lower()
            location_requests = [
                'necesito que proporciones',
                'proporciona la ubicación',
                'especifica la ubicación',
                'indica la ubicación',
                'ubicación geográfica de interés'
            ]
            
            asks_location = any(phrase in response_lower for phrase in location_requests)
            
            if asks_location:
                print('❌ IA AÚN PIDE UBICACIÓN GEOGRÁFICA')
                print('🔧 El prompt necesita más ajustes')
            else:
                print('✅ IA YA NO PIDE UBICACIÓN')
                print('🎉 Prompt actualizado funcionando')
                
                # Verificar si contiene datos específicos
                has_numbers = any(char.isdigit() for char in response.text)
                if has_numbers:
                    print('✅ Respuesta contiene números (posibles datos específicos)')
                else:
                    print('⚠️  Respuesta sin números específicos')
        else:
            print('❌ Respuesta vacía')
    else:
        print(f'❌ Error: {response.status_code}')
        
except Exception as e:
    print(f'❌ Error: {e}')

print('\n' + '-' * 50)
print('💡 Si aún pide ubicación → Ajustar prompt AI Agent')
print('💡 Si no pide ubicación → Revisar extracción Function Node')