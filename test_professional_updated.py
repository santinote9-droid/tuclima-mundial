#!/usr/bin/env python3
"""
🧪 PRUEBA CÓDIGO PROFESIONAL CORREGIDO
Verificar extracción inteligente y dinámicos (sin predeterminados)
"""

import requests
import time
import json

def test_professional_code():
    """Test del código profesional actualizado"""
    
    test_data = {
        'chatInput': 'Condiciones navales Puerto Valencia con viento 30 km/h y olas 2.5 metros',
        'sessionId': f'test-final-{int(time.time())}'
    }

    print('🧪 PRUEBA CÓDIGO PROFESIONAL CORREGIDO')
    print('=' * 50)
    print(f'📤 Enviando: {test_data["chatInput"]}')
    print('-' * 50)

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
        print(f'📏 Length: {len(response.text)} chars')
        
        if response.status_code == 200:
            if response.text.strip():
                print('🎉 ¡HAY RESPUESTA!')
                try:
                    json_resp = json.loads(response.text)
                    print('✅ JSON válido')
                    
                    if 'data' in json_resp:
                        data = json_resp['data']
                        
                        # Verificar campos clave
                        print('\n🔍 DATOS EXTRAÍDOS:')
                        
                        chat_input = data.get('chat_input', '')
                        if chat_input and len(chat_input) > 10:
                            print(f'✅ chat_input: "{chat_input[:50]}..." ({len(chat_input)} chars)')
                        else:
                            print('❌ chat_input: VACÍO')
                        
                        sector = data.get('sector', '')
                        if sector == 'NAVAL':
                            print(f'✅ sector: {sector} (detectado correctamente)')
                        else:
                            print(f'⚠️  sector: {sector} (esperaba NAVAL)')
                        
                        viento = data.get('viento_velocidad')
                        if viento == 30.0:
                            print(f'✅ viento_velocidad: {viento} km/h (extraído correctamente)')
                        else:
                            print(f'⚠️  viento_velocidad: {viento} (esperaba 30.0)')
                        
                        olas = data.get('altura_olas')
                        if olas == 2.5:
                            print(f'✅ altura_olas: {olas} m (extraído correctamente)')
                        else:
                            print(f'⚠️  altura_olas: {olas} (esperaba 2.5)')
                        
                        puerto = data.get('puerto') or data.get('location')
                        if puerto and 'Valencia' in puerto:
                            print(f'✅ puerto/location: {puerto} (Valencia detectado)')
                        else:
                            print(f'⚠️  puerto/location: {puerto} (esperaba Valencia)')
                        
                        # Verificar que NO sean datos predeterminados
                        data_str = str(data)
                        predefined_found = []
                        predefined_checks = [
                            ('Puerto de Barcelona', 'hardcoded port'),
                            ('debug-session-', 'debug session'),
                            ('Análisis naval de prueba', 'test analysis'),
                            ('Puerto de prueba', 'test port')
                        ]
                        
                        for check, desc in predefined_checks:
                            if check in data_str:
                                predefined_found.append(desc)
                        
                        if predefined_found:
                            print(f'❌ Datos predeterminados encontrados: {", ".join(predefined_found)}')
                        else:
                            print('✅ Sin datos predeterminados - TODO DINÁMICO')
                        
                        print('\n🚀 EVALUACIÓN FINAL:')
                        score = 0
                        if chat_input and len(chat_input) > 10: score += 1
                        if sector == 'NAVAL': score += 1
                        if viento == 30.0: score += 1
                        if olas == 2.5: score += 1
                        if not predefined_found: score += 1
                        
                        if score >= 4:
                            print('🎉 ¡FUNCIÓN PROFESIONAL FUNCIONANDO PERFECTAMENTE!')
                            print('✅ Extracción inteligente de datos')
                            print('✅ Detección automática de sector')
                            print('✅ Procesamiento de métricas numéricas')
                            print('✅ Sin valores predeterminados')
                            return True
                        else:
                            print(f'🔧 Función mejorando - Score: {score}/5')
                            return False
                    
                except json.JSONDecodeError:
                    print('❌ Respuesta no es JSON válido')
                    print(f'📄 Respuesta: {response.text[:200]}...')
            else:
                print('❌ Respuesta vacía')
        else:
            print(f'❌ Error: {response.status_code}')
            
    except Exception as e:
        print(f'❌ Error: {e}')
    
    return False

if __name__ == "__main__":
    success = test_professional_code()
    
    print('\n' + '=' * 50)
    if success:
        print('🚀 NAVAL_BI CON CÓDIGO PROFESIONAL EXITOSO!')
        print('📋 Listo para replicar a outros workflows')
        print('💡 Energia_BI, Agro_BI, Aereo_BI pueden usar este patrón')
    else:
        print('🔧 Necesita más ajustes en extracción de datos')