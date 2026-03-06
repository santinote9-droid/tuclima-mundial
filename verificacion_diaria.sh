#!/bin/bash
# Script de verificación diaria de usuarios (Linux/Mac)
# Ejecutar esto cada día para verificar que todo esté OK

echo ""
echo "==============================="
echo "  VERIFICACION DIARIA USUARIOS"
echo "==============================="
echo ""

echo "Verificando sistema..."
python manage.py check
if [ $? -ne 0 ]; then
    echo "ERROR: Problema con Django"
    exit 1
fi

echo ""
echo "Verificando usuarios..."
python manage.py backup_usuarios --check-only
if [ $? -ne 0 ]; then
    echo "ERROR: Problema con usuarios"
    exit 1
fi

echo ""
echo "Creando backup de seguridad..."
python manage.py backup_usuarios --backup-only
if [ $? -ne 0 ]; then
    echo "ERROR: Problema creando backup"
    exit 1
fi

echo ""
echo "==============================="
echo "  VERIFICACION COMPLETADA ✅"
echo "==============================="
echo ""
echo "Usuarios protegidos correctamente!"
echo "Backup creado en: backups_usuarios/"
echo ""