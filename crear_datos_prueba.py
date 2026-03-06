#!/usr/bin/env python3
"""
Script de Prueba para el Sistema Multisectorial
Crea datos de ejemplo para probar la detección automática de sectores
"""

import os
import json
import csv
from django.utils import timezone
from datetime import datetime

# Crear directorio de pruebas
if not os.path.exists('datos_prueba'):
    os.makedirs('datos_prueba')

print("🚀 Creando archivos de prueba para sistema multisectorial...")

# === DATOS NAVALES ===
naval_data = {
    "ubicacion": "Puerto de Buenos Aires",
    "altura_olas": 2.5,
    "corriente_marina": "15 km/h Norte",
    "salinidad": 35.2,
    "marea": "alta",
    "puerto": "BUENOS_AIRES",
    "navegacion": "comercial",
    "barco": "carguero",
    "oceano": "Atlántico",
    "temperatura_mar": 18.5,
    "profundidad": 15.0
}

with open('datos_prueba/naval_ejemplo.json', 'w', encoding='utf-8') as f:
    json.dump(naval_data, f, indent=2, ensure_ascii=False)

# === DATOS ENERGÍA ===
with open('datos_prueba/energia_ejemplo.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['voltaje', 'frecuencia', 'potencia', 'factor_potencia', 'energia', 'consumo', 'kwh'])
    writer.writerow([220, 50, 1500, 0.85, 'electrica', 450, 25.8])
    writer.writerow([380, 50, 3000, 0.92, 'industrial', 850, 48.2])

# === DATOS AÉREOS ===
aereo_txt = """
REPORTE METEOROLÓGICO AERONÁUTICO
===============================
Aeropuerto: Jorge Newbery Airfield (SABE)
Altitud: 10000 metros
Presión atmosférica: 1013.25 hPa
Visibilidad: 15 kilómetros
Turbulencia: moderada
Vientos: 15 nudos del SO
Temperatura: -45°C
Tráfico aéreo: alto
Vuelos programados: 45
Aviación comercial activa
Meteorología para navegación aérea
"""

with open('datos_prueba/aereo_ejemplo.txt', 'w', encoding='utf-8') as f:
    f.write(aereo_txt)

# === DATOS AGRÍCOLAS ===
agro_data = [
    {
        "humedad_suelo": 65,
        "ph_suelo": 6.8, 
        "nutrientes": "NPK 15-15-15",
        "tipo_cultivo": "maíz",
        "agricola": True,
        "campo": "Lote 15A",
        "cosecha": "2025-03-15",
        "ganado": 120,
        "rural": True,
        "hectareas": 50.5
    },
    {
        "humedad_suelo": 58,
        "ph_suelo": 7.2,
        "nutrientes": "Urea 46%",
        "tipo_cultivo": "soja",
        "agricola": True,
        "campo": "Lote 22B", 
        "cosecha": "2025-04-20",
        "ganado": 0,
        "rural": True,
        "hectareas": 75.3
    }
]

with open('datos_prueba/agro_ejemplo.json', 'w', encoding='utf-8') as f:
    json.dump(agro_data, f, indent=2, ensure_ascii=False)

# === CREAR ARCHIVO AMBIGUO PARA PROBAR IA ===
ambiguo_data = {
    "datos": [1.5, 2.3, 4.1],
    "ubicacion": "Zona Industrial",
    "fecha": datetime.now().isoformat(),
    "mediciones": "automáticas",
    "equipo": "sensor_generico_001"
}

with open('datos_prueba/ambiguo_ejemplo.json', 'w', encoding='utf-8') as f:
    json.dump(ambiguo_data, f, indent=2, ensure_ascii=False)

print("✅ Archivos de prueba creados en la carpeta 'datos_prueba/':")
print("📂 datos_prueba/")
print("   🚢 naval_ejemplo.json      -> Debería detectar NAVAL")
print("   ⚡ energia_ejemplo.csv     -> Debería detectar ENERGIA")
print("   ✈️  aereo_ejemplo.txt      -> Debería detectar AEREO")
print("   🌾 agro_ejemplo.json      -> Debería detectar AGRO")
print("   ❓ ambiguo_ejemplo.json   -> Prueba detección IA")
print("")
print("💡 Para probar:")
print("1. Iniciar servidor: python manage.py runserver")
print("2. Ir a: http://localhost:8000/carga-sectorial/")
print("3. Subir cualquiera de estos archivos")
print("4. Verificar que se detecte el sector correcto")
print("")
print("🔧 Nota: Configurar OPENAI_API_KEY en .env para análisis completo con IA")