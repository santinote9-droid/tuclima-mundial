#!/usr/bin/env python
"""
Script para crear/actualizar el usuario administrador sangioff
"""
import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nucleo.settings')
django.setup()

from django.contrib.auth.models import User

# Datos del usuario — cargar desde entorno o pasar por argumento
username = os.environ.get('ADMIN_USERNAME', 'sangioff')
email    = os.environ.get('ADMIN_EMAIL', 'sangioff@tuclima.com')
password = os.environ.get('ADMIN_PASSWORD', '')  # Obligatorio: setear ADMIN_PASSWORD en entorno

# Verificar si el usuario ya existe
user = User.objects.filter(username=username).first()

if user:
    print(f"✅ Usuario '{username}' ya existe. Actualizando...")
    user.email = email
    user.set_password(password)
    user.is_staff = True
    user.is_superuser = True
    user.save()
    print(f"✅ Usuario '{username}' actualizado correctamente")
    print(f"   - Email: {email}")
    print(f"   - Staff: {user.is_staff}")
    print(f"   - Superuser: {user.is_superuser}")
else:
    print(f"⚠️  Usuario '{username}' no existe. Creando...")
    user = User.objects.create_superuser(
        username=username,
        email=email,
        password=password
    )
    print(f"✅ Usuario '{username}' creado correctamente")
    print(f"   - Email: {email}")
    print(f"   - Staff: {user.is_staff}")
    print(f"   - Superuser: {user.is_superuser}")

print("\n🎉 Puedes ahora iniciar sesión con:")
print(f"   Usuario: {username}")
print(f"   Contraseña: {password}")
