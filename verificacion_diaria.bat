@echo off
:: Script de verificación diaria de usuarios (Windows)
:: Ejecutar esto cada día para verificar que todo esté OK

echo.
echo ================================
echo   VERIFICACION DIARIA USUARIOS
echo ================================
echo.

echo Verificando sistema...
python manage.py check
if errorlevel 1 (
    echo ERROR: Problema con Django
    pause
    exit /b 1
)

echo.
echo Verificando usuarios...
python manage.py backup_usuarios --check-only
if errorlevel 1 (
    echo ERROR: Problema con usuarios
    pause
    exit /b 1
)

echo.
echo Creando backup de seguridad...
python manage.py backup_usuarios --backup-only
if errorlevel 1 (
    echo ERROR: Problema creando backup
    pause
    exit /b 1
)

echo.
echo ================================
echo   VERIFICACION COMPLETADA ✅
echo ================================
echo.
echo Usuarios protegidos correctamente!
echo Backup creado en: backups_usuarios/
echo.

pause