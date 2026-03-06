#!/usr/bin/env python
"""
Script de verificación y backup de usuarios
Uso: python verificar_usuarios.py
"""

import os
import sys
import django
from datetime import datetime, timedelta
import json

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nucleo.settings')
django.setup()

from django.contrib.auth.models import User
from mundo.models import PerfilUsuario, ReporteUsuario, DatoSectorial

def verificar_usuarios():
    """Verificar el estado actual de usuarios"""
    print("=" * 60)
    print(f"🔍 VERIFICACIÓN DE USUARIOS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    try:
        # Contar usuarios
        total_usuarios = User.objects.count()
        usuarios_admin = User.objects.filter(is_staff=True).count()
        usuarios_activos = User.objects.filter(is_active=True).count()
        
        print(f"📊 ESTADÍSTICAS:")
        print(f"   - Total usuarios: {total_usuarios}")
        print(f"   - Administradores: {usuarios_admin}")
        print(f"   - Usuarios activos: {usuarios_activos}")
        print()
        
        # Mostrar usuarios
        print("👥 LISTA DE USUARIOS:")
        if total_usuarios == 0:
            print("   ⚠️  NO HAY USUARIOS REGISTRADOS")
        else:
            for user in User.objects.all().order_by('-date_joined'):
                admin_text = "👑 Admin" if user.is_staff else "👤 Usuario"
                active_text = "✅Activo" if user.is_active else "❌Inactivo"
                print(f"   - {user.username} ({admin_text}, {active_text}) - Registro: {user.date_joined.strftime('%Y-%m-%d %H:%M')}")
        
        print()
        
        # Verificar perfiles
        perfiles = PerfilUsuario.objects.count()
        reportes = ReporteUsuario.objects.count()
        datos_sectoriales = DatoSectorial.objects.count()
        
        print("📋 DATOS ADICIONALES:")
        print(f"   - Perfiles de usuario: {perfiles}")
        print(f"   - Reportes de usuarios: {reportes}")
        print(f"   - Datos sectoriales: {datos_sectoriales}")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR al verificar usuarios: {e}")
        return False

def crear_backup_usuarios():
    """Crear backup de usuarios en formato JSON"""
    try:
        backup_data = {
            'timestamp': datetime.now().isoformat(),
            'usuarios': []
        }
        
        for user in User.objects.all():
            user_data = {
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_active': user.is_active,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser,
                'date_joined': user.date_joined.isoformat(),
                'last_login': user.last_login.isoformat() if user.last_login else None
            }
            backup_data['usuarios'].append(user_data)
        
        # Crear directorio de backup si no existe
        backup_dir = 'backups_usuarios'
        os.makedirs(backup_dir, exist_ok=True)
        
        # Nombre del archivo con timestamp
        filename = f"{backup_dir}/backup_usuarios_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Backup creado: {filename}")
        return filename
        
    except Exception as e:
        print(f"❌ ERROR al crear backup: {e}")
        return None

def verificar_conexion_db():
    """Verificar que la conexión a la base de datos funcione"""
    try:
        from django.db import connection
        from django.core.management import sql
        
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        
        print("✅ Conexión a base de datos: OK")
        print(f"   - Motor: {connection.settings_dict['ENGINE']}")
        print(f"   - Base de datos: {connection.settings_dict['NAME']}")
        print(f"   - Host: {connection.settings_dict.get('HOST', 'localhost')}")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR de conexión a base de datos: {e}")
        return False

def main():
    """Función principal"""
    print("🚀 Iniciando verificación del sistema...")
    print()
    
    # Verificar conexión primera
    if not verificar_conexion_db():
        print("\n❌ No se puede continuar sin conexión a base de datos")
        sys.exit(1)
    
    print()
    
    # Verificar usuarios
    if verificar_usuarios():
        print("\n✅ Verificación completada")
    else:
        print("\n❌ Errores durante la verificación")
    
    print()
    
    # Crear backup
    print("💾 Creando backup...")
    backup_file = crear_backup_usuarios()
    
    if backup_file:
        print("✅ Backup completado correctamente")
    else:
        print("❌ Error al crear backup")
    
    print()
    print("=" * 60)
    print("✨ Proceso terminado")
    print("=" * 60)

if __name__ == '__main__':
    main()