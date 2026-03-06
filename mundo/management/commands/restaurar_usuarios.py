from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from mundo.models import PerfilUsuario
from django.utils import timezone
from dateutil import parser
import json
import os

class Command(BaseCommand):
    help = 'Restaura usuarios desde un archivo de backup JSON'

    def add_arguments(self, parser):
        parser.add_argument(
            'backup_file',
            type=str,
            help='Ruta al archivo de backup JSON'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo mostrar qué se haría, sin hacer cambios reales',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forzar restauración incluso si alguns usuarios ya existen',
        )

    def handle(self, *args, **options):
        backup_file = options['backup_file']
        dry_run = options['dry_run']
        force = options['force']
        
        if not os.path.exists(backup_file):
            raise CommandError(f"❌ Archivo de backup no encontrado: {backup_file}")
        
        self.stdout.write(f"📂 Cargando backup: {backup_file}")
        
        try:
            with open(backup_file, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
        except Exception as e:
            raise CommandError(f"❌ Error al leer backup: {e}")
        
        usuarios_backup = backup_data.get('usuarios', [])
        timestamp_backup = backup_data.get('timestamp', 'N/A')
        
        self.stdout.write(f"🕐 Backup fecha: {timestamp_backup}")
        self.stdout.write(f"👥 Usuarios en backup: {len(usuarios_backup)}")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("🔍 MODO DRY-RUN - Solo simulación"))
        
        restaurados = 0
        actualizados = 0
        errores = 0
        
        for user_data in usuarios_backup:
            try:
                username = user_data['username']
                
                # Verificar si el usuario ya existe
                existing_user = None
                try:
                    existing_user = User.objects.get(username=username)
                except User.DoesNotExist:
                    pass
                
                if existing_user:
                    if not force:
                        self.stdout.write(
                            self.style.WARNING(f"⚠️  Usuario ya existe: {username} (use --force para actualizar)")
                        )
                        continue
                    
                    if not dry_run:
                        # Actualizar usuario existente
                        existing_user.email = user_data.get('email', '')
                        existing_user.first_name = user_data.get('first_name', '')
                        existing_user.last_name = user_data.get('last_name', '')
                        existing_user.is_active = user_data.get('is_active', True)
                        existing_user.is_staff = user_data.get('is_staff', False)
                        existing_user.is_superuser = user_data.get('is_superuser', False)
                        existing_user.save()
                    
                    self.stdout.write(f"✅ Usuario actualizado: {username}")
                    actualizados += 1
                    
                else:
                    # Crear nuevo usuario
                    if not dry_run:
                        new_user = User.objects.create_user(
                            username=username,
                            email=user_data.get('email', ''),
                            first_name=user_data.get('first_name', ''),
                            last_name=user_data.get('last_name', ''),
                        )
                        
                        new_user.is_active = user_data.get('is_active', True)
                        new_user.is_staff = user_data.get('is_staff', False)
                        new_user.is_superuser = user_data.get('is_superuser', False)
                        
                        # Restaurar fechas si es posible
                        if user_data.get('date_joined'):
                            try:
                                new_user.date_joined = parser.parse(user_data['date_joined'])
                            except:
                                pass
                        
                        if user_data.get('last_login'):
                            try:
                                new_user.last_login = parser.parse(user_data['last_login'])
                            except:
                                pass
                        
                        new_user.save()
                        
                        # Restaurar perfil si existe
                        perfil_data = user_data.get('perfil')
                        if perfil_data:
                            perfil, created = PerfilUsuario.objects.get_or_create(
                                user=new_user,
                                defaults={}
                            )
                            
                            if perfil_data.get('fecha_vencimiento'):
                                try:
                                    perfil.fecha_vencimiento = parser.parse(perfil_data['fecha_vencimiento'])
                                    perfil.save()
                                except:
                                    pass
                    
                    self.stdout.write(f"✅ Usuario restaurado: {username}")
                    restaurados += 1
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"❌ Error al procesar {username}: {e}")
                )
                errores += 1
        
        # Resumen
        self.stdout.write(f"\n📊 RESUMEN:")
        self.stdout.write(f"   Restaurados: {restaurados}")
        self.stdout.write(f"   Actualizados: {actualizados}")
        self.stdout.write(f"   Errores: {errores}")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("🔍 Fue una simulación - no se hicieron cambios reales"))
        else:
            self.stdout.write(self.style.SUCCESS("✅ Restauración completada"))