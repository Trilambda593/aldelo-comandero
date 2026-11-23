@echo off
cd /d "%~dp0"
title Instalador Servicio Aldelo Comandero
if exist "dist\InstaladorServicioAldelo.exe" (
    start "" "dist\InstaladorServicioAldelo.exe"
) else if exist "InstaladorServicioAldelo.exe" (
    start "" "InstaladorServicioAldelo.exe"
) else (
    python installer.py
)
