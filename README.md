# Aldelo Comandero Móvil (iOS & Android)

Sistema táctil de comandas móviles para meseros que se sincroniza en tiempo real con **Aldelo POS for Restaurants**.

---

## ⚡ Instalación y Auto-Inicio con Windows (Recomendado)

Para que el sistema funcione siempre en segundo plano y **continúe ejecutándose automáticamente cada vez que se reinicie o encienda Windows**:

1. Haz doble clic en **`InstaladorServicioAldelo.exe`** (o ejecuta `INSTALAR_Y_ACTIVAR_SERVICIO.bat`).
2. Acepta los permisos de Administrador (UAC).
3. El instalador automáticamente:
   - Desbloquea el puerto `8000` en el Firewall de Windows.
   - Configura la red Wi-Fi en modo Privado (para permitir el acceso de las tablets).
   - Instala los archivos en `C:\AldeloComandero`.
   - Registra el servicio en el Programador de Tareas de Windows para arrancar automáticamente al inicio de Windows.
   - Crea un acceso directo en tu Escritorio: **"Aldelo Comandero Servidor"**.
   - Inicia el servicio inmediatamente sin necesidad de reiniciar.

---

## 🚀 Conexión de Tablets y Celulares (Meseros)

- **Desde esta PC:** [http://localhost:8000](http://localhost:8000)
- **Desde iPhone, iPad, Android o Tablets:**
  👉 **`http://<IP-DE-ESTA-PC>:8000`** (por ejemplo: `http://192.168.3.58:8000`)

### ¿Cómo usarlo como App nativa en la Tablet?
1. Conecta la tablet a la **misma red Wi-Fi** del restaurante.
2. Abre el navegador (**Safari** en iPad / **Chrome** en Android).
3. Entra a `http://<IP-DE-ESTA-PC>:8000`.
4. Pulsa en el menú y selecciona **"Agregar a inicio"** o **"Instalar aplicación"**.
5. Se abrirá a pantalla completa como una aplicación instalada.

---

## 🛠️ Ejecución Manual / Portátil

Si deseas ejecutar el servidor directamente en una ventana sin instalarlo como servicio:
- Haz doble clic en **`AldeloComandero.exe`** o ejecuta `run_comandero.bat`.
- Si el servicio ya está activo en segundo plano, la ventana te mostrará el estado actual, el enlace para las tablets y opciones para abrir el navegador o reiniciar el servicio.

---

## 🗑️ Desinstalación del Servicio

Si en algún momento deseas desactivar el servicio de arranque automático:
- Ejecuta `C:\AldeloComandero\DESINSTALAR_SERVICIO.bat` como Administrador.
