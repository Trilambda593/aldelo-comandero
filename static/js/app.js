const app = {
  currentWaiter: null,
  enteredPin: "",
  pendingTarget: "dinein", // "dinein" | "recall" | "backoffice"
  
  tableGroups: [],
  activeGroupId: 1,
  allTables: [],
  selectedTable: null,
  guestCount: 4,
  menuGroups: [],
  activeMenuGroupId: 1,
  currentMenuItems: [],
  orderItems: [], // [ { item_id, name, unit_price, quantity, modifiers: [] } ]
  currentOrderId: null,
  selectedTicketItemIndex: -1,
  taxRate: 15.0, // Dynamic from DB
  
  // Pending modifier workflow
  pendingItem: null,
  modifierSteps: [],
  currentModStepIndex: 0,
  currentSelectedModsForStep: [],

  // Cancel & Reduce flow state
  cancelPinEntered: "",
  cancelAuthorizedEmployee: null,
  pendingCancelAction: null, // "reduce" | "cancel_line"
  reduceSelectedIndex: 0,
  reduceSnapshot: null,
  cancelIsLoss: false,
  cancelReason: "",
  reasonCapsLock: true,
  qtyInputStr: "",
  pendingQuantity: 1,

  // Recall screen state
  recallFilter: "all",
  recallSearchText: "",
  recallSearchMode: "account", // "account" | "order"
  allRecallOrders: [],
  currentRevisadaOrder: null,
  
  init() {
    this.updateClock();
    setInterval(() => this.updateClock(), 1000);
    this.checkNetworkInfo();
    this.setupKeyboard();
  },

  setupKeyboard() {
    window.addEventListener('keydown', (e) => {
      const cancelPinModal = document.getElementById('modal-cancel-pin');
      if (cancelPinModal && cancelPinModal.classList.contains('active')) {
        if (e.key >= '0' && e.key <= '9') {
          this.cancelPinPress(e.key);
        } else if (e.key === 'Backspace') {
          this.cancelPinBackspace();
        } else if (e.key === 'Enter') {
          e.preventDefault();
          this.submitCancelPin();
        } else if (e.key === 'Escape') {
          this.closeCancelPinModal();
        }
        return;
      }

      const reasonModal = document.getElementById('modal-cancel-reason');
      if (reasonModal && reasonModal.classList.contains('active')) {
        if (e.key === 'Enter') {
          e.preventDefault();
          this.reasonFinish();
        } else if (e.key === 'Escape') {
          e.preventDefault();
          this.reasonCancel();
        }
        return;
      }

      const lossModal = document.getElementById('modal-cancel-loss');
      if (lossModal && lossModal.classList.contains('active')) {
        if (e.key === 'Escape') {
          e.preventDefault();
          this.cancelLossAbort();
        }
        return;
      }

      const qtyModal = document.getElementById('modal-quantity');
      if (qtyModal && qtyModal.classList.contains('active')) {
        if (e.key >= '0' && e.key <= '9') {
          this.qtyPress(e.key);
        } else if (e.key === 'Backspace') {
          this.qtyBackspace();
        } else if (e.key === 'Enter') {
          e.preventDefault();
          this.confirmQuantity();
        } else if (e.key === 'Escape') {
          this.qtyCancel();
        }
        return;
      }

      const pinScreen = document.getElementById('screen-pin');
      if (pinScreen && pinScreen.classList.contains('active')) {
        if (e.key >= '0' && e.key <= '9') {
          this.pinPress(e.key);
        } else if (e.key === 'Backspace') {
          this.pinBackspace();
        } else if (e.key === 'Enter') {
          this.submitPin();
        } else if (e.key === 'Escape') {
          this.pinClear();
        }
        return;
      }

      const recallScreen = document.getElementById('screen-recall');
      if (recallScreen && recallScreen.classList.contains('active')) {
        if (e.key >= '0' && e.key <= '9') {
          this.recallTypeDigit(e.key);
        } else if (e.key === 'Backspace') {
          this.recallBackspace();
        } else if (e.key === 'Enter') {
          this.recallSearchSubmit();
        } else if (e.key === 'Escape') {
          this.recallClearSearch();
        }
        return;
      }
    });
  },

  async checkNetworkInfo() {
    try {
      const res = await fetch('/api/info');
      const data = await res.json();
      const stationId = data.station_id || 16;
      this.activeStationId = stationId;
      const stEl = document.getElementById('status-network');
      if (stEl && data.local_ip) {
        stEl.textContent = `Station ${stationId} (${data.local_ip})`;
      }
      if (data.database_name) {
        const dbEl = document.getElementById('home-db-status');
        if (dbEl) dbEl.textContent = `Estación ${stationId} (${data.database_name.replace('.mdb', '')})`;
      }
      const orderStEl = document.getElementById('order-station-status');
      if (orderStEl) orderStEl.textContent = `Estación ${stationId}`;
      if (data.tax_rate) {
        this.taxRate = parseFloat(data.tax_rate);
        const lblTax = document.getElementById('lbl-tax-rate');
        if (lblTax) lblTax.textContent = `Impuesto (${this.taxRate}%):`;
      }
    } catch (e) {
      console.warn("Could not fetch server info", e);
    }
  },

  updateClock() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const fullDateStr = now.toLocaleDateString() + " " + timeStr;

    const elTicket = document.getElementById('ticket-time-now');
    if (elTicket) elTicket.textContent = timeStr;

    const elHome = document.getElementById('home-clock');
    if (elHome) elHome.textContent = fullDateStr;

    const elOrder = document.getElementById('order-clock');
    if (elOrder) elOrder.textContent = fullDateStr;
  },

  showScreen(screenId) {
    this.activeScreenId = screenId;
    if (screenId === 'screen-home') {
      // SIEMPRE que se regrese al inicio: solicitar código para ingresar a meseros y revisar
      this.currentWaiter = null;
      this.pendingTarget = null;
      this.enteredPin = "";
      this.selectedTable = null;
      this.currentOrderId = null;
      this.orderItems = [];
      const disp = document.getElementById('pin-display');
      if (disp) disp.textContent = "";
    }
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    const sc = document.getElementById(screenId);
    if (sc) sc.classList.add('active');
  },

  goHome() {
    this.showScreen('screen-home');
  },

  // --- NAVIGATION WITH PIN ROUTING ---
  startDineIn() {
    this.pendingTarget = "mesas";
    this.promptPin("Ingrese Código de Acceso (Mesas)");
  },

  startRecall() {
    this.pendingTarget = "revisar";
    this.promptPin("Ingrese Código de Acceso (Revisar Órdenes)");
  },

  startBackOffice() {
    this.pendingTarget = "backoffice";
    this.promptPin("Ingrese Código de Gerente (Oficina)");
  },

  promptPin(titleText) {
    this.enteredPin = "";
    this.updatePinDisplay();
    const titleEl = document.getElementById('pin-title-txt');
    if (titleEl) titleEl.textContent = titleText;
    const subEl = document.getElementById('pin-sub-header');
    if (subEl) subEl.textContent = titleText;
    this.showScreen('screen-pin');
  },

  // --- TOAST NOTIFICATION ---
  showToast(message, isError = false) {
    const el = document.getElementById('pos-toast');
    const msgEl = document.getElementById('toast-msg');
    const iconEl = document.getElementById('toast-icon');
    if (!el) return;

    msgEl.textContent = message;
    iconEl.textContent = isError ? '⚠️' : '✅';
    el.className = `pos-toast show ${isError ? 'error' : ''}`;

    if (this._toastTimer) clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => {
      el.classList.remove('show');
    }, 2200);
  },

  // --- PIN KEYPAD ACTIONS ---
  pinPress(digit) {
    if (this.enteredPin.length < 8) {
      this.enteredPin += digit;
      this.updatePinDisplay();
      this.tryAutoAuth();
    }
  },

  pinBackspace() {
    this.enteredPin = this.enteredPin.slice(0, -1);
    this.updatePinDisplay();
  },

  pinClear() {
    this.enteredPin = "";
    this.updatePinDisplay();
  },

  updatePinDisplay() {
    const el = document.getElementById('pin-display');
    if (el) {
      el.textContent = "•".repeat(this.enteredPin.length);
    }
  },

  async showWaitersHelp() {
    try {
      const res = await fetch('/api/auth/employees-summary');
      if (res.ok) {
        const emps = await res.json();
        const names = emps.map(e => `${e.first_name} (${e.is_manager ? 'Gerente' : 'Mesero'})`).join(' | ');
        this.showToast(`Personal en BD: ${names}`);
        return;
      }
    } catch (e) {}
    this.showToast("PIN 1: Administrador (Acceso Máximo / Oficina) | PIN 2: Ken");
  },

  async submitPin() {
    if (!this.enteredPin) {
      this.showToast("Ingrese PIN de acceso", true);
      return;
    }
    await this.tryAutoAuth(true);
  },

  async tryAutoAuth(isExplicitSubmit = false) {
    if (!this.enteredPin) return;

    try {
      const res = await fetch('/api/auth/pin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pin: this.enteredPin,
          action: this.pendingTarget || "mesas"
        })
      });

      if (res.ok) {
        const data = await res.json();
        this.currentWaiter = data.employee;
        const target = this.pendingTarget;
        this.enteredPin = "";
        this.updatePinDisplay();

        if (target === "backoffice") {
          this.showScreen('screen-backoffice');
          this.loadBackOfficePrinters();
        } else if (target === "revisar") {
          await this.openRecallScreen();
        } else {
          // Default: Mesas / Dine-In
          await this.loadTableGroups();
          await this.loadTables();
          this.showScreen('screen-tables');
        }
      } else {
        if (isExplicitSubmit) {
          const err = await res.json();
          this.showToast(err.detail || "Código de acceso incorrecto", true);
          this.pinClear();
        }
      }
    } catch (e) {
      if (isExplicitSubmit) {
        this.showToast("Error de conexión al validar código", true);
      }
    }
  },

  logout() {
    this.currentWaiter = null;
    this.enteredPin = "";
    this.updatePinDisplay();
    this.showScreen('screen-home');
  },

  // --- BACK OFFICE PRINTER CONFIGURATION (ALDELO OFICIAL) ---
  currentBoMainTab: 'receipt',
  selectedBoStation: null,

  switchBoMainTab(tabName) {
    this.currentBoMainTab = tabName;
    
    // Update tab pills
    const tabs = ['receipt', 'packer', 'kitchen-bar', 'label', 'report', 'other'];
    tabs.forEach(t => {
      const el = document.getElementById(`bo-tab-${t}`);
      if (el) {
        if (t === tabName) el.classList.add('active');
        else el.classList.remove('active');
      }
    });

    // Update panels
    const pReceipt = document.getElementById('bo-panel-receipt');
    const pKitchenBar = document.getElementById('bo-panel-kitchen-bar');
    const pPlaceholder = document.getElementById('bo-panel-placeholder');

    if (tabName === 'receipt') {
      if (pReceipt) pReceipt.style.display = 'block';
      if (pKitchenBar) pKitchenBar.style.display = 'none';
      if (pPlaceholder) pPlaceholder.style.display = 'none';
    } else if (tabName === 'kitchen-bar') {
      if (pReceipt) pReceipt.style.display = 'none';
      if (pKitchenBar) pKitchenBar.style.display = 'block';
      if (pPlaceholder) pPlaceholder.style.display = 'none';
    } else {
      if (pReceipt) pReceipt.style.display = 'none';
      if (pKitchenBar) pKitchenBar.style.display = 'none';
      if (pPlaceholder) {
        pPlaceholder.style.display = 'block';
        const titles = {
          'packer': 'Impresora del Empaquetador',
          'label': 'Impresora de Etiquetas',
          'report': 'Impresora de Reportes',
          'other': 'Otros Ajustes de Impresora'
        };
        const titleEl = document.getElementById('bo-placeholder-title');
        const descEl = document.getElementById('bo-placeholder-desc');
        if (titleEl) titleEl.textContent = titles[tabName] || 'Ajustes de Impresora';
        if (descEl) descEl.textContent = `Los parámetros para ${titles[tabName] || 'esta opción'} se configuran en la base de datos de Aldelo.`;
      }
    }

    // Update test button text
    const btnTest = document.getElementById('bo-btn-test-action');
    if (btnTest) {
      if (tabName === 'receipt') {
        btnTest.textContent = 'Fuente de Información / Probar Recibo';
      } else if (tabName === 'kitchen-bar') {
        btnTest.textContent = 'Fuente de Información / Probar Cocina';
      } else {
        btnTest.textContent = 'Fuente de Información';
      }
    }
  },

  changeBoStation(stationId) {
    this.selectedBoStation = parseInt(stationId);
    this.loadBackOfficePrinters(this.selectedBoStation);
  },

  async loadBackOfficePrinters(targetStationId = null) {
    try {
      const url = targetStationId ? `/api/backoffice/printers?station_id=${targetStationId}` : '/api/backoffice/printers';
      const res = await fetch(url);
      const data = await res.json();
      
      const current = data.current || {};
      const receipt = current.receipt || {};
      const kitchenList = current.kitchen || [];
      const bar = current.bar || {};
      const installed = data.installed_printers || [];
      const presets = data.presets || [];
      
      this.selectedBoStation = data.selected_station_id;

      // Update Back Office Title and active badge
      const titleHeader = document.getElementById('bo-title-header');
      if (titleHeader) {
        titleHeader.textContent = `Ajustes de Estación - Estación ${data.selected_station_id} (Aldelo Back Office)`;
      }
      const badge = document.getElementById('bo-station-badge');
      if (badge) {
        badge.style.display = (data.selected_station_id === data.active_station_id) ? 'inline-block' : 'none';
      }

      // Populate Station Dropdown
      const stSelect = document.getElementById('bo-select-station');
      if (stSelect && data.available_stations) {
        stSelect.innerHTML = "";
        data.available_stations.forEach(s => {
          const opt = document.createElement('option');
          opt.value = s;
          const isAct = (s === data.active_station_id);
          opt.textContent = isAct ? `Estación ${s} (PC Actual) ★` : `Estación ${s}`;
          if (s === data.selected_station_id) opt.selected = true;
          stSelect.appendChild(opt);
        });
      }

      // Populate printers dropdown helper
      const fillPrinters = (selId, currentVal) => {
        const sel = document.getElementById(selId);
        if (!sel) return;
        sel.innerHTML = '<option value="No Printer Attached">No Printer Attached</option>';
        installed.forEach(p => {
          const opt = document.createElement('option');
          opt.value = p;
          opt.textContent = p;
          if (p === currentVal) opt.selected = true;
          sel.appendChild(opt);
        });
      };

      // Populate presets dropdown helper
      const fillPresets = (selId, currentVal) => {
        const sel = document.getElementById(selId);
        if (!sel) return;
        sel.innerHTML = "";
        presets.forEach(pr => {
          const opt = document.createElement('option');
          opt.value = pr.id;
          opt.textContent = pr.name;
          if (String(pr.id) === String(currentVal)) opt.selected = true;
          sel.appendChild(opt);
        });
      };

      // Fill Receipt Printer (Aldelo Foto Oficial)
      fillPrinters('bo-receipt-printer', receipt.name || 'No Printer Attached');
      fillPresets('bo-receipt-type', receipt.type || '20021');

      // Fill all 6 kitchen stations
      for (let i = 1; i <= 6; i++) {
        const kData = kitchenList.find(k => k.id === i) || { title: "", name: "No Printer Attached", type: "20006" };
        const titleInput = document.getElementById(`bo-k${i}-title`);
        if (titleInput) {
          titleInput.value = kData.title || "";
        }
        fillPrinters(`bo-k${i}-printer`, kData.name);
        fillPresets(`bo-k${i}-type`, kData.type);
      }

      // Fill Bar
      const barTitleInput = document.getElementById('bo-bar-title');
      if (barTitleInput) barTitleInput.value = bar.title || "Bar";
      fillPrinters('bo-bar-printer', bar.name);
      fillPresets('bo-bar-type', bar.type);

    } catch (e) {
      this.showToast("Error cargando ajustes Back Office", true);
    }
  },

  switchBoTab(tabName) {
    document.getElementById('bo-panel-kitchen').style.display = (tabName === 'kitchen') ? 'block' : 'none';
    document.getElementById('bo-panel-bar').style.display = (tabName === 'bar') ? 'block' : 'none';

    document.getElementById('bo-subtab-kitchen').className = `bo-subtab-btn ${tabName === 'kitchen' ? 'active' : ''}`;
    document.getElementById('bo-subtab-bar').className = `bo-subtab-btn ${tabName === 'bar' ? 'active' : ''}`;
  },

  async saveBackOfficePrinters() {
    // 1. Receipt Printer
    const receiptEl = document.getElementById('bo-receipt-printer');
    const receiptTypeEl = document.getElementById('bo-receipt-type');
    const receipt_printer = {
      name: receiptEl ? receiptEl.value : "No Printer Attached",
      type: receiptTypeEl ? receiptTypeEl.value : "20021"
    };

    // 2. Kitchen Printers
    const kitchen_printers = [];
    for (let i = 1; i <= 6; i++) {
      const titleEl = document.getElementById(`bo-k${i}-title`);
      const printerEl = document.getElementById(`bo-k${i}-printer`);
      const typeEl = document.getElementById(`bo-k${i}-type`);
      kitchen_printers.push({
        id: i,
        title: titleEl ? titleEl.value.trim() : "",
        name: printerEl ? printerEl.value : "No Printer Attached",
        type: typeEl ? typeEl.value : "20006"
      });
    }

    // 3. Bar Printer
    const barTitleEl = document.getElementById('bo-bar-title');
    const barPrinterEl = document.getElementById('bo-bar-printer');
    const barTypeEl = document.getElementById('bo-bar-type');
    const bar_printer = {
      title: barTitleEl ? barTitleEl.value.trim() : "Bar",
      name: barPrinterEl ? barPrinterEl.value : "No Printer Attached",
      type: barTypeEl ? barTypeEl.value : "20006"
    };

    const payload = {
      station_id: this.selectedBoStation,
      receipt_printer,
      kitchen_printers,
      bar_printer
    };

    try {
      const res = await fetch('/api/backoffice/printers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        const resData = await res.json();
        this.showToast(`Impresoras guardadas en Aldelo (Estación ${resData.station_id || this.selectedBoStation})`);
      } else {
        this.showToast("Error al guardar impresoras", true);
      }
    } catch (e) {
      this.showToast("Error al guardar en Aldelo", true);
    }
  },

  async saveAndCloseBackOffice() {
    await this.saveBackOfficePrinters();
    this.goHome();
  },

  async testReceiptPrinter() {
    this.showToast("Enviando ticket de prueba a impresora de recibos...");
    try {
      const st = this.selectedBoStation ? `?station_id=${this.selectedBoStation}` : '';
      const res = await fetch(`/api/printers/test-receipt${st}`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        this.showToast(`✅ Recibo impreso: ${data.printer_name}`);
      } else {
        this.showToast(`Error recibo: ${data.message || data.error}`, true);
      }
    } catch (e) {
      this.showToast("Error al enviar prueba de recibo", true);
    }
  },

  async testBackOfficePrinter() {
    this.showToast("Enviando ticket de prueba a cocina...");
    try {
      const res = await fetch('/api/printers/test', { method: 'POST' });
      const data = await res.json();
      const k = data.results?.kitchen || 'N/A';
      this.showToast(`Prueba Cocina: ${k}`);
    } catch (e) {
      this.showToast("Error al probar impresora", true);
    }
  },

  async testBackOfficeCurrent() {
    if (this.currentBoMainTab === 'receipt') {
      await this.testReceiptPrinter();
    } else if (this.currentBoMainTab === 'kitchen-bar') {
      await this.testBackOfficePrinter();
    } else {
      this.showToast("Pestaña informativa de Aldelo");
    }
  },

  // --- RECALL ORDERS SCREEN (CLON EXACTO ALDELO POS) ---
  async openRecallScreen() {
    this.recallSearchText = "";
    this.recallFilter = "all";
    const txtBox = document.getElementById('recall-search-txt');
    if (txtBox) txtBox.textContent = "";
    
    const modeBtn = document.getElementById('btn-recall-search-mode');
    if (modeBtn) {
      if (this.recallSearchMode === 'account') {
        modeBtn.textContent = 'Por número de cuenta';
        modeBtn.style.color = '#80d8ff';
        modeBtn.style.borderColor = '#0070ba';
      } else {
        modeBtn.textContent = 'Por #Orden';
        modeBtn.style.color = '#ffd54f';
        modeBtn.style.borderColor = '#ffb300';
      }
    }

    document.querySelectorAll('.recall-tab-btn').forEach(b => b.classList.remove('active'));
    const allTab = document.querySelector('.recall-tab-btn[data-filter="all"]');
    if (allTab) allTab.classList.add('active');

    await this.loadRecallOrders();
    this.showScreen('screen-recall');
  },

  closeRecallScreen() {
    if (this.selectedTable) {
      this.showScreen('screen-tables');
    } else {
      this.showScreen('screen-home');
    }
  },

  toggleRecallSearchMode() {
    const btn = document.getElementById('btn-recall-search-mode');
    if (this.recallSearchMode === 'account') {
      this.recallSearchMode = 'order';
      if (btn) {
        btn.textContent = 'Por #Orden';
        btn.style.color = '#ffd54f';
        btn.style.borderColor = '#ffb300';
      }
    } else {
      this.recallSearchMode = 'account';
      if (btn) {
        btn.textContent = 'Por número de cuenta';
        btn.style.color = '#80d8ff';
        btn.style.borderColor = '#0070ba';
      }
    }
    if (!this.recallSearchText) {
      this.loadRecallOrders();
    }
  },

  scrollRecallDown() {
    const grid = document.getElementById('recall-cards-grid');
    if (grid) {
      grid.scrollBy({ top: 180, behavior: 'smooth' });
    }
  },

  async printOrderCheck(orderId) {
    try {
      this.showToast(`Imprimiendo cuenta #${orderId}...`);
      const res = await fetch(`/api/orders/${orderId}/print-check`, { method: 'POST' });
      if (!res.ok) throw new Error("Error al imprimir cuenta");
      this.showToast(`Cuenta #${orderId} enviada a impresora`);
    } catch (e) {
      this.showToast(e.message, true);
    }
  },

  filterMyOrders() {
    if (!this.currentWaiter) {
      this.showToast("No hay mesero seleccionado", true);
      return;
    }
    const myName = (this.currentWaiter.name || this.currentWaiter.first_name || "").toLowerCase();
    const filtered = this.allRecallOrders.filter(o => o.waiter.toLowerCase().includes(myName));
    this.renderFilteredCards(filtered, `Mis ordenes (${this.currentWaiter.name || 'Oscar'})`);
  },

  async loadRecallOrders() {
    try {
      let url = `/api/recall-orders?type_filter=${this.recallFilter}&search_mode=${this.recallSearchMode}`;
      if (this.recallSearchText) {
        url += `&search=${encodeURIComponent(this.recallSearchText)}`;
      }
      const res = await fetch(url);
      this.allRecallOrders = await res.json();
      this.renderRecallOrders();
    } catch (e) {
      this.showToast("Error cargando órdenes", true);
    }
  },

  filterRecallType(typeId, btnEl) {
    this.recallFilter = typeId;
    document.querySelectorAll('.recall-tab-btn').forEach(b => b.classList.remove('active'));
    if (btnEl) {
      btnEl.classList.add('active');
    } else {
      const target = document.querySelector(`.recall-tab-btn[data-filter="${typeId}"]`);
      if (target) target.classList.add('active');
    }
    this.loadRecallOrders();
  },

  renderRecallOrders() {
    const banner = document.getElementById('recall-orders-banner');
    if (banner) {
      if (this.recallSearchText) {
        const modeLabel = (this.recallSearchMode === 'order') ? 'Por #Orden' : 'Por Cuenta/Mesa';
        banner.textContent = `Búsqueda: "${this.recallSearchText}" (${modeLabel})`;
      } else {
        const titles = {
          'all': 'Ordenes abiertas',
          '1': 'Mesas abiertas',
          '2': 'Bar - Ordenes abiertas',
          '3': 'Para Llevar - Ordenes abiertas',
          '4': 'Drive-In - Ordenes abiertas',
          '5': 'Domicilio - Ordenes abiertas'
        };
        banner.textContent = titles[this.recallFilter] || 'Ordenes abiertas';
      }
    }
    this.renderFilteredCards(this.allRecallOrders);
  },

  renderFilteredCards(ordersList, bannerOverride) {
    const grid = document.getElementById('recall-cards-grid');
    if (!grid) return;
    grid.innerHTML = "";

    if (bannerOverride) {
      const banner = document.getElementById('recall-orders-banner');
      if (banner) banner.textContent = bannerOverride;
    }

    const countNum = document.getElementById('recall-count-num');
    if (countNum) {
      countNum.textContent = ordersList.length;
    }

    if (ordersList.length === 0) {
      const msg = this.recallSearchText 
        ? `No se encontraron órdenes con la búsqueda "${this.recallSearchText}".` 
        : `No se encontraron órdenes abiertas.`;
      grid.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; color: #888; padding: 40px; font-size: 15px;">${msg}</div>`;
      return;
    }

    ordersList.forEach(ord => {
      const card = document.createElement('div');
      card.className = 'recall-order-card';
      if (ord.is_paid) {
        card.style.borderColor = '#00c853';
      }
      const acctNum = ord.account_number || 1;
      const formattedAmt = ord.amount.toFixed(2).replace('.', ',');
      const paidBadge = ord.is_paid 
        ? `<span style="background: rgba(0,230,118,0.2); color: #00e676; border: 1px solid #00e676; border-radius: 4px; padding: 1px 5px; font-size: 10px; font-weight: bold; margin-left: 4px;">PAGADA</span>` 
        : '';
      card.innerHTML = `
        <div class="recall-card-info-wrap">
          <div class="recall-card-row-top">
            <span style="font-size: 15px; font-weight: 900;"><strong style="color: #ffffff;">O#${ord.order_id}</strong> ${paidBadge}</span>
            <span style="font-size: 13px; font-weight: 700; opacity: 0.95;">${ord.order_type}${ord.table ? ' • ' + ord.table : ''}</span>
            <span style="color: #ffffff; font-weight: 900; font-size: 15px;">T#${acctNum}</span>
          </div>
          <div class="recall-card-row-mid">${ord.elapsed}</div>
          <div class="recall-card-row-bot">
            <span style="max-width: 130px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${ord.waiter}</span>
            <span style="color: #ffffff; font-weight: 900; font-size: 14.5px;">$${formattedAmt}</span>
            <span style="font-size: 11.5px; opacity: 0.9;">${ord.time}</span>
          </div>
        </div>
        <button class="recall-card-print-btn" onclick="event.stopPropagation(); app.printOrderCheck(${ord.order_id})" title="Imprimir cuenta">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#00e5ff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="6 9 6 2 18 2 18 9"></polyline>
            <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path>
            <rect x="6" y="14" width="12" height="8"></rect>
          </svg>
        </button>
      `;
      card.onclick = () => this.openOrderRevisada(ord.order_id);
      grid.appendChild(card);
    });
  },

  async openOrderRevisada(orderId) {
    try {
      const res = await fetch(`/api/orders/${orderId}`);
      if (!res.ok) throw new Error("No se pudo cargar la orden");
      const order = await res.json();
      this.currentRevisadaOrder = order;

      // Actualizar cabecera del ticket
      const srvName = order.waiter_name || (this.currentWaiter ? this.currentWaiter.name : "Oscar");
      document.getElementById('rev-waiter-name').textContent = `Mesero: ${srvName}`;
      
      const acctNum = order.account_number || 1;
      const statusSuffix = order.is_paid ? ' (PAGADA)' : (order.status_code === '3' ? ' (ANULADA)' : '');
      const orderIdEl = document.getElementById('rev-order-id-txt');
      if (orderIdEl) {
        orderIdEl.textContent = `# de Orden: ${order.order_id}${statusSuffix}`;
        orderIdEl.style.color = order.is_paid ? '#00e676' : '';
      }
      document.getElementById('rev-order-type-txt').textContent = order.order_type || "Mesas";
      document.getElementById('rev-table-name-txt').textContent = `Mesa: ${order.table_text || order.table_id}`;
      document.getElementById('rev-guests-txt').textContent = `Personas: ${order.guests || 1}`;

      // Renderizar platos del ticket
      const listEl = document.getElementById('rev-ticket-items-list');
      listEl.innerHTML = "";
      if (!order.items || order.items.length === 0) {
        listEl.innerHTML = `<div style="text-align: center; color: #888; padding: 20px;">Sin platos registrados</div>`;
      } else {
        order.items.forEach(it => {
          const itemRow = document.createElement('div');
          itemRow.className = 'rev-item-line';
          const itemPrice = (it.unit_price * it.quantity).toFixed(2).replace('.', ',');
          itemRow.innerHTML = `
            <span>${it.quantity} *${it.name}</span>
            <span>${itemPrice}</span>
          `;
          listEl.appendChild(itemRow);

          if (it.modifiers && it.modifiers.length > 0) {
            it.modifiers.forEach(m => {
              const modRow = document.createElement('div');
              modRow.className = 'rev-mod-line';
              modRow.textContent = m.name || m;
              listEl.appendChild(modRow);
            });
          }
        });
      }

      // Pie de ticket idéntico a Aldelo Foto usuario: >> # de cuenta:   X <<
      const accSuffix = order.is_paid ? ' (PAGADA)' : '';
      document.getElementById('rev-account-num-txt').textContent = `>> # de cuenta:   ${acctNum}${accSuffix} <<`;
      document.getElementById('rev-datetime-txt').textContent = order.order_datetime || "";

      // Totales
      const sub = (order.subtotal || 0).toFixed(2).replace('.', ',');
      const tx = (order.tax || 0).toFixed(2).replace('.', ',');
      const tot = (order.total || 0).toFixed(2).replace('.', ',');
      document.getElementById('rev-subtotal-val').textContent = sub;
      document.getElementById('rev-tax-val').textContent = tx;
      document.getElementById('rev-total-due-val').textContent = `$${tot}`;

      this.showScreen('screen-order-revisada');
    } catch (e) {
      this.showToast(e.message, true);
    }
  },

  editOrderFromRevisada() {
    if (this.currentRevisadaOrder) {
      if (this.currentRevisadaOrder.is_paid || this.currentRevisadaOrder.status_code === '2') {
        this.showToast("Esta orden ya fue pagada y está cerrada", true);
        return;
      }
      this.openExistingOrder(this.currentRevisadaOrder.order_id);
    }
  },

  async printCurrentOrderFromRevisada() {
    if (!this.currentRevisadaOrder) return;
    await this.printOrderCheck(this.currentRevisadaOrder.order_id);
  },

  rushCurrentOrder() {
    if (!this.currentRevisadaOrder) return;
    if (this.currentRevisadaOrder.is_paid || this.currentRevisadaOrder.status_code === '2') {
      this.showToast("Esta orden ya está pagada y finalizada", true);
      return;
    }
    this.showToast(`Orden #${this.currentRevisadaOrder.order_id} marcada como Apresurada (RUSH)`);
  },

  scrollRevTicket(delta) {
    const listEl = document.getElementById('rev-ticket-items-list');
    if (listEl) {
      listEl.scrollBy({ top: delta, behavior: 'smooth' });
    }
  },

  recallTypeDigit(digit) {
    if (this.recallSearchText.length < 10) {
      this.recallSearchText += digit;
      const txt = document.getElementById('recall-search-txt');
      if (txt) txt.textContent = this.recallSearchText;
      // No realizar búsqueda automática mientras escribe, solo al presionar 'Buscar'
    }
  },

  recallBackspace() {
    if (this.recallSearchText.length > 0) {
      this.recallSearchText = this.recallSearchText.slice(0, -1);
      const txt = document.getElementById('recall-search-txt');
      if (txt) txt.textContent = this.recallSearchText;
    }
  },

  recallClearSearch() {
    this.recallSearchText = "";
    const txt = document.getElementById('recall-search-txt');
    if (txt) txt.textContent = "";
    this.loadRecallOrders();
  },

  async recallSearchSubmit() {
    if (!this.recallSearchText) {
      await this.loadRecallOrders();
      return;
    }

    try {
      let url = `/api/recall-orders?type_filter=${this.recallFilter}&search_mode=${this.recallSearchMode}&search=${encodeURIComponent(this.recallSearchText)}`;
      const res = await fetch(url);
      const orders = await res.json();
      this.allRecallOrders = orders;
      this.renderRecallOrders();

      if (orders.length === 0) {
        this.showToast(`No se encontró la orden #${this.recallSearchText}`, true);
        return;
      }

      // Si hay coincidencia exacta con el número de orden o si solo hay 1 resultado, abrir directamente la orden
      const exactMatch = orders.find(o => String(o.order_id) === String(this.recallSearchText).trim());
      if (exactMatch) {
        await this.openOrderRevisada(exactMatch.order_id);
      } else if (orders.length === 1) {
        await this.openOrderRevisada(orders[0].order_id);
      }
    } catch (e) {
      this.showToast("Error al buscar orden", true);
    }
  },

  async openExistingOrder(orderId) {
    try {
      const res = await fetch(`/api/orders/${orderId}`);
      if (!res.ok) throw new Error("No se pudo cargar la orden");
      const order = await res.json();

      this.currentOrderId = orderId;
      this.currentAccountNumber = order.account_number || 1;
      if (order.tax_rate) this.taxRate = parseFloat(order.tax_rate);
      this.selectedTicketItemIndex = -1;

      if (!this.currentWaiter) {
        this.currentWaiter = { id: order.waiter_id, name: order.waiter_name, first_name: order.waiter_name };
      }

      this.selectedTable = { id: order.table_id, number: order.table_text || order.table_id, is_occupied: true };
      this.guestCount = order.guests || 1;
      this.orderItems = (order.items || []).map(it => ({ ...it, is_existing: true }));

      // Update header elements matching Aldelo Foto 2
      const acctNum = order.account_number || 1;
      const srvEl = document.getElementById('ticket-server-title');
      if (srvEl) srvEl.textContent = `Mesero: ${order.waiter_name}`;
      const ordEl = document.getElementById('ticket-order-num-title');
      if (ordEl) ordEl.textContent = `# de Orden: ${orderId}`;
      const tblEl = document.getElementById('ticket-table-title');
      if (tblEl) tblEl.textContent = `Mesa: ${this.selectedTable.number}`;
      const gstEl = document.getElementById('ticket-guests-title');
      if (gstEl) gstEl.textContent = `Personas: ${this.guestCount}`;
      const timeEl = document.getElementById('ticket-time-now');
      if (timeEl) timeEl.textContent = order.order_datetime || '';

      document.getElementById('order-screen-table-status').textContent = `Mesa ${this.selectedTable.number} (Cuenta #${acctNum} • Orden #${orderId})`;

      this.updateTicket();
      await this.loadMenuGroups();
      await this.loadMenuItems(this.activeMenuGroupId);
      this.showScreen('screen-order');
    } catch (e) {
      this.showToast(e.message, true);
    }
  },

  // --- TABLES SELECTION ---
  async loadTableGroups() {
    const res = await fetch('/api/table-groups');
    this.tableGroups = await res.json();
    const container = document.getElementById('room-tabs-container');
    container.innerHTML = "";
    this.tableGroups.forEach(g => {
      const btn = document.createElement('button');
      btn.className = `room-tab-btn ${g.id === this.activeGroupId ? 'active' : ''}`;
      btn.textContent = g.name;
      btn.onclick = () => {
        this.activeGroupId = g.id;
        document.querySelectorAll('.room-tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this.renderTables();
      };
      container.appendChild(btn);
    });
  },

  async loadTables() {
    const res = await fetch('/api/tables');
    this.allTables = await res.json();
    this.renderTables();
  },

  renderTables() {
    const canvas = document.getElementById('tables-canvas');
    canvas.innerHTML = "";

    const filtered = this.allTables.filter(t => t.group_id === this.activeGroupId);

    filtered.forEach(t => {
      const box = document.createElement('div');
      box.className = `table-box ${t.is_occupied ? 'occupied' : ''}`;
      
      if (t.grid_row !== undefined && t.grid_col !== undefined) {
        box.style.gridColumnStart = t.grid_col + 1;
        box.style.gridRowStart = t.grid_row + 1;
      }

      const totalStr = (t.active_order && t.active_order.total) ? '$' + t.active_order.total.toFixed(2) : '$0.00';
      const orderCountBadge = (t.order_count && t.order_count > 1) ? ` (${t.order_count})` : '';

      box.innerHTML = `
        <div class="table-number">${t.number}</div>
        <div class="table-meta">${t.is_occupied ? totalStr + orderCountBadge : 'Libre'}</div>
      `;

      box.onclick = () => this.onSelectTable(t);
      canvas.appendChild(box);
    });
  },

  onSelectTable(table) {
    this.selectedTable = table;
    if (table.is_occupied) {
      this.openTableChecks(table.id);
    } else {
      this.guestCount = 4;
      document.getElementById('guests-display').textContent = this.guestCount;
      this.showScreen('screen-guests');
    }
  },

  // --- CHEQUES DE MESA (FOTO 1) ---
  async openTableChecks(tableId) {
    try {
      const res = await fetch(`/api/tables/${tableId}/checks`);
      if (!res.ok) throw new Error("No se pudieron cargar los cheques de la mesa");
      const data = await res.json();
      this.tableChecksData = data;
      this.selectedCheckIndex = 0;

      const titleEl = document.getElementById('checks-table-label');
      if (titleEl) titleEl.textContent = `Mesa ${data.table_number}`;

      this.renderTableChecks();
      this.showScreen('screen-table-checks');
    } catch (e) {
      this.showToast(e.message, true);
    }
  },

  renderTableChecks() {
    const container = document.getElementById('checks-cards-container');
    if (!container) return;
    container.innerHTML = "";

    const checks = (this.tableChecksData && this.tableChecksData.checks) ? this.tableChecksData.checks : [];
    if (checks.length === 0) {
      container.innerHTML = `
        <div style="color: #fff; font-size: 20px; margin: auto; text-align: center;">
          No hay órdenes activas en esta mesa
          <div style="margin-top: 18px;">
            <button class="chk-action-btn" onclick="app.newCheckOnTable()" style="background: #00c853; padding: 12px 24px; font-size: 16px; border-radius: 8px;">
              Crear Nueva Orden
            </button>
          </div>
        </div>`;
      return;
    }

    checks.forEach((chk, idx) => {
      const isSelected = (idx === this.selectedCheckIndex);
      const card = document.createElement('div');
      card.className = `chk-card ${isSelected ? 'active' : ''}`;
      card.onclick = () => this.selectCheck(idx);
      card.ondblclick = () => this.editSelectedCheck();

      const itemsHtml = (chk.items || []).map(it => {
        const isCanc = (it.cancelled === true);
        const qty = parseInt(it.quantity) || 1;
        const name = it.name || "Plato";
        const unitP = parseFloat(it.unit_price) || 0.0;
        const price = (unitP * qty).toFixed(2).replace('.', ',');
        return `
          <div class="chk-receipt-line" style="${isCanc ? 'color: red; text-decoration: line-through;' : ''}">
            <span>${qty} *${name}</span>
            <span>${isCanc ? '0,00' : price}</span>
          </div>
          ${(it.modifiers || []).map(m => `
            <div class="chk-receipt-mod">
              ${m.name} 0,00Cada uno
            </div>
          `).join('')}
        `;
      }).join('');

      const subtotalVal = (parseFloat(chk.subtotal) || 0.0).toFixed(2).replace('.', ',');
      const taxVal = (parseFloat(chk.tax) || 0.0).toFixed(2).replace('.', ',');
      const totalVal = (parseFloat(chk.total) || 0.0).toFixed(2).replace('.', ',');
      const acctNum = chk.account_number || chk.check_index || (idx + 1);
      const totalChecks = chk.total_accounts || chk.total_checks || checks.length;

      card.innerHTML = `
        <div class="chk-card-header"># de Cheque: ${acctNum}/${totalChecks}</div>
        <div class="chk-receipt-body" id="chk-receipt-body-${idx}">
          <div class="chk-receipt-header-meta">
            <div class="chk-meta-row">
              <span>Mesero: ${chk.waiter_name || 'Oscar'}</span>
              <span>Estación: 16</span>
            </div>
            <div style="border-bottom: 1px dashed #000; margin: 4px 0;"></div>
            <div class="chk-meta-row">
              <span style="font-weight: 900; color: #000;"># de Orden: ${chk.order_id}</span>
              <span>Mesas</span>
            </div>
            <div class="chk-meta-row">
              <span>Mesa: ${chk.table_text || (this.tableChecksData ? this.tableChecksData.table_number : '')}</span>
              <span>Personas: ${chk.guests || 1}</span>
            </div>
          </div>

          <div class="chk-receipt-items">
            ${itemsHtml}
          </div>

          <div class="chk-receipt-footer-meta">
            <div style="font-weight: 900; font-size: 14px;">&gt;&gt; # de cuenta:   ${acctNum} &lt;&lt;</div>
            <div style="margin-top: 3px; font-weight: normal;">${chk.order_datetime || ''}</div>
          </div>

          <div class="chk-scroll-nav">
            <button class="chk-scroll-btn" onclick="event.stopPropagation(); app.scrollCheckReceipt(${idx}, -70)">▲</button>
            <button class="chk-scroll-btn" onclick="event.stopPropagation(); app.scrollCheckReceipt(${idx}, 70)">▼</button>
          </div>
        </div>

        <div class="chk-card-totals">
          <div class="chk-tot-col">
            <span class="chk-tot-label">Subtotal</span>
            <span class="chk-tot-val">${subtotalVal}</span>
          </div>
          <div class="chk-tot-col">
            <span class="chk-tot-label">Impuesto</span>
            <span class="chk-tot-val">${taxVal}</span>
          </div>
          <div class="chk-tot-col" style="align-items: flex-end;">
            <span class="chk-tot-label" style="color: #ff5252;">Total debido</span>
            <span class="chk-tot-val due">$${totalVal}</span>
          </div>
        </div>
      `;

      container.appendChild(card);
    });
  },

  selectCheck(index) {
    this.selectedCheckIndex = index;
    const cards = document.querySelectorAll('.chk-card');
    cards.forEach((c, idx) => {
      if (idx === index) {
        c.classList.add('active');
        c.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
      } else {
        c.classList.remove('active');
      }
    });
  },

  editSelectedCheck() {
    if (!this.tableChecksData || !this.tableChecksData.checks || !this.tableChecksData.checks[this.selectedCheckIndex]) {
      this.showToast("Seleccione un cheque primero", true);
      return;
    }
    const chk = this.tableChecksData.checks[this.selectedCheckIndex];
    this.openExistingOrder(chk.order_id);
  },

  newCheckOnTable() {
    if (!this.selectedTable) return;
    this.currentOrderId = null;
    this.orderItems = [];
    this.guestCount = 1;
    this.selectedTicketItemIndex = -1;
    this.openOrderScreen();
  },

  async printSelectedCheck() {
    if (!this.tableChecksData || !this.tableChecksData.checks || !this.tableChecksData.checks[this.selectedCheckIndex]) {
      this.showToast("Seleccione un cheque para imprimir", true);
      return;
    }
    const chk = this.tableChecksData.checks[this.selectedCheckIndex];
    this.showToast(`🖨️ Imprimiendo Cheque #${chk.check_label} (Orden #${chk.order_id})...`);
    try {
      const res = await fetch(`/api/orders/${chk.order_id}/print-check`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        this.showToast(`✅ Cheque #${chk.order_id} impreso con éxito`);
      } else {
        this.showToast(`⚠️ No se pudo enviar a impresora`);
      }
    } catch (e) {
      this.showToast(`Error de impresión: ${e.message}`, true);
    }
  },

  async printAllChecksOnTable() {
    if (!this.selectedTable) return;
    this.showToast(`🖨️ Imprimiendo todos los cheques de la Mesa ${this.selectedTable.number}...`);
    try {
      const res = await fetch(`/api/tables/${this.selectedTable.id}/print-all-checks`, { method: 'POST' });
      const data = await res.json();
      this.showToast(`✅ Se imprimieron ${data.count || 0} cheques de la Mesa`);
    } catch (e) {
      this.showToast(`Error de impresión: ${e.message}`, true);
    }
  },

  scrollCheckReceipt(index, delta) {
    const el = document.getElementById(`chk-receipt-body-${index}`);
    if (el) el.scrollTop += delta;
  },

  scrollTicket(delta) {
    const el = document.getElementById('ticket-items-list');
    if (el) el.scrollTop += delta;
  },

  // --- GUEST COUNT ---
  guestPress(digit) {
    let str = document.getElementById('guests-display').textContent;
    if (str.length < 2) {
      str = (str === "0" || str === "4" ? "" : str) + digit;
      document.getElementById('guests-display').textContent = str;
    }
  },

  guestClear() {
    document.getElementById('guests-display').textContent = "1";
  },

  confirmGuests() {
    const val = parseInt(document.getElementById('guests-display').textContent) || 1;
    this.guestCount = val;
    this.openOrderScreen();
  },

  // --- ORDER ENTRY & MENU ---
  async openOrderScreen() {
    this.orderItems = [];
    this.currentOrderId = null;
    this.selectedTicketItemIndex = -1;
    this.setPendingQuantity(1);

    const srvName = this.currentWaiter ? this.currentWaiter.name : "Oscar";
    const srvEl = document.getElementById('ticket-server-title');
    if (srvEl) srvEl.textContent = `Mesero: ${srvName}`;
    const ordEl = document.getElementById('ticket-order-num-title');
    if (ordEl) ordEl.textContent = `# de Orden: (Nueva)`;
    const tblEl = document.getElementById('ticket-table-title');
    if (tblEl) tblEl.textContent = `Mesa: ${this.selectedTable.number}`;
    const gstEl = document.getElementById('ticket-guests-title');
    if (gstEl) gstEl.textContent = `Personas: ${this.guestCount}`;
    const timeEl = document.getElementById('ticket-time-now');
    if (timeEl) {
      const now = new Date();
      timeEl.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    this.updateTicket();
    document.getElementById('order-screen-table-status').textContent = `Mesa ${this.selectedTable.number}`;

    await this.loadMenuGroups();
    await this.loadMenuItems(this.activeMenuGroupId);
    this.showScreen('screen-order');
  },

  async loadMenuGroups() {
    try {
      const res = await fetch('/api/menu/groups');
      this.menuGroups = await res.json();
    } catch (e) {
      console.warn("Could not load menu groups", e);
    }
    const panel = document.getElementById('categories-panel');
    if (!panel) return;
    panel.innerHTML = "";

    const isPhoneMode = window.innerWidth < 550;

    // Asegurar que haya un grupo activo válido
    if (!this.activeMenuGroupId || !this.menuGroups.some(g => g.id === this.activeMenuGroupId)) {
      if (this.menuGroups.length > 0) {
        this.activeMenuGroupId = this.menuGroups[0].id;
      }
    }

    this.menuGroups.forEach((g, idx) => {
      const btn = document.createElement('button');
      const isActive = (g.id === this.activeMenuGroupId);
      btn.className = `cat-btn ${isActive ? 'active' : ''}`;
      
      // Cuadrícula exacta de Aldelo: 2 columnas
      // Col 1: idx par (0, 2, 4...)
      // Col 2: idx impar (1, 3, 5...)
      // Fila: Math.floor(idx / 2) + 1
      if (!isPhoneMode) {
        const catRow = Math.floor(idx / 2) + 1;
        const catCol = (idx % 2 === 0) ? 1 : 2;
        btn.style.gridRowStart = catRow;
        btn.style.gridColumnStart = catCol;
      } else {
        btn.style.gridRowStart = 'auto';
        btn.style.gridColumnStart = 'auto';
      }

      // Color oficial de Aldelo:
      // Todas las categorías estándar son Azul Oficial (#0080ff).
      // Solo promociones o domicilios usan colores específicos (Rojo #ff0000, Rosa #ff8080).
      let catColor = '#0080ff';
      if (g.color && g.color.toLowerCase() !== '#fde1aa' && g.color !== 'transparent') {
        catColor = g.color;
      }
      btn.dataset.color = catColor;
      if (!isActive) {
        btn.style.backgroundColor = catColor;
      }
  
      btn.innerHTML = `
        ${g.image ? `<img src="${g.image}" alt="${g.name}" onerror="this.style.display='none'">` : '🍽️'}
        <span>${g.name}</span>
      `;
      btn.onclick = () => {
        this.activeMenuGroupId = g.id;
        document.querySelectorAll('.cat-btn').forEach(b => {
          b.classList.remove('active');
          b.style.backgroundColor = b.dataset.color || '#0080ff';
        });
        btn.classList.add('active');
        btn.style.backgroundColor = ''; // Aplica el verde brillante oficial .cat-btn.active
        this.loadMenuItems(g.id);
      };
      panel.appendChild(btn);
    });

    // Botón de navegación / scroll hacia abajo en Aldelo si hay más de 18 categorías
    if (!isPhoneMode && this.menuGroups.length > 18) {
      const navBtn = document.createElement('button');
      navBtn.className = 'cat-nav-btn';
      navBtn.innerHTML = '▼';
      navBtn.title = 'Ver más categorías';
      navBtn.style.gridColumn = '1 / span 2';
      navBtn.style.gridRowStart = Math.ceil(this.menuGroups.length / 2) + 1;
      navBtn.style.height = '34px';
      navBtn.style.background = '#1a2738';
      navBtn.style.color = '#ffffff';
      navBtn.style.border = '1px solid #334e68';
      navBtn.style.borderRadius = '4px';
      navBtn.style.fontSize = '14px';
      navBtn.style.fontWeight = 'bold';
      navBtn.style.cursor = 'pointer';
      navBtn.onclick = () => {
        if (panel.scrollTop + panel.clientHeight >= panel.scrollHeight - 10) {
          panel.scrollTo({ top: 0, behavior: 'smooth' });
          navBtn.innerHTML = '▼';
        } else {
          panel.scrollBy({ top: 180, behavior: 'smooth' });
          setTimeout(() => {
            if (panel.scrollTop + panel.clientHeight >= panel.scrollHeight - 10) {
              navBtn.innerHTML = '▲';
            }
          }, 200);
        }
      };
      panel.appendChild(navBtn);
    }
  },

  async loadMenuItems(groupId) {
    this.activeMenuGroupId = groupId;
    const res = await fetch(`/api/menu/items?group_id=${groupId}`);
    this.currentMenuItems = await res.json();
    const panel = document.getElementById('products-panel');
    panel.innerHTML = "";

    const isPhoneMode = (window.innerWidth < 550);

    if (isPhoneMode) {
      // MODO CELULAR ESTRECHO (< 550px): Flujo adaptativo
      panel.className = 'products-panel portrait-flow';

      this.currentMenuItems.forEach(item => {
        const card = document.createElement('div');
        card.className = 'product-card';
        if (item.button_color && item.button_color !== '#e7e7d4' && item.button_color !== '#ffffff') {
          card.style.backgroundColor = item.button_color;
          const r = parseInt(item.button_color.slice(1, 3), 16) || 0;
          const g = parseInt(item.button_color.slice(3, 5), 16) || 0;
          const b = parseInt(item.button_color.slice(5, 7), 16) || 0;
          const lum = (0.299 * r + 0.587 * g + 0.114 * b);
          const txtColor = (lum < 125) ? '#ffffff' : '#000000';
          card.style.color = txtColor;
        }
        card.innerHTML = `
          ${item.image ? `<img src="${item.image}" alt="${item.name}" onerror="this.style.display='none'">` : ''}
          <div class="product-name">${item.name}</div>
        `;
        if (card.style.color) {
          const pName = card.querySelector('.product-name');
          if (pName) pName.style.color = card.style.color;
        }
        card.onclick = () => this.addItemToOrder(item);
        panel.appendChild(card);
      });
    } else {
      // TABLETS (VERTICAL Y HORIZONTAL) Y COMPUTADORAS:
      // Cuadrícula exacta de 4 columnas oficiales de Aldelo POS para preservar la memoria muscular
      panel.className = 'products-panel pos-fixed-grid';

      this.currentMenuItems.forEach(item => {
        const card = document.createElement('div');
        card.className = 'product-card';

        // 1-based indexing para CSS grid
        if (item.grid_row !== undefined && item.grid_row >= 0 && item.grid_col !== undefined && item.grid_col >= 0) {
          card.style.gridRowStart = item.grid_row + 1;
          card.style.gridColumnStart = item.grid_col + 1;
        }

        // Color de botón exacto de la base de datos de Aldelo
        if (item.button_color && item.button_color !== '#e7e7d4' && item.button_color !== '#ffffff') {
          card.style.backgroundColor = item.button_color;
          const r = parseInt(item.button_color.slice(1, 3), 16) || 0;
          const g = parseInt(item.button_color.slice(3, 5), 16) || 0;
          const b = parseInt(item.button_color.slice(5, 7), 16) || 0;
          const lum = (0.299 * r + 0.587 * g + 0.114 * b);
          const txtColor = (lum < 125) ? '#ffffff' : '#000000';
          card.style.color = txtColor;
        }

        card.innerHTML = `
          ${item.image ? `<img src="${item.image}" alt="${item.name}" onerror="this.style.display='none'">` : ''}
          <div class="product-name">${item.name}</div>
        `;
        if (card.style.color) {
          const pName = card.querySelector('.product-name');
          if (pName) pName.style.color = card.style.color;
        }

        card.onclick = () => this.addItemToOrder(item);
        panel.appendChild(card);
      });
    }
  },

  async addItemToOrder(item) {
    // Si el plato tiene opciones de tamaño / porciones (ej. Todays Soup -> Cup vs Bowl)
    if (item.has_choices) {
      try {
        const res = await fetch(`/api/menu/items/${item.id}/choices`);
        const choices = await res.json();
        if (choices && choices.length > 0) {
          const step = {
            title: `Seleccione Opción para ${item.name}`,
            options: choices.map(c => ({
              id: c.id,
              name: `${c.choice_text} ($${c.price.toFixed(2)})`,
              cost: 0,
              choice_item: c
            }))
          };
          this.modifierSteps = [step];
          this.currentModStepIndex = 0;
          this.pendingItem = null;
          this.openChoiceStep();
          return;
        }
      } catch (e) {
        console.error("Error fetching choices", e);
      }
    }

    if (item.has_modifiers) {
      try {
        const res = await fetch(`/api/menu/items/${item.id}/modifiers`);
        const steps = await res.json();
        if (steps && steps.length > 0) {
          this.pendingItem = { ...item, modifiers: [] };
          this.modifierSteps = steps;
          this.currentModStepIndex = 0;
          this.openModifierStep();
          return;
        }
      } catch (e) {
        console.error("Error fetching modifiers", e);
      }
    }

    this.pushOrderItem(item, []);
  },

  openChoiceStep() {
    const step = this.modifierSteps[0];
    const titleEl = document.getElementById('modal-modifier-title');
    if (titleEl) {
      titleEl.textContent = step.title;
    }

    const container = document.getElementById('modal-modifier-options');
    container.innerHTML = "";

    step.options.forEach(opt => {
      const btn = document.createElement('button');
      btn.className = 'mod-option-btn';
      btn.style.cssText = "background: #0070ba; color: #fff; font-size: 18px; font-weight: bold; min-height: 60px; border-radius: 6px;";
      btn.textContent = opt.name;
      btn.onclick = async () => {
        document.getElementById('modal-modifiers').classList.remove('active');
        const chosen = opt.choice_item;
        if (chosen.has_modifiers) {
          try {
            const res = await fetch(`/api/menu/items/${chosen.id}/modifiers`);
            const mSteps = await res.json();
            if (mSteps && mSteps.length > 0) {
              this.pendingItem = { ...chosen, modifiers: [] };
              this.modifierSteps = mSteps;
              this.currentModStepIndex = 0;
              this.openModifierStep();
              return;
            }
          } catch (e) {}
        }
        this.pushOrderItem(chosen, []);
      };
      container.appendChild(btn);
    });

    document.getElementById('modal-modifiers').classList.add('active');
  },

  pushOrderItem(item, modifiers) {
    const qty = this.pendingQuantity || 1;
    this.orderItems.push({
      item_id: item.id,
      name: item.name,
      unit_price: item.price,
      quantity: qty,
      modifiers: modifiers || []
    });
    if (qty > 1) {
      this.setPendingQuantity(1);
    }
    this.updateTicket();
  },

  // --- MODIFIERS MODAL WITH AUTO-ADVANCE ---
  openModifierStep() {
    const step = this.modifierSteps[this.currentModStepIndex];
    if (!step) {
      if (this.pendingItem) {
        this.pushOrderItem(this.pendingItem, this.pendingItem.modifiers);
      }
      this.closeModifierModal(true);
      return;
    }

    const titleEl = document.getElementById('modal-modifier-title');
    if (titleEl) {
      const stepNum = this.currentModStepIndex + 1;
      const totalSteps = this.modifierSteps.length;
      titleEl.textContent = `${step.title || 'Modificador'} (${stepNum}/${totalSteps}) para ${this.pendingItem.name}...`;
    }

    const container = document.getElementById('modal-modifier-options');
    container.innerHTML = "";

    step.options.forEach(opt => {
      const btn = document.createElement('button');
      btn.className = 'mod-option-btn';
      btn.innerHTML = `
        <div style="font-size: 17px; font-weight: bold;">${opt.name}</div>
        ${opt.cost > 0 ? `<div style="font-size: 13px; color: #ffeb3b; margin-top: 4px;">+$${opt.cost.toFixed(2)}</div>` : ''}
      `;
      btn.onclick = () => {
        this.selectModifierAndAdvance(opt);
      };
      container.appendChild(btn);
    });

    document.getElementById('modal-modifiers').classList.add('active');
  },

  selectModifierAndAdvance(opt) {
    if (this.pendingItem) {
      if (!this.pendingItem.modifiers) this.pendingItem.modifiers = [];
      this.pendingItem.modifiers.push(opt);
    }
    this.currentModStepIndex++;
    this.openModifierStep();
  },

  skipModifierStep() {
    this.currentModStepIndex++;
    this.openModifierStep();
  },

  closeModifierModal(completed = false) {
    document.getElementById('modal-modifiers').classList.remove('active');
    if (!completed && this.pendingItem) {
      this.pushOrderItem(this.pendingItem, this.pendingItem.modifiers);
    }
    this.pendingItem = null;
  },

  // --- TICKET CALCULATIONS & RENDERING ---
  updateTicket() {
    const list = document.getElementById('ticket-items-list');
    list.innerHTML = "";

    const activeItems = this.orderItems.filter(it => !it.cancelled);

    if (this.orderItems.length === 0) {
      list.innerHTML = `
        <div style="text-align: center; color: #888; margin-top: 40px;">
          Seleccione platos del menú para armar la comanda
        </div>`;
      document.getElementById('txt-subtotal').textContent = "0,00";
      document.getElementById('txt-tax').textContent = "0,00";
      document.getElementById('txt-grand-total').textContent = "$0,00";
      return;
    }

    let subtotal = 0;

    this.orderItems.forEach((oi, idx) => {
      const isCanc = (oi.cancelled === true);
      let lineTotal = 0;

      if (!isCanc) {
        const modCost = (oi.modifiers || []).reduce((sum, m) => sum + (m.cost || 0), 0);
        lineTotal = (oi.unit_price + modCost) * oi.quantity;
        subtotal += lineTotal;
      }

      const row = document.createElement('div');
      row.className = `ticket-row ${idx === this.selectedTicketItemIndex ? 'selected' : ''} ${isCanc ? 'cancelled' : ''}`;
      
      let titleStr = `${oi.quantity} *${oi.name}`;
      if (isCanc) {
        titleStr += " ** CANCELADO **";
      }

      const priceFmt = isCanc ? '0,00' : lineTotal.toFixed(2).replace('.', ',');

      row.innerHTML = `
        <div class="ticket-row-main" style="${isCanc ? 'color: #ff5252; font-weight: bold;' : ''}">
          <span>${titleStr}</span>
          <span>${priceFmt}</span>
        </div>
        ${(oi.modifiers || []).map(m => `
          <div class="ticket-modifier-item" style="${isCanc ? 'text-decoration: line-through; opacity: 0.6;' : ''}">
            ${m.name} 0,00Cada uno
          </div>
        `).join('')}
      `;
      row.onclick = () => {
        this.selectedTicketItemIndex = (this.selectedTicketItemIndex === idx ? -1 : idx);
        this.updateTicket();
      };
      list.appendChild(row);
    });

    // If existing order or editing, display account footer identical to Foto 2
    if (this.currentOrderId) {
      const footerDiv = document.createElement('div');
      footerDiv.style.cssText = "border-top: 1px dashed #333; margin-top: 14px; padding-top: 8px; text-align: center; font-size: 13px; font-weight: bold; color: #111; font-family: 'Courier New', monospace;";
      const timeStr = document.getElementById('ticket-time-now') ? document.getElementById('ticket-time-now').textContent : '';
      footerDiv.innerHTML = `
        <div>&gt;&gt; # de cuenta:   ${this.currentAccountNumber || 1} &lt;&lt;</div>
        ${timeStr ? `<div style="margin-top: 2px; font-weight: normal; font-size: 12px;">${timeStr}</div>` : ''}
      `;
      list.appendChild(footerDiv);
    }

    const taxRate = this.taxRate || 15.0;
    const tax = subtotal * (taxRate / 100.0);
    const total = subtotal + tax;

    const lblTax = document.getElementById('lbl-tax-rate');
    if (lblTax) lblTax.textContent = `Impuesto`;

    document.getElementById('txt-subtotal').textContent = subtotal.toFixed(2).replace('.', ',');
    document.getElementById('txt-tax').textContent = tax.toFixed(2).replace('.', ',');
    document.getElementById('txt-grand-total').textContent = `$${total.toFixed(2).replace('.', ',')}`;

    list.scrollTop = list.scrollHeight;
  },

  // --- COLUMNA CENTRAL DE ACCIONES ALDELO (FOTO 1) ---
  actionModifiers() {
    if (this.selectedTicketItemIndex < 0 || !this.orderItems[this.selectedTicketItemIndex]) {
      this.showToast("Seleccione un plato del ticket primero", true);
      return;
    }
    const item = this.orderItems[this.selectedTicketItemIndex];
    if (item.cancelled) return;
    this.addItemToOrder(item);
  },

  actionQuantity() {
    this.openQuantityModal();
  },

  actionReorder() {
    if (this.selectedTicketItemIndex < 0 || !this.orderItems[this.selectedTicketItemIndex]) {
      this.showToast("Seleccione un plato del ticket primero", true);
      return;
    }
    const item = this.orderItems[this.selectedTicketItemIndex];
    if (item.cancelled) return;
    const clone = JSON.parse(JSON.stringify(item));
    delete clone.tx_id;
    clone.cancelled = false;
    this.orderItems.push(clone);
    this.selectedTicketItemIndex = this.orderItems.length - 1;
    this.updateTicket();
    this.showToast(`Re-ordenado: ${clone.name}`);
  },

  actionDiscount() { this.showToast("Función Descuento (Gestión Caja)"); },
  actionSurcharge() { this.showToast("Función Sobrecargo"); },
  actionHold() { this.showToast("Plato marcado en Espera"); },
  actionDetails() {
    if (this.selectedTicketItemIndex >= 0) {
      const it = this.orderItems[this.selectedTicketItemIndex];
      this.showToast(`${it.name} - $${(it.unit_price || 0).toFixed(2)}`);
    }
  },
  actionWeight() { this.showToast("Balanza no conectada"); },
  actionSplit() { this.showToast("Dividir cuenta en caja"); },
  actionCombine() { this.showToast("Combinar cuentas en caja"); },

  // --- MODAL CANTIDAD (FLUJO ALDELO: CANTIDAD -> SELECCIONAR PRODUCTO) ---
  setPendingQuantity(q) {
    const qty = Math.max(1, parseInt(q, 10) || 1);
    this.pendingQuantity = qty;
    const btn = document.getElementById('btn-action-quantity');
    if (btn) {
      if (qty > 1) {
        btn.textContent = `Cantidad (${qty}x)`;
        btn.classList.add('ac-btn-qty-active');
      } else {
        btn.textContent = 'Cantidad';
        btn.classList.remove('ac-btn-qty-active');
      }
    }
  },
  openQuantityModal() {
    this.qtyInputStr = "";
    const box = document.getElementById('qty-display-box');
    if (box) box.textContent = "";
    document.getElementById('modal-quantity').classList.add('active');
  },
  closeQuantityModal() {
    document.getElementById('modal-quantity').classList.remove('active');
  },
  qtyPress(digit) {
    if (this.qtyInputStr === "0") {
      this.qtyInputStr = digit;
    } else if (this.qtyInputStr.length < 3) {
      this.qtyInputStr += digit;
    }
    const box = document.getElementById('qty-display-box');
    if (box) box.textContent = this.qtyInputStr;
  },
  qtyBackspace() {
    this.qtyInputStr = this.qtyInputStr.slice(0, -1);
    const box = document.getElementById('qty-display-box');
    if (box) box.textContent = this.qtyInputStr;
  },
  qtyClear() {
    this.qtyInputStr = "";
    const box = document.getElementById('qty-display-box');
    if (box) box.textContent = "";
  },
  qtyCancel() {
    this.qtyInputStr = "";
    this.closeQuantityModal();
  },
  confirmQuantity() {
    const q = parseInt(this.qtyInputStr, 10);
    if (!q || q < 1) {
      this.setPendingQuantity(1);
      this.closeQuantityModal();
      return;
    }
    this.setPendingQuantity(q);
    this.closeQuantityModal();
    this.showToast(`Cantidad: ${q}x — Seleccione el producto`);
  },

  // --- FLUJO COMPLETO CANCELAR / REDUCIR ARTÍCULOS (SIN CLAVE AL ABRIR -> CLAVE NIVEL ALDELO AL REDUCIR/CANCELAR -> PERDIDAS/NO PERDIDAS -> RAZÓN -> NOTIFICAR) ---
  openCancelItemFlow() {
    if (this.orderItems.length === 0) {
      this.showToast("No hay artículos en la comanda para cancelar", true);
      return;
    }
    // Sin clave al presionar Cancelar: abrir directamente Reducir artículos existentes
    this.reduceSnapshot = JSON.parse(JSON.stringify(this.orderItems));
    this.cancelAuthorizedEmployee = null;
    this.pendingCancelAction = null;
    this.cancelIsLoss = false;
    this.cancelReason = "";
    this.openReduceItemsModal();
  },

  openCancelPinModal(actionType) {
    this.pendingCancelAction = actionType;
    this.cancelPinEntered = "";
    const disp = document.getElementById('cancel-pin-display');
    if (disp) disp.textContent = "";
    document.getElementById('modal-cancel-pin').classList.add('active');
  },

  closeCancelPinModal() {
    this.pendingCancelAction = null;
    this.cancelPinEntered = "";
    document.getElementById('modal-cancel-pin').classList.remove('active');
  },

  cancelPinPress(digit) {
    if (this.cancelPinEntered.length < 6) {
      this.cancelPinEntered += digit;
      document.getElementById('cancel-pin-display').textContent = "•".repeat(this.cancelPinEntered.length);
    }
  },

  cancelPinBackspace() {
    this.cancelPinEntered = this.cancelPinEntered.slice(0, -1);
    document.getElementById('cancel-pin-display').textContent = "•".repeat(this.cancelPinEntered.length);
  },

  cancelPinClear() {
    this.cancelPinEntered = "";
    document.getElementById('cancel-pin-display').textContent = "";
  },

  async submitCancelPin() {
    if (!this.cancelPinEntered) {
      this.showToast("Ingrese un código de acceso", true);
      return;
    }
    try {
      const res = await fetch('/api/auth/pin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin: this.cancelPinEntered, action: 'void' })
      });
      if (res.ok) {
        const data = await res.json();
        this.cancelAuthorizedEmployee = data.employee || { id: 1, name: "Supervisor" };
        const actionToRun = this.pendingCancelAction;
        this.closeCancelPinModal();
        this.showToast(`Autorizado: ${this.cancelAuthorizedEmployee.name}`);
        if (actionToRun === 'reduce') {
          this.reduceSelectedItemQty();
        } else if (actionToRun === 'cancel_line') {
          this.cancelSelectedLine();
        }
      } else {
        let errMsg = "Código de acceso incorrecto o sin permiso para anular";
        try {
          const errData = await res.json();
          if (errData && errData.detail) errMsg = errData.detail;
        } catch (e) {}
        this.showToast(errMsg, true);
        this.cancelPinClear();
      }
    } catch (e) {
      this.showToast("Error de conexión al validar permiso", true);
    }
  },

  // REDUCIR / CANCELAR ARTÍCULOS EXISTENTES
  openReduceItemsModal() {
    this.reduceSelectedIndex = (this.selectedTicketItemIndex >= 0) ? this.selectedTicketItemIndex : 0;
    this.renderReduceWhiteList();
    document.getElementById('modal-reduce-items').classList.add('active');
  },

  renderReduceWhiteList() {
    const list = document.getElementById('reduce-white-list');
    list.innerHTML = "";

    this.orderItems.forEach((oi, idx) => {
      const row = document.createElement('div');
      const isCanc = (oi.cancelled === true);
      row.className = `reduce-item-row ${idx === this.reduceSelectedIndex ? 'selected' : ''} ${isCanc ? 'cancelled' : ''}`;
      
      const priceStr = `$${(oi.unit_price || 0).toFixed(2)}`;
      row.innerHTML = `
        <span>${oi.quantity} *${oi.name} ${isCanc ? '** CANCELADO **' : ''}</span>
        <span>${isCanc ? '$0.00' : priceStr}</span>
      `;
      row.onclick = () => {
        this.reduceSelectedIndex = idx;
        this.renderReduceWhiteList();
      };
      list.appendChild(row);
    });
  },

  reduceSelectedItemQty() {
    if (this.reduceSelectedIndex < 0 || !this.orderItems[this.reduceSelectedIndex]) return;
    const item = this.orderItems[this.reduceSelectedIndex];
    if (item.cancelled) return;

    // Al momento de reducir: solicitar código con nivel de acceso configurado en Aldelo ('Void Order')
    if (!this.cancelAuthorizedEmployee) {
      this.openCancelPinModal('reduce');
      return;
    }

    if (item.quantity > 1) {
      item.quantity -= 1;
    } else {
      item.cancelled = true;
    }
    this.renderReduceWhiteList();
  },

  cancelSelectedLine() {
    if (this.reduceSelectedIndex < 0 || !this.orderItems[this.reduceSelectedIndex]) return;
    const item = this.orderItems[this.reduceSelectedIndex];
    if (item.cancelled) return;

    // Al momento de cancelar línea: solicitar código con nivel de acceso configurado en Aldelo ('Void Order')
    if (!this.cancelAuthorizedEmployee) {
      this.openCancelPinModal('cancel_line');
      return;
    }

    item.cancelled = true;
    this.renderReduceWhiteList();
  },

  reduceScrollUp() {
    if (this.reduceSelectedIndex > 0) {
      this.reduceSelectedIndex--;
      this.renderReduceWhiteList();
    }
  },

  reduceScrollDown() {
    if (this.reduceSelectedIndex < this.orderItems.length - 1) {
      this.reduceSelectedIndex++;
      this.renderReduceWhiteList();
    }
  },

  hasReduceChanges() {
    if (!this.reduceSnapshot) return false;
    for (let i = 0; i < this.orderItems.length; i++) {
      const orig = this.reduceSnapshot[i];
      const cur = this.orderItems[i];
      if (!orig) continue;
      if ((cur.cancelled === true) !== (orig.cancelled === true)) return true;
      if (Number(cur.quantity) !== Number(orig.quantity)) return true;
    }
    return false;
  },

  confirmReduceItems() {
    document.getElementById('modal-reduce-items').classList.remove('active');
    if (!this.hasReduceChanges()) {
      this.reduceSnapshot = null;
      return;
    }
    // Paso siguiente: Perdidas / No perdidas
    document.getElementById('modal-cancel-loss').classList.add('active');
  },

  cancelLossAbort() {
    document.getElementById('modal-cancel-loss').classList.remove('active');
    if (this.reduceSnapshot) {
      this.orderItems = JSON.parse(JSON.stringify(this.reduceSnapshot));
      this.reduceSnapshot = null;
      this.updateTicket();
    }
  },

  selectCancelLoss(isLoss) {
    this.cancelIsLoss = !!isLoss;
    document.getElementById('modal-cancel-loss').classList.remove('active');
    // Paso siguiente: Razón de la cancelación
    const inp = document.getElementById('cancel-reason-input');
    if (inp) {
      inp.value = "";
    }
    this.reasonCapsLock = true;
    this.updateReasonKeyboardCapsUI();
    document.getElementById('modal-cancel-reason').classList.add('active');
    if (inp) {
      setTimeout(() => inp.focus(), 60);
    }
  },

  updateReasonKeyboardCapsUI() {
    const capsBtn = document.getElementById('btn-reason-caps');
    if (capsBtn) {
      capsBtn.classList.toggle('caps-active', this.reasonCapsLock);
    }
    document.querySelectorAll('#modal-cancel-reason .aldelo-kbd-key[data-ch]').forEach(btn => {
      const ch = btn.getAttribute('data-ch');
      btn.textContent = this.reasonCapsLock ? ch.toUpperCase() : ch.toLowerCase();
    });
  },

  reasonToggleCaps() {
    this.reasonCapsLock = !this.reasonCapsLock;
    this.updateReasonKeyboardCapsUI();
  },

  reasonKey(ch) {
    const inp = document.getElementById('cancel-reason-input');
    if (!inp) return;
    const out = (ch.length === 1 && /[A-Za-z]/.test(ch))
      ? (this.reasonCapsLock ? ch.toUpperCase() : ch.toLowerCase())
      : ch;
    const start = inp.selectionStart != null ? inp.selectionStart : inp.value.length;
    const end = inp.selectionEnd != null ? inp.selectionEnd : inp.value.length;
    inp.value = inp.value.slice(0, start) + out + inp.value.slice(end);
    const pos = start + out.length;
    inp.focus();
    inp.setSelectionRange(pos, pos);
  },

  reasonBackspace() {
    const inp = document.getElementById('cancel-reason-input');
    if (!inp) return;
    const start = inp.selectionStart != null ? inp.selectionStart : inp.value.length;
    const end = inp.selectionEnd != null ? inp.selectionEnd : inp.value.length;
    if (start !== end) {
      inp.value = inp.value.slice(0, start) + inp.value.slice(end);
      inp.focus();
      inp.setSelectionRange(start, start);
    } else if (start > 0) {
      inp.value = inp.value.slice(0, start - 1) + inp.value.slice(end);
      inp.focus();
      inp.setSelectionRange(start - 1, start - 1);
    }
  },

  reasonClear() {
    const inp = document.getElementById('cancel-reason-input');
    if (!inp) return;
    inp.value = "";
    inp.focus();
  },

  reasonHome() {
    const inp = document.getElementById('cancel-reason-input');
    if (!inp) return;
    inp.focus();
    inp.setSelectionRange(0, 0);
  },

  reasonEnd() {
    const inp = document.getElementById('cancel-reason-input');
    if (!inp) return;
    const len = inp.value.length;
    inp.focus();
    inp.setSelectionRange(len, len);
  },

  reasonMove(delta) {
    const inp = document.getElementById('cancel-reason-input');
    if (!inp) return;
    const pos = Math.max(0, Math.min(inp.value.length, (inp.selectionStart || 0) + delta));
    inp.focus();
    inp.setSelectionRange(pos, pos);
  },

  reasonCancel() {
    document.getElementById('modal-cancel-reason').classList.remove('active');
    if (this.reduceSnapshot) {
      this.orderItems = JSON.parse(JSON.stringify(this.reduceSnapshot));
      this.reduceSnapshot = null;
      this.updateTicket();
    }
    this.showToast("Cancelación anulada");
  },

  reasonFinish() {
    const inp = document.getElementById('cancel-reason-input');
    const txt = inp ? inp.value.trim() : "";
    if (!txt) {
      this.showToast("Ingrese la razón de la cancelación", true);
      if (inp) inp.focus();
      return;
    }
    this.cancelReason = txt;
    document.getElementById('modal-cancel-reason').classList.remove('active');
    // Paso final: Notificar impresión a cocina/bar
    document.getElementById('modal-notify-print').classList.add('active');
  },

  async finalizeItemCancel(notifyKitchen) {
    document.getElementById('modal-notify-print').classList.remove('active');

    const snapshot = this.reduceSnapshot || [];
    const newlyCancelledTxs = [];
    const reducedItemsPayload = [];
    const kitchenCancelledItems = [];

    this.orderItems.forEach((cur, idx) => {
      const orig = snapshot[idx];
      if (!orig) return;
      const wasCancelled = (orig.cancelled === true);
      const isNowCancelled = (cur.cancelled === true);

      if (!wasCancelled && isNowCancelled) {
        if (cur.tx_id) {
          newlyCancelledTxs.push(cur.tx_id);
        }
        kitchenCancelledItems.push({ name: cur.name, quantity: orig.quantity || 1 });
      } else if (!isNowCancelled && Number(cur.quantity) < Number(orig.quantity)) {
        const diff = Number(orig.quantity) - Number(cur.quantity);
        if (cur.tx_id) {
          reducedItemsPayload.push({ tx_id: cur.tx_id, new_qty: Number(cur.quantity) });
        }
        kitchenCancelledItems.push({ name: cur.name, quantity: diff });
      }
    });

    // Si la orden ya está grabada en la base de datos de Aldelo
    if (this.currentOrderId && (newlyCancelledTxs.length > 0 || reducedItemsPayload.length > 0)) {
      try {
        await fetch(`/api/orders/${this.currentOrderId}/void-items`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            transaction_ids: newlyCancelledTxs,
            reduced_items: reducedItemsPayload,
            items: kitchenCancelledItems,
            notify_kitchen: notifyKitchen,
            table_num: String(this.selectedTable.number || this.selectedTable.id),
            waiter_name: this.currentWaiter ? this.currentWaiter.name : "Mesero",
            employee_id: this.cancelAuthorizedEmployee ? this.cancelAuthorizedEmployee.id : (this.currentWaiter ? this.currentWaiter.id : 1),
            is_loss: this.cancelIsLoss,
            reason: this.cancelReason
          })
        });
      } catch (e) {
        console.error("Error voiding in DB:", e);
      }
    } else if (!this.currentOrderId) {
      // Si son platos aún no enviados, eliminar los marcados como cancelados de la lista local
      this.orderItems = this.orderItems.filter(it => !it.cancelled);
    }

    this.reduceSnapshot = null;
    this.cancelAuthorizedEmployee = null;
    this.pendingCancelAction = null;
    this.updateTicket();
    const lossText = this.cancelIsLoss ? "Pérdida" : "No pérdidas";
    this.showToast(`Cancelación registrada (${lossText})`);
  },

  cancelCurrentOrder() {
    this.orderItems = [];
    this.currentWaiter = null;
    this.setPendingQuantity(1);
    this.showScreen('screen-home');
  },

  promptChangeGuests() {
    document.getElementById('guests-display').textContent = this.guestCount;
    this.showScreen('screen-guests');
  },

  // --- SUBMIT TO KITCHEN / LISTO & CADENA ---
  async submitOrderToKitchen(isChain = false) {
    if (this.orderItems.length === 0) {
      this.showToast("Comanda vacía: agregue platos", true);
      return;
    }

    const btn = document.getElementById('btn-submit-order');
    btn.disabled = true;
    btn.textContent = "Enviando...";

    try {
      if (this.currentOrderId) {
        // Editando orden existente: verificar si hay platos nuevos agregados
        const newItems = this.orderItems.filter(it => !it.is_existing && !it.cancelled);
        if (newItems.length > 0) {
          const payload = {
            order_id: this.currentOrderId,
            table_id: this.selectedTable.id,
            employee_id: this.currentWaiter ? this.currentWaiter.id : 5,
            guests: this.guestCount,
            items: newItems
          };

          const res = await fetch('/api/orders', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });

          if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Error al actualizar la orden");
          }

          if (isChain) {
            this.showToast("¡Platos adicionales enviados a cocina!");
            await this.openExistingOrder(this.currentOrderId);
          } else {
            this.showToast(`Comanda #${this.currentOrderId} actualizada y enviada a cocina`);
            this.orderItems = [];
            this.currentOrderId = null;
            this.currentWaiter = null;
            this.showScreen('screen-home');
          }
        } else {
          this.showToast(`Orden #${this.currentOrderId} guardada`);
          this.orderItems = [];
          this.currentOrderId = null;
          this.currentWaiter = null;
          this.showScreen('screen-home');
        }
      } else {
        // Nueva orden desde cero
        const payload = {
          table_id: this.selectedTable.id,
          employee_id: this.currentWaiter ? this.currentWaiter.id : 5,
          guests: this.guestCount,
          items: this.orderItems
        };

        const res = await fetch('/api/orders', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || "Error al enviar la comanda");
        }

        const result = await res.json();

        if (isChain) {
          this.showToast(`¡Comanda enviada a cocina! Continúe agregando platos.`);
          this.orderItems = [];
          this.updateTicket();
        } else {
          this.showToast(`Comanda #${result.order_id} enviada (Mesa ${this.selectedTable.number})`);
          this.orderItems = [];
          this.currentWaiter = null;
          this.showScreen('screen-home');
        }
      }
    } catch (e) {
      this.showToast(e.message, true);
    } finally {
      btn.disabled = false;
      btn.textContent = "Listo";
    }
  },

  toggleFullscreen() {
    if (!document.fullscreenElement && !document.webkitFullscreenElement) {
      const docEl = document.documentElement;
      if (docEl.requestFullscreen) {
        docEl.requestFullscreen();
      } else if (docEl.webkitRequestFullscreen) {
        docEl.webkitRequestFullscreen();
      } else if (docEl.msRequestFullscreen) {
        docEl.msRequestFullscreen();
      }
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen();
      } else if (document.webkitExitFullscreen) {
        document.webkitExitFullscreen();
      } else if (document.msExitFullscreen) {
        document.msExitFullscreen();
      }
    }
  },

  deferredPwaPrompt: null,

  installPWA() {
    if (this.deferredPwaPrompt) {
      this.deferredPwaPrompt.prompt();
      this.deferredPwaPrompt.userChoice.then((choiceResult) => {
        if (choiceResult.outcome === 'accepted') {
          this.showToast("Instalando Aldelo POS...");
        }
        this.deferredPwaPrompt = null;
        const btn = document.getElementById('btn-install-pwa');
        if (btn) btn.style.display = 'none';
      });
    } else {
      this.showToast("Pulsa el menú ⋮ y elige 'Agregar a pantalla principal' / 'Instalar'");
    }
  }
};

window.addEventListener('DOMContentLoaded', () => {
  app.init();
});

// Registrar Service Worker para PWA
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js')
      .then(reg => console.log('Aldelo POS Service Worker activo:', reg.scope))
      .catch(err => console.log('Service Worker no activo:', err));
  });
}

// Activar pantalla completa automáticamente al primer toque del mesero (sin botones confusos)
let hasRequestedFs = false;
function triggerAutoFullscreen() {
  if (hasRequestedFs) return;
  if (!document.fullscreenElement && !document.webkitFullscreenElement) {
    const docEl = document.documentElement;
    const req = docEl.requestFullscreen || docEl.webkitRequestFullscreen || docEl.msRequestFullscreen;
    if (req) {
      req.call(docEl)
        .then(() => { hasRequestedFs = true; })
        .catch(() => {});
    }
  }
}
window.addEventListener('click', triggerAutoFullscreen, { passive: true });
window.addEventListener('touchstart', triggerAutoFullscreen, { passive: true });

// Capturar evento de instalación PWA en Chrome / Android
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  app.deferredPwaPrompt = e;
});

window.addEventListener('resize', () => {
  if (app.activeScreenId === 'screen-order' && app.activeMenuGroupId) {
    app.loadMenuGroups();
    app.loadMenuItems(app.activeMenuGroupId);
  }
});

window.addEventListener('orientationchange', () => {
  setTimeout(() => {
    if (app.activeScreenId === 'screen-order' && app.activeMenuGroupId) {
      app.loadMenuGroups();
      app.loadMenuItems(app.activeMenuGroupId);
    }
  }, 150);
});
