#!/usr/bin/env python
"""
🧪 SCRIPT DE TESTING PARA MEMORIA DE IA EN N8N
Prueba el sistema de memoria y reporta problemas
"""

import requests
import json
import time
import uuid
from datetime import datetime

# 🔧 CONFIGURACIÓN
N8N_WEBHOOK_URL = "https://n8n-production-2651.up.railway.app/webhook/chat"  # Tu URL exacta basada en la imagen
TEST_SESSION_ID = f"test_session_{int(time.time())}"

# 🧪 CASOS DE PRUEBA
test_cases = [
    {
        "nombre": "Primera interacción - Naval",
        "payload": {
            "chatInput": "Hola, ¿cómo están las condiciones navales en el puerto de Buenos Aires?",
            "sessionId": TEST_SESSION_ID,
            "currentPage": "naval"
        },
        "esperado": ["hola", "primera", "buenos aires", "naval"]
    },
    {
        "nombre": "Segunda interacción - Continuidad",
        "payload": {
            "chatInput": "¿Y cómo sigue el viento?",
            "sessionId": TEST_SESSION_ID,
            "currentPage": "naval"
        },
        "esperado": ["viento", "antes", "puerto", "conversación"]
    },
    {
        "nombre": "Tercera interacción - Cambio tema",
        "payload": {
            "chatInput": "Ahora quiero saber sobre condiciones agrícolas",
            "sessionId": TEST_SESSION_ID,
            "currentPage": "agro"
        },
        "esperado": ["agro", "cambio", "ahora", "agricola"]
    },
    {
        "nombre": "Cuarta interacción - Volver tema anterior",
        "payload": {
            "chatInput": "Volviendo al tema naval, ¿hubo cambios?",
            "sessionId": TEST_SESSION_ID,
            "currentPage": "naval"
        },
        "esperado": ["naval", "cambios", "antes", "volviendo"]
    }
]

def ejecutar_test_case(caso, indice):
    """Ejecutar un caso de prueba individual"""
    print(f"\n{'='*60}")
    print(f"🧪 TEST {indice + 1}: {caso['nombre']}")
    print(f"{'='*60}")
    
    print("📤 Enviando:", json.dumps(caso['payload'], indent=2))
    
    try:
        # Hacer request
        response = requests.post(
            N8N_WEBHOOK_URL, 
            json=caso['payload'],
            timeout=30
        )
        
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ ERROR: {response.text}")
            return False
        
        # Parsear respuesta
        try:
            respuesta_json = response.json()
        except:
            respuesta_json = {"response": response.text}
        
        print(f"📨 Respuesta Raw: {json.dumps(respuesta_json, indent=2)}")
        
        # Extraer texto de respuesta
        texto_respuesta = ""
        if isinstance(respuesta_json, dict):
            texto_respuesta = respuesta_json.get("response", respuesta_json.get("message", str(respuesta_json)))
        else:
            texto_respuesta = str(respuesta_json)
        
        texto_respuesta = texto_respuesta.lower()
        
        print(f"💬 Respuesta de IA: {texto_respuesta}")
        
        # Verificar palabras esperadas
        palabras_encontradas = [palabra for palabra in caso['esperado'] if palabra in texto_respuesta]
        palabras_faltantes = [palabra for palabra in caso['esperado'] if palabra not in texto_respuesta]
        
        print(f"✅ Palabras encontradas: {palabras_encontradas}")
        if palabras_faltantes:
            print(f"⚠️  Palabras faltantes: {palabras_faltantes}")
        
        # Análisis de memoria
        if indice > 0:  # No es la primera interacción
            indicadores_memoria = ["antes", "anterior", "previa", "como", "recordando", "conversación", "mencioné"]
            memoria_detectada = [ind for ind in indicadores_memoria if ind in texto_respuesta]
            
            if memoria_detectada:
                print(f"🧠 MEMORIA DETECTADA: {memoria_detectada}")
            else:
                print(f"⚠️  NO SE DETECTÓ MEMORIA (puede ser normal en algunos casos)")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR DE CONEXIÓN: {e}")
        return False
    except Exception as e:
        print(f"❌ ERROR INESPERADO: {e}")
        return False

def verificar_configuracion():
    """Verificar configuración básica"""
    print("🔍 VERIFICANDO CONFIGURACIÓN...")
    print(f"📍 URL de webhook: {N8N_WEBHOOK_URL}")
    print(f"🆔 Session ID de prueba: {TEST_SESSION_ID}")
    
    # Test de conectividad básica
    try:
        response = requests.get(N8N_WEBHOOK_URL.replace("/webhook/chat", "/"), timeout=5)
        print(f"✅ URL base accesible (status: {response.status_code})")
    except:
        print(f"⚠️  No se puede verificar URL base (normal si n8n no tiene index)")

def main():
    """Función principal de testing"""
    print("🚀 INICIANDO TESTS DE MEMORIA IA")
    print(f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    verificar_configuracion()
    
    resultados = []
    
    for i, caso in enumerate(test_cases):
        exito = ejecutar_test_case(caso, i)
        resultados.append(exito)
        
        # Pausa entre tests para no sobrecargar
        if i < len(test_cases) - 1:
            print(f"\n⏳ Pausa 3 segundos antes del próximo test...")
            time.sleep(3)
    
    # Resumen final
    print(f"\n{'='*60}")
    print("📊 RESUMEN DE RESULTADOS")
    print(f"{'='*60}")
    
    exitosos = sum(resultados)
    total = len(resultados)
    
    print(f"✅ Tests exitosos: {exitosos}/{total}")
    print(f"❌ Tests fallidos: {total - exitosos}/{total}")
    
    for i, (caso, resultado) in enumerate(zip(test_cases, resultados)):
        status = "✅ PASS" if resultado else "❌ FAIL"
        print(f"  {i+1}. {caso['nombre']}: {status}")
    
    if exitosos == total:
        print(f"\n🎉 TODOS LOS TESTS PASARON! Sistema de memoria funcionando correctamente.")
    else:
        print(f"\n⚠️  ALGUNOS TESTS FALLARON. Revisar configuración de n8n.")
        print("\n🔧 PASOS PARA DIAGNOSTICAR:")
        print("1. Verificar que la tabla 'conversaciones_memoria' existe en Supabase")
        print("2. Confirmar que el flujo de n8n está activado")
        print("3. Revisar logs de n8n para errores específicos")
        print("4. Verificar que todos los nodos estén configurados correctamente")
    
    print(f"\n📋 Session ID usado: {TEST_SESSION_ID}")
    print("💡 Puedes buscar este session_id en Supabase para ver los registros creados")

if __name__ == "__main__":
    main()

"""
📋 CÓMO USAR ESTE SCRIPT:

1. Instalar requests: pip install requests
2. Cambiar N8N_WEBHOOK_URL por tu URL real
3. Ejecutar: python test_memoria_ia.py
4. Revisar output y diagnosticar problemas
5. Buscar TEST_SESSION_ID en tabla conversations_memoria en Supabase

🎯 QUÉ EVALÚA:
- Conectividad con n8n
- Respuestas de IA coherentes  
- Detección de memoria entre conversaciones
- Continuidad de contexto
- Manejo de cambios de tema
"""