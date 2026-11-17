@echo off
rem Comprobar permisos de Administrador
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Solicitando permisos de Administrador...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process cmd -ArgumentList '/k \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

title Desbloqueo de Firewall - Aldelo Comandero
color 0A
cls
echo ========================================================
echo   CONFIGURANDO FIREWALL PARA ALDELO COMANDERO MOVIL
echo ========================================================
echo.

echo 1. Eliminando reglas de bloqueo de Python...
netsh advfirewall firewall delete rule name="python.exe" >nul 2>&1

echo 2. Habilitando puerto 8000 en el Firewall de Windows...
netsh advfirewall firewall add rule name="Aldelo Comandero 8000" dir=in action=allow protocol=TCP localport=8000 profile=any

echo 3. Habilitando acceso al ejecutable Python...
netsh advfirewall firewall add rule name="Aldelo Comandero Python" dir=in action=allow program="C:\Users\Steven V Dj\AppData\Local\Python\pythoncore-3.14-64\python.exe" profile=any

echo 4. Configurando red Wi-Fi como Red Privada...
powershell -NoProfile -Command "Set-NetConnectionProfile -InterfaceAlias 'Wi-Fi' -NetworkCategory Private -ErrorAction SilentlyContinue"

echo.
echo ========================================================
echo   EXITO: ACCESO DESBLOQUEADO CORRECTAMENTE
echo ========================================================
echo.
echo Ya puedes ingresar desde tu celular o tablet al enlace:
echo.
echo     http://192.168.100.129:8000
echo.
echo ========================================================
pause
