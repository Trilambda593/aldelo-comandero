import os
import sys
import socket
import json

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

def main():
    db_path, db_origin = check_or_configure_database()
    local_ip = get_local_ip()
    
    port = 8000
    cfg_path = get_config_path()
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                port = int(cfg.get("port", 8000))
        except Exception:
            pass

    # Port conflict resolution
    if is_port_in_use(port):
        print(f" [!] Nota: El puerto {port} esta en uso. Buscando puerto disponible...")
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
    print("  Presione Ctrl+C en esta ventana para cerrar el servidor.\n")

    # Run uvicorn directly with app instance
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")

if __name__ == "__main__":
    main()
