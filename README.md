# Aldelo Comandero Móvil (iOS & Android)

Sistema táctil de comandas móviles para meseros que se sincroniza en tiempo real con **Aldelo POS for Restaurants**.

## 🚀 Acceso Rápido

El servidor ya está en ejecución en tu PC:
- **En esta PC:** [http://localhost:8000](http://localhost:8000)
- **Desde iPhone / iPad / Android:** Abre tu navegador y entra a:
  👉 **`http://192.168.100.129:8000`**

### ¿Cómo usarlo como App nativa en el móvil?
1. Abre el enlace en **Safari (iOS)** o **Chrome (Android)**.
2. Toca el botón compartir / menú y selecciona **"Agregar a pantalla de inicio"**.
3. Se abrirá a pantalla completa, sin barras de navegación, con aspecto y fluidez nativa.

---

## 📱 Pantallas Clonadas de Aldelo

1. **Login con PIN:** Ingreso rápido para meseros (ej. PIN `1` para Oscar).
2. **Selector de Mesas:** Filtro por áreas (Main Dining Room, Patio, Banquet...) con rejilla gráfica de mesas en tiempo real.
3. **Número de Comensales:** Teclado táctil para registrar la cantidad de personas.
4. **Toma de Pedido / Menú:** Categorías laterales, grilla de platos con iconos oficiales de Aldelo y panel de ticket en vivo con cálculo automático de impuestos (7.5%).
5. **Modificadores Dinámicos:** Ventana emergente paso a paso para platos con opciones obligatorias (ej. tipo de pan, guarnición).
6. **Done / Enviar a Cocina:** Guarda la comanda directamente en `OrderHeaders` y `OrderTransactions` de `adResDemo.mdb` para que Aldelo la imprima y facture.

---

## 🛠️ Iniciar el Servidor en el Futuro

Simplemente haz doble clic en el archivo:
`run_comandero.bat`
