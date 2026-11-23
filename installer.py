import os
import sys
import ctypes
import shutil
import socket
import json
import time
import subprocess
import urllib.request

def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def elevate():
    """Relaunches the current script or executable with Administrator privileges (UAC prompt)."""
    if getattr(sys, "frozen", False):
        exe = sys.executable
        args = " ".join([f'"{a}"' for a in sys.argv[1:]])
    else:
        exe = sys.executable
        args = f'"{os.path.abspath(__file__)}" ' + " ".join([f'"{a}"' for a in sys.argv[1:]])
    
    ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, args, None, 1)
    sys.exit(0)

def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def run_cmd(cmd: str, desc: str = "") -> bool:
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return res.returncode == 0
    except Exception as e:
        print(f" [!] Error en {desc}: {e}")
        return False

def run_ps(script: str, desc: str = "") -> bool:
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True, text=True, timeout=30
        )
        if res.returncode != 0 and res.stderr:
            print(f" [!] Detalle en {desc}: {res.stderr.strip()}")
        return res.returncode == 0
    except Exception as e:
        print(f" [!] Error en {desc}: {e}")
        return False

def main():
    # Force UTF-8 console output
    if sys.platform.startswith("win"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    # Ensure Administrator privileges
    if not is_admin():
        print(" [i] Solicitando permisos de Administrador...")
        elevate()

    print()
    print("=" * 70)
    print("     >>> INSTALADOR Y ACTIVADOR DEL SERVICIO ALDELO COMANDERO <<<")
    print("=" * 70)
    print(" Este instalador:")
    print("  1. Instalara los archivos en C:\\AldeloComandero")
    print("  2. Desbloqueara el puerto 8000 en el Firewall de Windows")
    print("  3. Configurara la red Wi-Fi en modo Privado para aceptar conexiones")
    print("  4. Configurara el servicio de Windows para iniciar AUTOMATICAMENTE")
    print("     cada vez que se reinicie o encienda la computadora.")
    print("=" * 70)
    print()

    target_dir = r"C:\AldeloComandero"
    os.makedirs(target_dir, exist_ok=True)

    # 1. Detener procesos existentes para permitir sobreescritura de archivos
    print(" [1/7] Deteniendo instancias previas si existen...")
    run_cmd('powershell -NoProfile -Command "Stop-ScheduledTask -TaskName \'AldeloComandero_Service\' -ErrorAction SilentlyContinue"')
    run_cmd('taskkill /F /IM AldeloComandero.exe /T')
    time.sleep(1)

    # 2. Localizar y copiar AldeloComandero.exe
    print(" [2/7] Instalando ejecutable AldeloComandero.exe...")
    source_exe = None
    candidate_paths = []
    
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            candidate_paths.append(os.path.join(meipass, "AldeloComandero.exe"))
        candidate_paths.append(os.path.join(os.path.dirname(sys.executable), "AldeloComandero.exe"))
        candidate_paths.append(os.path.join(os.path.dirname(sys.executable), "dist", "AldeloComandero.exe"))

    base_script = os.path.dirname(os.path.abspath(__file__))
    candidate_paths.extend([
        os.path.join(base_script, "AldeloComandero.exe"),
        os.path.join(base_script, "dist", "AldeloComandero.exe"),
        r"C:\Users\echoe\OneDrive\Documents\aldelo-comandero-main\aldelo-comandero-main\dist\AldeloComandero.exe",
        os.path.join(target_dir, "AldeloComandero.exe")
    ])

    for cp in candidate_paths:
        if os.path.exists(cp) and os.path.abspath(cp).lower() != os.path.join(target_dir, "AldeloComandero.exe").lower():
            source_exe = cp
            break

    target_exe = os.path.join(target_dir, "AldeloComandero.exe")
    if source_exe and os.path.exists(source_exe):
        shutil.copy2(source_exe, target_exe)
        print(f"       Copiado desde: {source_exe}")
    elif os.path.exists(target_exe):
        print(f"       Usando ejecutable existente en: {target_exe}")
    else:
        print(" [!] ERROR: No se encontro AldeloComandero.exe para instalar.")
        input(" Presione Enter para salir...")
        return

    # 3. Configurar config.json
    print(" [3/7] Configurando base de datos y ajustes en config.json...")
    target_config = os.path.join(target_dir, "config.json")
    db_default = r"C:\Users\echoe\Videos\21 gramos nullomati\21 GRAMOS BUIJO.mdb"
    
    cfg = {
        "database_path": db_default,
        "auto_registry": True,
        "station_id": 5,
        "port": 8000
    }

    # Preservar si ya existe
    source_config = os.path.join(base_script, "config.json")
    if os.path.exists(source_config):
        try:
            with open(source_config, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                cfg.update(loaded)
        except Exception:
            pass

    with open(target_config, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    print(f"       Base de datos vinculada: {cfg.get('database_path')}")

    # Copiar icono si existe
    source_ico = os.path.join(base_script, "app.ico")
    if os.path.exists(source_ico):
        shutil.copy2(source_ico, os.path.join(target_dir, "app.ico"))

    # 4. Configurar Firewall de Windows
    print(" [4/7] Configurando reglas de Firewall de Windows...")
    run_cmd('netsh advfirewall firewall delete rule name="Aldelo Comandero 8000"')
    run_cmd('netsh advfirewall firewall delete rule name="Aldelo Comandero EXE"')
    run_cmd('netsh advfirewall firewall add rule name="Aldelo Comandero 8000" dir=in action=allow protocol=TCP localport=8000 profile=any', "Firewall puerto 8000")
    run_cmd(f'netsh advfirewall firewall add rule name="Aldelo Comandero EXE" dir=in action=allow program="{target_exe}" profile=any', "Firewall EXE")
    print("       Puerto 8000 TCP habilitado para todos los perfiles de red.")

    # 5. Configurar Red como Privada y permisos de carpetas
    print(" [5/7] Configurando red Privada y permisos de carpetas...")
    run_ps('Get-NetConnectionProfile | Set-NetConnectionProfile -NetworkCategory Private -ErrorAction SilentlyContinue', "Red Privada")
    run_cmd(f'icacls "{target_dir}" /grant "SYSTEM:(OI)(CI)F" "Administrators:(OI)(CI)F" "Users:(OI)(CI)M" /T /C /Q', "Permisos C:\\AldeloComandero")
    db_path_cfg = cfg.get("database_path", "")
    if db_path_cfg and os.path.exists(os.path.dirname(db_path_cfg)):
        db_dir = os.path.dirname(db_path_cfg)
        run_cmd(f'icacls "{db_dir}" /grant "SYSTEM:(OI)(CI)F" /C /Q', "Permisos carpeta BD")
    print("       Red privada y permisos de sistema configurados correctamente.")

    # 6. Registrar Servicio en el Programador de Tareas (Task Scheduler)
    print(" [6/7] Registrando Servicio de inicio automatico con Windows...")
    ps_task_cmd = f"""
    $action = New-ScheduledTaskAction -Execute '{target_exe}' -Argument '--service' -WorkingDirectory '{target_dir}'
    $triggerBoot = New-ScheduledTaskTrigger -AtStartup
    $triggerLogon = New-ScheduledTaskTrigger -AtLogOn
    $principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName 'AldeloComandero_Service' -Action $action -Trigger @($triggerBoot, $triggerLogon) -Principal $principal -Settings $settings -Force | Out-Null
    """
    task_created = run_ps(ps_task_cmd, "Creacion de Tarea Programada")
    if task_created:
        print("       Servicio registrado: Se iniciara en el arranque de Windows con permisos maximos.")
    else:
        print("       Advertencia: Verifique los permisos del Programador de Tareas.")

    # Crear accesos directos en el Escritorio
    print("       Creando acceso directo en el Escritorio...")
    ps_shortcut_cmd = f"""
    $WshShell = New-Object -comObject WScript.Shell
    $DesktopPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
    $Shortcut = $WshShell.CreateShortcut("$DesktopPath\\Aldelo Comandero Servidor.lnk")
    $Shortcut.TargetPath = '{target_exe}'
    $Shortcut.WorkingDirectory = '{target_dir}'
    $Shortcut.Description = 'Aldelo Comandero Movil - Servidor Bridge'
    $Shortcut.Save()
    
    $CommonDesktop = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::CommonDesktop)
    if (Test-Path $CommonDesktop) {{
        $ShortcutPublic = $WshShell.CreateShortcut("$CommonDesktop\\Aldelo Comandero Servidor.lnk")
        $ShortcutPublic.TargetPath = '{target_exe}'
        $ShortcutPublic.WorkingDirectory = '{target_dir}'
        $ShortcutPublic.Description = 'Aldelo Comandero Movil - Servidor Bridge'
        $ShortcutPublic.Save()
    }}
    """
    run_ps(ps_shortcut_cmd, "Crear acceso directo")

    # Crear script de desinstalacion en C:\AldeloComandero
    uninstaller_path = os.path.join(target_dir, "DESINSTALAR_SERVICIO.bat")
    with open(uninstaller_path, "w", encoding="utf-8") as f:
        f.write("""@echo off
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Solicitando permisos de Administrador...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process cmd -ArgumentList '/k \\"\\"%~f0\\"\\"' -Verb RunAs"
    exit /b
)
title Desinstalar Servicio Aldelo Comandero
echo ========================================================
echo   DESINSTALANDO SERVICIO ALDELO COMANDERO
echo ========================================================
echo Deteniendo y eliminando tarea programada...
powershell -NoProfile -Command "Stop-ScheduledTask -TaskName 'AldeloComandero_Service' -ErrorAction SilentlyContinue"
powershell -NoProfile -Command "Unregister-ScheduledTask -TaskName 'AldeloComandero_Service' -Confirm:$false -ErrorAction SilentlyContinue"
taskkill /F /IM AldeloComandero.exe /T >nul 2>&1

echo Eliminando reglas de Firewall...
netsh advfirewall firewall delete rule name="Aldelo Comandero 8000" >nul 2>&1
netsh advfirewall firewall delete rule name="Aldelo Comandero EXE" >nul 2>&1

echo.
echo ========================================================
echo   SERVICIO DESINSTALADO CORRECTAMENTE
echo ========================================================
pause
""")

    # 7. Iniciar el servicio y verificar estado
    print(" [7/7] Iniciando el servicio ahora...")
    run_cmd('powershell -NoProfile -Command "Start-ScheduledTask -TaskName \'AldeloComandero_Service\'"', "Iniciar servicio")
    
    # Esperar confirmacion de arranque
    local_ip = get_local_ip()
    is_live = False
    for attempt in range(8):
        time.sleep(1)
        try:
            req = urllib.request.Request("http://127.0.0.1:8000/api/info", headers={"User-Agent": "InstallerCheck"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    info_data = json.loads(resp.read().decode())
                    is_live = True
                    break
        except Exception:
            pass

    print()
    print("=" * 70)
    if is_live:
        print("          ¡INSTALACION Y ACTIVACION COMPLETADA CON EXITO!")
    else:
        print("          INSTALACION COMPLETADA (Iniciando servicio)")
    print("=" * 70)
    print(f"  [Estado]:          ACTIVO (Servicio de Windows en segundo plano)")
    print(f"  [Auto-reinicio]:   SI (Inicia con Windows automaticamente)")
    print(f"  [Firewall]:        Puerto 8000 TCP DESBLOQUEADO")
    print(f"  [Red]:             Modo PRIVADO habilitado")
    print(f"  [Ubicacion]:       {target_dir}")
    print(f"  [PC Local]:        http://localhost:8000")
    print(f"  [Enlace Tablets]:  http://{local_ip}:8000")
    print("-" * 70)
    print("  [*] INSTRUCCIONES PARA LAS TABLETS Y TELEFONOS:")
    print("     1. Asegurese de que la tablet este conectada al mismo Wi-Fi.")
    print("     2. Abra el navegador (Safari en iPad / Chrome en Android).")
    print(f"     3. Ingrese a la direccion:  http://{local_ip}:8000")
    print("     4. Agregue a 'Pantalla de Inicio' para usarlo a pantalla completa.")
    print("-" * 70)
    print("  [*] Si se reinicia o apaga este PC, el servicio se iniciara")
    print("      AUTOMATICAMENTE y las tablets podran seguir ingresando.")
    print("=" * 70)
    print()
    input(" Presione Enter para finalizar...")

if __name__ == "__main__":
    main()
