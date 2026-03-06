from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from mundo.models import PerfilUsuario
from django.utils import timezone
import json
import os
from datetime import datetime

class Command(BaseCommand):
    help = 'Genera backup de usuarios y verifica su estado'

    def add_arguments(self, parser):
        parser.add_argument(
            '--backup-only',
            action='store_true',
            help='Solo crear backup, no mostrar información',
        )
        parser.add_argument(
            '--check-only',
            action='store_true',
            help='Solo verificar usuarios, no crear backup',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🔍 Iniciando verificación de usuarios...'))
        
        if not options['backup_only']:
            self.verificar_usuarios()
        
        if not options['check_only']:
            self.crear_backup()
        
        self.stdout.write(self.style.SUCCESS('✅ Proceso completado'))

    def verificar_usuarios(self):
        """Verificar estado de usuarios"""
        total_usuarios = User.objects.count()
        usuarios_admin = User.objects.filter(is_staff=True).count()
        usuarios_activos = User.objects.filter(is_active=True).count()
        
        self.stdout.write(f"\n📊 ESTADÍSTICAS DE USUARIOS:")
        self.stdout.write(f"   Total: {total_usuarios}")
        self.stdout.write(f"   Administradores: {usuarios_admin}")
        self.stdout.write(f"   Activos: {usuarios_activos}")
        
        if total_usuarios == 0:
            self.stdout.write(
                self.style.WARNING("⚠️  NO HAY USUARIOS REGISTRADOS!")
            )
        else:
            self.stdout.write(f"\n👥 USUARIOS REGISTRADOS:")
            for user in User.objects.all().order_by('-date_joined'):
                admin_icon = "👑" if user.is_staff else "👤"
                status_icon = "✅" if user.is_active else "❌"
                self.stdout.write(
                    f"   {admin_icon} {user.username} {status_icon} "
                    f"({user.date_joined.strftime('%Y-%m-%d %H:%M')})"
                )
        
        # Verificar perfiles
        perfiles_count = PerfilUsuario.objects.count()
        self.stdout.write(f"\n📋 Perfiles asociados: {perfiles_count}")

    def crear_backup(self):
        """Crear backup de usuarios"""
        try:
            backup_data = {
                'timestamp': timezone.now().isoformat(),
                'total_usuarios': User.objects.count(),
                'usuarios': []
            }
            
            for user in User.objects.all():
                # Obtener perfil si existe
                perfil_data = None
                try:
                    perfil = user.perfil
                    perfil_data = {
                        'fecha_vencimiento': perfil.fecha_vencimiento.isoformat() if perfil.fecha_vencimiento else None,
                        'suscripcion_activa': perfil.suscripcion_activa
                    }
                except PerfilUsuario.DoesNotExist:
                    pass
                
                user_data = {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'is_active': user.is_active,
                    'is_staff': user.is_staff,
                    'is_superuser': user.is_superuser,
                    'date_joined': user.date_joined.isoformat(),
                    'last_login': user.last_login.isoformat() if user.last_login else None,
                    'perfil': perfil_data
                }
                backup_data['usuarios'].append(user_data)
            
            # Crear directorio si no existe
            backup_dir = 'backups_usuarios'
            os.makedirs(backup_dir, exist_ok=True)
            
            # Nombre del archivo
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{backup_dir}/backup_usuarios_{timestamp}.json"
            
            # Escribir archivo
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, indent=2, ensure_ascii=False)
            
            self.stdout.write(
                self.style.SUCCESS(f"💾 Backup creado: {filename}")
            )
            
            return filename
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error al crear backup: {e}")
            )
            return None