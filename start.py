import os
import sys
import socket
import json
import subprocess
import webbrowser

# Force UTF-8 on Windows console output to prevent cp1252 / cp850 UnicodeEncodeError
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure bundled root is in sys.path
if getattr(sys, "frozen", False):
    BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import uvicorn
from backend.paths import get_config_path, get_app_dir
from backend import db
from backend.main import app

def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def check_service_running(port: int = 8000) -> bool:
    try:
        import urllib.request
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/info", headers={"User-Agent": "AldeloHealthCheck"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                if data.get("system") == "Aldelo POS Bridge":
                    return True
    except Exception:
        pass
    return False

def ensure_firewall_and_network():
    """Silently attempts to open firewall port and set network to private if elevated."""
    if sys.platform.startswith("win"):
        try:
            subprocess.run(
                'netsh advfirewall firewall add rule name="Aldelo Comandero 8000" dir=in action=allow protocol=TCP localport=8000 profile=any',
                shell=True, capture_output=True, timeout=3
            )
            subprocess.run(
                'powershell -NoProfile -Command "Get-NetConnectionProfile | Set-NetConnectionProfile -NetworkCategory Private -ErrorAction SilentlyContinue"',
                shell=True, capture_output=True, timeout=3
            )
        except Exception:
            pass

def check_or_configure_database():
    """Detects or configures the active Aldelo database."""
    reg_db = db.get_aldelo_registry_database_path()
    if reg_db and os.path.exists(reg_db):
        return reg_db, "Auto-detectada desde Aldelo (Registro de Windows)"
    
    cfg_path = get_config_path()
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                custom = cfg.get("database_path")
                if custom and os.path.exists(custom):
                    return custom, "Configurada en config.json"
        except Exception:
            pass

    # Search common fallback paths
    common_paths = [
        r"C:\ProgramData\Aldelo\Aldelo For Restaurants\Databases\Samples\Standard\adResDemo.mdb",
        r"C:\Aldelo For Restaurants\Databases\adResDemo.mdb"
    ]
    for cp in common_paths:
        if os.path.exists(cp):
            return cp, "Ubicacion estandar de Aldelo"

    # Interactive prompt if running in console
    print("\n" + "=" * 65)
    print(" [!] ATENCION: NO SE DETECTO LA BASE DE DATOS DE ALDELO")
    print("=" * 65)
    print(" Ingrese o arrastre la ruta de su archivo .mdb de Aldelo:")
    print(" Ejemplo: C:\\Aldelo\\PORTONES SONESTA.mdb\n")
    try:
        user_path = input(" Ruta de la base de datos (.mdb): ").strip().strip('"')
        if user_path and os.path.exists(user_path):
            cfg = {}
            if os.path.exists(cfg_path):
                try:
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                except Exception:
                    pass
            cfg["database_path"] = user_path
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
            print(f" [OK] Guardado en config.json: {user_path}")
            return user_path, "Ingresada por el usuario"
    except Exception:
        pass

    return db.DEFAULT_MDB_PATH, "Ruta de demostracion (Por defecto)"

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def show_interactive_manager(port: int, local_ip: str, db_filename: str):
    while True:
        print("\n" + "=" * 68)
        print("          >>> ALDELO COMANDERO MOVIL (Servidor POS) <<<")
        print("=" * 68)
        print(f"  [Estado]:          ACTIVO (Ejecutandose en segundo plano)")
        print(f"  [Base de Datos]:   {db_filename}")
        print(f"  [PC Local]:        http://localhost:{port}")
        print(f"  [Movil / Tablet]:  http://{local_ip}:{port}")
        print("-" * 68)
        print("  [*] El servicio esta activo para recibir comandas de las tablets.")
        print()
        print("  Opciones:")
        print("    [1] Abrir Comandero en el Navegador de este PC")
        print("    [2] Reiniciar servicio de segundo plano")
        print("    [3] Detener servicio")
        print("    [4] Salir (El servicio seguira funcionando para las tablets)")
        print("=" * 68)
        try:
            choice = input(" Seleccione una opcion (1-4) [default: 1]: ").strip()
            if choice == "1" or choice == "":
                webbrowser.open(f"http://localhost:{port}")
            elif choice == "2":
                print(" [i] Reiniciando servicio...")
                subprocess.run('powershell -NoProfile -Command "Restart-ScheduledTask -TaskName \'AldeloComandero_Service\' -ErrorAction SilentlyContinue"', shell=True)
                subprocess.run('taskkill /F /IM AldeloComandero.exe /T', shell=True, capture_output=True)
                break
            elif choice == "3":
                print(" [i] Deteniendo servicio...")
                subprocess.run('powershell -NoProfile -Command "Stop-ScheduledTask -TaskName \'AldeloComandero_Service\' -ErrorAction SilentlyContinue"', shell=True)
                subprocess.run('taskkill /F /IM AldeloComandero.exe /T', shell=True, capture_output=True)
                print(" [OK] Servicio detenido.")
                break
            elif choice == "4":
                print(" [OK] Saliendo de la ventana de administracion. El servicio continua activo.")
                break
        except (KeyboardInterrupt, EOFError):
            break

def main():
    ensure_firewall_and_network()
    
    port = 8000
    cfg_path = get_config_path()
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                port = int(cfg.get("port", 8000))
        except Exception:
            pass

    is_service_mode = "--service" in sys.argv
    local_ip = get_local_ip()

    # If the bridge is already actively responding on port 8000:
    if check_service_running(port):
        if is_service_mode:
            # Service is already running, exit quietly
            sys.exit(0)
        else:
            db_path = db.get_database_path()
            db_filename = os.path.basename(db_path)
            show_interactive_manager(port, local_ip, db_filename)
            sys.exit(0)

    db_path, db_origin = check_or_configure_database()

    # If running as background service, start immediately with minimal logging
    if is_service_mode:
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
        return

    # Port conflict resolution if not Aldelo bridge
    if is_port_in_use(port):
        print(f" [!] Nota: El puerto {port} esta en uso por otro programa. Buscando puerto disponible...")
        for alt_port in range(port + 1, port + 10):
            if not is_port_in_use(alt_port):
                port = alt_port
                break

    db_filename = os.path.basename(db_path)

    print()
    print("=" * 68)
    print("          >>> ALDELO COMANDERO MOVIL (Servidor POS) <<<")
    print("=" * 68)
    print(f"  [Base de Datos]:   {db_filename}")
    print(f"  [Origen]:          {db_origin}")
    print(f"  [Ruta]:            {db_path}")
    print(f"  [PC Local]:        http://localhost:{port}")
    print(f"  [Movil / Tablet]:  http://{local_ip}:{port}")
    print("-" * 68)
    print("  [*] CONECTAR TABLETS O TELEFONOS (Meseros):")
    print(f"     1. Conecte la tablet a la misma red Wi-Fi.")
    print(f"     2. Abra el navegador (Safari en iOS / Chrome en Android).")
    print(f"     3. Ingrese a la direccion:")
    print(f"        ->  http://{local_ip}:{port}")
    print()
    print("  [*] MODO PANTALLA COMPLETA (Como App Nativa):")
    print("     * iOS (iPad/iPhone): Safari -> Compartir -> 'Agregar a inicio'.")
    print("     * Android: Chrome -> Menu (tres puntos) -> 'Instalar app' o 'Agregar a pantalla'.")
    print("=" * 68)
    print("  Presione Ctrl+C en esta ventana para cerrar el servidor manual.\n")

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")

if __name__ == "__main__":
    main()
