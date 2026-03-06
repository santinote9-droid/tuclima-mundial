#!/usr/bin/env python
"""
Script de monitoreo automático de usuarios
Se puede ejecutar como tarea programada para vigilancia continua
"""

import os
import sys
import django
from datetime import datetime, timedelta
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nucleo.settings')
django.setup()

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.mail import send_mail
from django.conf import settings

class MonitorUsuarios:
    def __init__(self):
        self.log_file = "logs_usuarios.txt"
        self.alertas = []
        
    def log(self, mensaje):
        """Escribir log con timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {mensaje}"
        
        print(log_entry)
        
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")
    
    def verificar_usuarios_criticos(self):
        """Verificar que usuarios críticos estén presentes"""
        usuarios_criticos = ['Sangioff']  # Añadir usuarios que NUNCA deben faltar
        
        for username in usuarios_criticos:
            try:
                user = User.objects.get(username=username)
                if not user.is_active:
                    self.alertas.append(f"❌ Usuario crítico INACTIVO: {username}")
                    self.log(f"ALERTA: Usuario crítico inactivo: {username}")
                else:
                    self.log(f"✅ Usuario crítico OK: {username}")
            except User.DoesNotExist:
                self.alertas.append(f"🚨 Usuario crítico NO EXISTE: {username}")
                self.log(f"ALERTA CRÍTICA: Usuario no existe: {username}")
    
    def verificar_total_usuarios(self):
        """Verificar si el número de usuarios es sospechosamente bajo"""
        total = User.objects.count()
        admin_count = User.objects.filter(is_staff=True).count()
        
        self.log(f"Total usuarios: {total}, Administradores: {admin_count}")
        
        if total == 0:
            self.alertas.append("🚨 NO HAY USUARIOS EN LA BASE DE DATOS")
            self.log("ALERTA CRÍTICA: Base de datos vacía")
        elif admin_count == 0:
            self.alertas.append("⚠️  NO HAY ADMINISTRADORES")
            self.log("ALERTA: Sin administradores") 
        elif total < 1:  # Ajustar según tus expectativas
            self.alertas.append(f"⚠️  Pocos usuarios: {total}")
            self.log(f"ALERTA: Solo {total} usuarios")
    
    def verificar_conexion_db(self):
        """Verificar que la conexión a base de datos funcione"""
        try:
            from django.db import connection
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            self.log("✅ Conexión a base de datos OK")
            return True
        except Exception as e:
            self.alertas.append(f"🚨 Error de conexión DB: {str(e)}")
            self.log(f"ALERTA CRÍTICA: Error DB: {e}")
            return False
    
    def crear_backup_automatico(self):
        """Crear backup usando el comando Django"""
        try:
            call_command('backup_usuarios', verbosity=0)
            self.log("✅ Backup automático creado")
        except Exception as e:
            self.alertas.append(f"❌ Error creando backup: {str(e)}")
            self.log(f"ERROR: Backup falló: {e}")
    
    def limpiar_backups_antiguos(self, dias=30):
        """Eliminar backups más antiguos que X días"""
        backup_dir = "backups_usuarios"
        if not os.path.exists(backup_dir):
            return
        
        limite = datetime.now() - timedelta(days=dias)
        eliminados = 0
        
        for filename in os.listdir(backup_dir):
            if filename.startswith("backup_usuarios_") and filename.endswith(".json"):
                filepath = os.path.join(backup_dir, filename)
                file_time = datetime.fromtimestamp(os.path.getctime(filepath))
                
                if file_time < limite:
                    try:
                        os.remove(filepath)
                        eliminados += 1
                    except Exception as e:
                        self.log(f"Error eliminando {filename}: {e}")
        
        if eliminados > 0:
            self.log(f"🧹 Eliminados {eliminados} backups antiguos")
    
    def generar_reporte(self):
        """Generar reporte de estado"""
        reporte = {
            'timestamp': datetime.now().isoformat(),
            'usuarios_total': User.objects.count(),
            'usuarios_admin': User.objects.filter(is_staff=True).count(),
            'usuarios_activos': User.objects.filter(is_active=True).count(),
            'alertas': len(self.alertas),
            'alertas_detalle': self.alertas
        }
        
        # Guardar reporte
        reporte_file = f"reporte_usuarios_{datetime.now().strftime('%Y%m%d')}.json"
        with open(reporte_file, 'w', encoding='utf-8') as f:
            json.dump(reporte, f, indent=2, ensure_ascii=False)
        
        return reporte
    
    def enviar_alertas_por_email(self, reporte):
        """Enviar alertas por email si hay problemas (configurar según necesidades)"""
        if not self.alertas:
            return
        
        # Configurar según tu proveedor de email
        # EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD
        
        destinatario = "admin@tudominio.com"  # Cambiar por tu email
        asunto = f"🚨 Alertas de Usuario - {len(self.alertas)} problemas"
        
        mensaje = f"""
        REPORTE DE USUARIOS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        ALERTAS DETECTADAS ({len(self.alertas)}):
        {''.join([f'• {alerta}' for alerta in self.alertas])}
        
        ESTADÍSTICAS:
        • Total usuarios: {reporte['usuarios_total']}
        • Administradores: {reporte['usuarios_admin']}  
        • Usuarios activos: {reporte['usuarios_activos']}
        
        Revisa el sistema inmediatamente.
        """
        
        # Descomentar y configurar si quieres emails automáticos
        # try:
        #     send_mail(asunto, mensaje, 'noreply@tuapp.com', [destinatario])
        #     self.log(f"📧 Email de alerta enviado a {destinatario}")
        # except Exception as e:
        #     self.log(f"ERROR enviando email: {e}")
    
    def ejecutar_monitoreo_completo(self):
        """Ejecutar monitoreo completo del sistema"""
        self.log("🚀 INICIANDO MONITOREO AUTOMÁTICO")
        
        # Verificaciones principales
        if not self.verificar_conexion_db():
            self.log("❌ Monitoreo abortado por error de conexión")
            return False
        
        self.verificar_usuarios_criticos()
        self.verificar_total_usuarios()
        self.crear_backup_automatico()
        self.limpiar_backups_antiguos()
        
        # Generar reporte
        reporte = self.generar_reporte()
        
        # Alertas por email si es necesario
        self.enviar_alertas_por_email(reporte)
        
        # Log final
        if self.alertas:
            self.log(f"⚠️  MONITOREO COMPLETADO CON {len(self.alertas)} ALERTAS")
            for alerta in self.alertas:
                self.log(f"   {alerta}")
        else:
            self.log("✅ MONITOREO COMPLETADO - TODO OK")
        
        self.log("=" * 60)
        return True

def main():
    """Función principal para ejecutar como script"""
    monitor = MonitorUsuarios()
    monitor.ejecutar_monitoreo_completo()

if __name__ == '__main__':
    main()