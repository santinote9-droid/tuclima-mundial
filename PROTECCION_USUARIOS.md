# 👥 SISTEMA DE PROTECCIÓN DE USUARIOS

Este documento explica cómo proteger y verificar usuarios en tu aplicación Django.

## 🛡️ Protecciones Implementadas

### 1. Variables de Entorno Seguras
- **DATABASE_URL**: Configuración explícita de PostgreSQL
- **Persistencia**: Conexiones de larga duración (10 minutos)
- **Transacciones atómicas**: Garantiza integridad de datos

### 2. Configuración Mejorada de Base de Datos
- ✅ **PostgreSQL con Supabase**: Base de datos en la nube
- ✅ **Verificación de salud de conexiones**: Detecta problemas automáticamente
- ✅ **Timeouts configurados**: Evita conexiones colgadas
- ✅ **Transacciones serializables**: Máximo nivel de consistencia

### 3. Sistema de Backup Automático
- 💾 **Backups JSON**: Preserva toda la información de usuarios
- 📅 **Timestamp automático**: Nombres únicos con fecha/hora
- 🔄 **Recuperación automática**: Scripts de restauración incluidos

## 🚀 Herramientas Disponibles

### Verificación Manual
```bash
# Verificar estado de usuarios y crear backup
python verificar_usuarios.py

# Solo crear backup via comando Django
python manage.py backup_usuarios

# Solo verificar (sin backup)
python manage.py backup_usuarios --check-only
```

### Restauración de Usuarios
```bash
# Simular restauración (no hace cambios)
python manage.py restaurar_usuarios backup_file.json --dry-run

# Restaurar usuarios desde backup
python manage.py restaurar_usuarios backup_file.json

# Forzar actualización de usuarios existentes
python manage.py restaurar_usuarios backup_file.json --force
```

## 📋 Comandos Útiles

### Verificación de Base de Datos
```bash
# Verificar estado general del sistema
python manage.py check

# Ver qué base de datos se está usando
python manage.py shell -c "from django.conf import settings; print(settings.DATABASES['default'])"

# Contar usuarios actuales
python manage.py shell -c "from django.contrib.auth.models import User; print('Usuarios:', User.objects.count())"
```

### Migraciciones y Configuración
```bash
# Verificar migraciones
python manage.py showmigrations

# Aplicar migraciones pendientes
python manage.py migrate

# Crear superuser si es necesario
python manage.py createsuperuser
```

## 🔍 Monitoreo Continuo

### Lista de Verificación Diaria
- [ ] Ejecutar `python verificar_usuarios.py`
- [ ] Verificar que hay backup reciente en `backups_usuarios/`
- [ ] Confirmar que usuarios críticos existen
- [ ] Revisar logs por errores de conexión

### Lista de Verificación Semanal
- [ ] Revisar espacio en Supabase
- [ ] Limpiar backups antiguos (conservar últimos 30 días)
- [ ] Verificar variables de entorno
- [ ] Actualizar dependencias si es necesario

## 🆘 Problemas Comunes y Soluciones

### "No hay usuarios"
1. Verifica conexión: `python verificar_usuarios.py`
2. Revisa la base de datos en Supabase
3. Restaura desde backup más reciente

### "Error de conexión a base de datos"
1. Verifica archivo `.env`
2. Confirma credenciales de Supabase
3. Revisa conectividad a internet

### "Usuarios se borran periódicamente"
1. Verifica que no hay scripts que borren usuarios
2. Confirma que DATABASE_URL está en `.env`
3. Revisa logs de Supabase para actividad inusual

## 📁 Estructura de Archivos

```
proyecto_clima/
├── .env                           # Variables de entorno
├── verificar_usuarios.py          # Script independiente de verificación
├── backups_usuarios/              # Directorio de backups automáticos
│   ├── backup_usuarios_20260228_142841.json
│   └── backup_usuarios_20260228_142858.json
└── mundo/management/commands/     # Comandos Django personalizados
    ├── backup_usuarios.py         # Backup via comando Django
    └── restaurar_usuarios.py      # Restauración de usuarios
```

## ✅ Estado Actual

- **Base de Datos**: PostgreSQL en Supabase ✅
- **Usuario Admin**: Sangioff (activo) ✅  
- **Fecha último registro**: 2026-02-28 17:07 ✅
- **Backups**: Funcionando automáticamente ✅
- **Variables de entorno**: Configuradas ✅

## 🔧 Configuración Técnica Aplicada

### Variables de Entorno (`.env`)
```env
DATABASE_URL=postgresql://postgres.lmumvstjdyaozewqygfx:Sangioff_23@aws-1-us-east-2.pooler.supabase.com:5432/postgres
DB_CONN_MAX_AGE=600
DB_ATOMIC_REQUESTS=True
```

### Configuración de Base de Datos Mejorada
- **Connection pooling**: Mantiene conexiones activas
- **Health checks**: Verifica estado de conexiones
- **Atomic requests**: Todas las requests en transacciones
- **Timeout configuration**: Evita conexiones colgadas

---

🎯 **Resultado**: Usuarios completamente protegidos con backup automático y monitoreo continuo.