#!/usr/bin/env python3
"""
🌍 TEST CON UBICACIÓN GEOGRÁFICA ESPECÍFICA
La IA necesita ubicación específica para generar datos reales
"""

import requests
import time
import json

def test_specific_location():
    """Test con ubicación geográfica específica"""
    
    # Test con diferentes ubicaciones específicas
    test_cases = [
        {
            'name': 'Puerto Madrid Específico',
            'chatInput': 'Analizar condiciones meteorológicas marítimas en el Puerto de Madrid, España con datos actuales de viento, olas y temperatura',
            'expected_location': 'Madrid'
        },
        {
            'name': 'Costa Barcelona Específica', 
            'chatInput': 'Condiciones navales en Puerto de Barcelona, Catalunya, España - necesito datos de viento, altura de olas y visibilidad actual',
            'expected_location': 'Barcelona'
        },
        {
            'name': 'Puerto Valencia Específico',
            'chatInput': 'Análisis meteorológico naval Puerto de Valencia, Comunidad Valenciana, España - viento, olas, temperatura del agua',
            'expected_location': 'Valencia'
        }
    ]

    print('🌍 TEST CON UBICACIÓN GEOGRÁFICA ESPECÍFICA')
    print('=' * 60)
    print('🎯 Objetivo: IA debe generar datos reales con ubicación específica')
    print('-' * 60)

    for i, test_case in enumerate(test_cases, 1):
        print(f'\n📍 TEST {i}: {test_case["name"]}')
        print('-' * 40)
        
        test_data = {
            'chatInput': test_case['chatInput'],
            'sessionId': f'geo-test-{i}-{int(time.time())}'
        }
        
        print(f'📤 Query: {test_case["chatInput"][:60]}...')
        
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
            
            if response.status_code == 200 and response.text.strip():
                try:
                    json_resp = json.loads(response.text)
                    
                    if 'data' in json_resp:
                        data = json_resp['data']
                        
                        # Verificar extracción de ubicación
                        chat_input = data.get('chat_input', '')
                        ai_response = data.get('ai_response', '')
                        location = data.get('location') or data.get('puerto')
                        
                        print(f'💬 Input recibido: {len(chat_input)} chars')
                        print(f'🤖 AI response: {len(ai_response)} chars')
                        
                        if location and test_case['expected_location'].lower() in location.lower():
                            print(f'✅ Ubicación extraída: {location}')
                        else:
                            print(f'⚠️  Ubicación: {location}')
                        
                        # Verificar datos meteorológicos específicos
                        wind = data.get('viento_velocidad')
                        waves = data.get('altura_olas')  
                        temp = data.get('temperatura')
                        
                        real_data_count = 0
                        if wind and isinstance(wind, (int, float)) and wind > 0:
                            print(f'✅ Viento: {wind} km/h (dato específico)')
                            real_data_count += 1
                        else:
                            print(f'⚠️  Viento: {wind}')
                            
                        if waves and isinstance(waves, (int, float)) and waves > 0:
                            print(f'✅ Olas: {waves} m (dato específico)')
                            real_data_count += 1
                        else:
                            print(f'⚠️  Olas: {waves}')
                            
                        if temp and isinstance(temp, (int, float)) and temp > 0:
                            print(f'✅ Temperatura: {temp}°C (dato específico)')
                            real_data_count += 1
                        else:
                            print(f'⚠️  Temperatura: {temp}')
                        
                        # Evaluación
                        if real_data_count >= 2 and chat_input:
                            print('🎉 ¡IA GENERANDO DATOS REALES CON UBICACIÓN!')
                            return True
                        elif chat_input:
                            print('🔄 IA responde pero necesita ubicación más específica')
                        else:
                            print('❌ Datos aún vacíos')
                    
                except json.JSONDecodeError:
                    print('❌ Respuesta no JSON válida')
                    
            else:
                print(f'❌ Error o respuesta vacía: {response.status_code}')
                
        except Exception as e:
            print(f'❌ Error: {e}')
    
    return False

if __name__ == "__main__":
    success = test_specific_location()
    
    print('\n' + '=' * 60)
    if success:
        print('🚀 ¡IA FUNCIONA CON UBICACIONES ESPECÍFICAS!')
        print('✅ Datos reales generados basados en ubicación')
        print('✅ Function Node extrae información correctamente')
        print('📋 Patrón confirmado para replicar a otros workflows')
    else:
        print('🔧 Ajustar queries para incluir ubicaciones más específicas')
        print('💡 La IA necesita contexto geográfico detallado')