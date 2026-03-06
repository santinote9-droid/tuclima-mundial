#!/usr/bin/env python3
"""
🏗️ CREAR TABLA BIGQUERY PARA LOS WORKFLOWS
Crear la tabla datos_sectoriales con el esquema correcto
"""

from google.cloud import bigquery
import os

def crear_tabla_bigquery():
    """Crear la tabla datos_sectoriales en BigQuery"""
    
    # Configurar credenciales
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'C:\Users\fabig\proyecto_clima\credenciales\bigquery-credentials.json'
    
    try:
        client = bigquery.Client()
        
        # Verificar dataset existe
        dataset_id = "proyecto-bi-488218.datos_clima"
        
        print("🔍 VERIFICANDO DATASET Y CREANDO TABLA")
        print("=" * 60)
        
        try:
            dataset = client.get_dataset(dataset_id)
            print(f"✅ Dataset encontrado: {dataset.dataset_id}")
        except Exception as e:
            print(f"❌ Dataset no encontrado: {e}")
            print("📝 Creando dataset...")
            
            # Crear dataset si no existe
            dataset = bigquery.Dataset(dataset_id)
            dataset.location = "US"
            dataset = client.create_dataset(dataset, timeout=30)
            print(f"✅ Dataset creado: {dataset.dataset_id}")
        
        # Definir esquema de la tabla según sql_query.txt
        table_id = f"{dataset_id}.datos_sectoriales"
        
        schema = [
            bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("session_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("sector", "STRING", mode="REQUIRED"),
            
            # Campos NAVAL
            bigquery.SchemaField("puerto", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("condiciones_mar", "STRING", mode="NULLABLE"), 
            bigquery.SchemaField("viento_velocidad", "FLOAT", mode="NULLABLE"),
            bigquery.SchemaField("viento_direccion", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("temperatura_agua", "FLOAT", mode="NULLABLE"),
            bigquery.SchemaField("altura_olas", "FLOAT", mode="NULLABLE"),
            bigquery.SchemaField("visibilidad", "FLOAT", mode="NULLABLE"),
            bigquery.SchemaField("ai_analysis", "STRING", mode="NULLABLE"),
            
            # Campos ENERGIA
            bigquery.SchemaField("tipo_energia", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("ubicacion", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("radiacion_solar", "FLOAT", mode="NULLABLE"),
            bigquery.SchemaField("velocidad_viento", "FLOAT", mode="NULLABLE"),
            bigquery.SchemaField("temperatura_ambiente", "FLOAT", mode="NULLABLE"),
            bigquery.SchemaField("eficiencia_estimada", "FLOAT", mode="NULLABLE"),
            bigquery.SchemaField("produccion_kwh", "FLOAT", mode="NULLABLE"),
            bigquery.SchemaField("ai_efficiency_analysis", "STRING", mode="NULLABLE"),
            
            # Campos AGRO
            bigquery.SchemaField("cultivo", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("region", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("temperatura_suelo", "FLOAT", mode="NULLABLE"),
            bigquery.SchemaField("humedad_relativa", "FLOAT", mode="NULLABLE"),
            bigquery.SchemaField("precipitacion", "FLOAT", mode="NULLABLE"),
            bigquery.SchemaField("horas_sol", "FLOAT", mode="NULLABLE"),
            bigquery.SchemaField("fase_lunar", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("ai_recommendations", "STRING", mode="NULLABLE"),
            
            # Campos AEREO
            bigquery.SchemaField("aeropuerto_origen", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("aeropuerto_destino", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("altitud_vuelo", "FLOAT", mode="NULLABLE"),
            bigquery.SchemaField("temperatura_altitud", "FLOAT", mode="NULLABLE"),
            bigquery.SchemaField("corrientes_viento", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("visibilidad_km", "FLOAT", mode="NULLABLE"),
            bigquery.SchemaField("condiciones_atmosfericas", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("ai_flight_analysis", "STRING", mode="NULLABLE"),
            
            # Metadatos
            bigquery.SchemaField("metadata", "STRING", mode="NULLABLE"),
        ]
        
        print(f"🏗️ Creando tabla: {table_id}")
        print(f"📊 Campos definidos: {len(schema)}")
        
        # Verificar si tabla ya existe
        try:
            existing_table = client.get_table(table_id)
            print(f"⚠️  Tabla ya existe: {existing_table.table_id}")
            print(f"📏 Registros actuales: {existing_table.num_rows}")
            return existing_table
        except:
            print("📝 Tabla no existe, creando...")
        
        # Crear tabla
        table = bigquery.Table(table_id, schema=schema)
        table.description = "Datos sectoriales del sistema de análisis climático con IA"
        
        table = client.create_table(table)
        
        print(f"✅ TABLA CREADA EXITOSAMENTE: {table.table_id}")
        print(f"📍 Location: {table.location}")
        print(f"🆔 Table ID: {table.table_id}")
        print(f"📊 Schema: {len(table.schema)} campos")
        
        # Mostrar algunos campos clave
        print("\n🔧 CAMPOS PRINCIPALES:")
        key_fields = ['timestamp', 'session_id', 'sector', 'ai_analysis', 'metadata']
        for field in table.schema:
            if field.name in key_fields:
                print(f"  • {field.name}: {field.field_type} ({field.mode})")
        
        print("\n🚀 ¡TABLA LISTA PARA RECIBIR DATOS DE LOS WORKFLOWS!")
        
        return table
        
    except Exception as e:
        print(f"❌ ERROR AL CREAR TABLA: {str(e)}")
        return None

if __name__ == "__main__":
    crear_tabla_bigquery()