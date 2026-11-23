import os
import json
import socket
from datetime import datetime
from typing import Dict, Any, List, Optional
import win32print
import pythoncom
import win32com.client
from backend.db import get_database_path, get_station_id, get_connection
from backend.paths import get_printer_config_path

CONFIG_FILE = get_printer_config_path()

def get_aldelo_station_printers(station_id: Optional[int] = None) -> Dict[str, Any]:
    """Reads receipt printer, all 6 kitchen printers and bar printer directly from Aldelo's StationSettings table."""
    if station_id is None:
        station_id = get_station_id()

    pythoncom.CoInitialize()
    printers_info = {
        "station_id": station_id,
        "receipt": {"title": "Impresora de recibos", "name": "No Printer Attached", "type": "20006"},
        "kitchen": [],
        "bar": {"title": "Bar", "name": "No Printer Attached", "type": "20006"}
    }
    try:
        conn = get_connection()
        rs = win32com.client.Dispatch("ADODB.Recordset")
        rs.Open(f"SELECT * FROM StationSettings WHERE StationID = {station_id}", conn)
        if not rs.EOF:
            # 1. Impresora de recibos
            r_name = rs.Fields("ReceiptPrinterName").Value
            r_type = rs.Fields("ReceiptPrinterType").Value
            printers_info["receipt"] = {
                "title": "Impresora de recibos",
                "name": str(r_name).strip() if r_name and str(r_name).strip() != "None" else "No Printer Attached",
                "type": str(r_type).strip() if r_type and str(r_type).strip() != "None" else "20006"
            }

            # 2. Impresoras de cocina 1..6
            for i in range(1, 7):
                k_title = rs.Fields(f"KitchenPrinter{i}Title").Value
                k_name = rs.Fields(f"KitchenPrinter{i}Name").Value
                k_type = rs.Fields(f"KitchenPrinter{i}Type").Value
                
                title_clean = str(k_title).strip() if k_title and str(k_title).strip() != "None" else ("Cocina" if i == 1 else "")
                name_clean = str(k_name).strip() if k_name and str(k_name).strip() != "None" else "No Printer Attached"
                type_clean = str(k_type).strip() if k_type and str(k_type).strip() != "None" else "20006"
                
                printers_info["kitchen"].append({
                    "id": i,
                    "title": title_clean,
                    "name": name_clean,
                    "type": type_clean
                })
            
            # 3. Impresora de bar
            b_name = rs.Fields("BarPrinterName").Value
            b_type = rs.Fields("BarPrinterType").Value
            printers_info["bar"] = {
                "title": "Bar",
                "name": str(b_name).strip() if b_name and str(b_name).strip() != "None" else "No Printer Attached",
                "type": str(b_type).strip() if b_type and str(b_type).strip() != "None" else "20006"
            }
        rs.Close()
        conn.Close()
    except Exception as e:
        print(f"Error reading Aldelo StationSettings for Station {station_id}: {e}")
        
    return printers_info

def load_printer_config(station_id: Optional[int] = None) -> Dict[str, Any]:
    aldelo_printers = get_aldelo_station_printers(station_id)
    cfg = {
        "receipt": {"type": "none", "windows_name": "", "ip": "", "port": 9100},
        "kitchen": {"type": "none", "windows_name": "", "ip": "", "port": 9100},
        "bar": {"type": "none", "windows_name": "", "ip": "", "port": 9100}
    }
    
    r = aldelo_printers.get("receipt", {})
    if r.get("name") and r["name"] != "No Printer Attached":
        cfg["receipt"]["type"] = "windows"
        cfg["receipt"]["windows_name"] = r["name"]

    k_list = aldelo_printers.get("kitchen", [])
    for kp in k_list:
        if kp.get("name") and kp["name"] != "No Printer Attached":
            cfg["kitchen"]["type"] = "windows"
            cfg["kitchen"]["windows_name"] = kp["name"]
            break
        
    b = aldelo_printers.get("bar", {})
    if b.get("name") and b["name"] != "No Printer Attached":
        cfg["bar"]["type"] = "windows"
        cfg["bar"]["windows_name"] = b["name"]

    return cfg

def save_printer_config(config: Dict[str, Any]):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

def get_installed_windows_printers() -> List[str]:
    try:
        printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
        return [p[2] for p in printers]
    except Exception as e:
        print(f"Error enumerating printers: {e}")
        return []

def resolve_target_printer(station_id: Optional[int] = None, role: str = "receipt") -> Optional[str]:
    """
    Resuelve la impresora física adecuada verificando que realmente esté instalada en Windows en este PC.
    """
    installed = get_installed_windows_printers()
    if not installed:
        return None

    local_st_id = get_station_id()
    local_st = get_aldelo_station_printers(local_st_id)

    # 1. Prioridad: Impresora configurada en la estación activa de este PC
    if role == "receipt":
        cand = local_st.get("receipt", {}).get("name")
        if cand and cand != "No Printer Attached" and cand in installed:
            return cand
    elif role == "kitchen":
        for kp in local_st.get("kitchen", []):
            cand = kp.get("name")
            if cand and cand != "No Printer Attached" and cand in installed:
                return cand
    elif role == "bar":
        cand = local_st.get("bar", {}).get("name")
        if cand and cand != "No Printer Attached" and cand in installed:
            return cand

    # 2. Prioridad: Impresora configurada en la estación solicitada (si existe instalada localmente)
    if station_id and station_id != local_st_id:
        req_st = get_aldelo_station_printers(station_id)
        if role == "receipt":
            cand = req_st.get("receipt", {}).get("name")
            if cand and cand != "No Printer Attached" and cand in installed:
                return cand
        elif role == "kitchen":
            for kp in req_st.get("kitchen", []):
                cand = kp.get("name")
                if cand and cand != "No Printer Attached" and cand in installed:
                    return cand
        elif role == "bar":
            cand = req_st.get("bar", {}).get("name")
            if cand and cand != "No Printer Attached" and cand in installed:
                return cand

    # 3. Fallback a cualquier impresora de la estación local que sí esté instalada
    cand_r = local_st.get("receipt", {}).get("name")
    if cand_r and cand_r in installed:
        return cand_r
    for kp in local_st.get("kitchen", []):
        cand_k = kp.get("name")
        if cand_k and cand_k in installed:
            return cand_k
    cand_b = local_st.get("bar", {}).get("name")
    if cand_b and cand_b in installed:
        return cand_b

    # 4. Fallback a impresoras instaladas físicas de Windows (evitando PDF/AnyDesk si hay una física)
    physical = [p for p in installed if not any(v in p.lower() for v in ["pdf", "xps", "onenote", "anydesk", "fax"])]
    if physical:
        return physical[0]
    return installed[0]

def _send_raw_to_windows(printer_name: str, raw_data: bytes):
    hPrinter = win32print.OpenPrinter(printer_name)
    try:
        hJob = win32print.StartDocPrinter(hPrinter, 1, ("Comanda Aldelo", None, "RAW"))
        win32print.StartPagePrinter(hPrinter)
        win32print.WritePrinter(hPrinter, raw_data)
        win32print.EndPagePrinter(hPrinter)
        win32print.EndDocPrinter(hPrinter)
    finally:
        win32print.ClosePrinter(hPrinter)

def _send_raw_to_network(ip: str, port: int, raw_data: bytes):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(4.0)
    s.connect((ip, port))
    s.sendall(raw_data)
    s.close()

def _enc(text: str) -> bytes:
    """Encodes text to Code Page 850 with fallback for thermal/matrix POS receipt printers."""
    try:
        return text.encode('cp850', errors='replace')
    except Exception:
        return text.encode('ascii', errors='replace')

def _two_col(left: str, right: str, width: int = 40) -> str:
    left = str(left or '').strip()
    right = str(right or '').strip()
    space = width - len(left) - len(right)
    if space < 1:
        left = left[:max(1, width - len(right) - 1)]
        space = 1
    return left + (" " * space) + right + "\n"

def build_esc_pos_ticket(
    title: str,
    table_num: str,
    waiter_name: str,
    guests: int,
    order_id: int,
    items: List[Dict[str, Any]],
    station_id: Optional[int] = None,
    order_type: str = "Mesas",
    is_reorder: bool = False
) -> bytes:
    """Genera la comanda de cocina/bar exactamente en el formato oficial de Aldelo POS."""
    if station_id is None:
        station_id = get_station_id()

    ESC = b'\x1b'
    GS = b'\x1d'
    
    INIT = ESC + b'@'
    SELECT_CP850 = ESC + b't\x02'
    ALIGN_CENTER = ESC + b'a\x01'
    ALIGN_LEFT = ESC + b'a\x00'
    BOLD_ON = ESC + b'E\x01'
    BOLD_OFF = ESC + b'E\x00'
    NORMAL_SIZE = ESC + b'!\x00' + GS + b'!\x00'
    DOUBLE_HEIGHT = ESC + b'!\x10' + GS + b'!\x01'
    DOUBLE_SIZE = ESC + b'!\x30' + GS + b'!\x11'
    PAPER_CUT = GS + b'V\x00'
    WIDTH = 40
    
    buf = bytearray()
    buf.extend(INIT)
    buf.extend(SELECT_CP850)
    
    # 1. Cabecera (Título de cocina oficial de Aldelo)
    buf.extend(ALIGN_CENTER)
    buf.extend(BOLD_ON + DOUBLE_SIZE)
    display_title = f"** {title.upper()} **" if title else "** COCINA **"
    buf.extend(_enc(f"{display_title}\n"))
    buf.extend(NORMAL_SIZE + BOLD_OFF)
    buf.extend(_enc("=" * WIDTH + "\n"))
    
    # 2. Datos de orden
    buf.extend(ALIGN_LEFT)
    buf.extend(BOLD_ON + DOUBLE_HEIGHT)
    buf.extend(_enc(f"ORDEN #: {order_id}\n"))
    buf.extend(NORMAL_SIZE + BOLD_OFF)

    # Mesa y comensales
    table_str = f"MESA: {table_num}"
    pax_str = f"PERSONAS: {guests}"
    buf.extend(BOLD_ON)
    buf.extend(_enc(_two_col(table_str, pax_str, WIDTH)))
    buf.extend(BOLD_OFF)

    # Mesero y Estación
    waiter_str = f"MESERO: {waiter_name}"
    st_str = f"ESTACION: {station_id}"
    buf.extend(_enc(_two_col(waiter_str, st_str, WIDTH)))

    # Fecha y Hora
    now = datetime.now()
    date_str = now.strftime("%d/%m/%Y")
    time_str = now.strftime("%I:%M %p")
    buf.extend(_enc(_two_col(f"FECHA: {date_str}", f"HORA: {time_str}", WIDTH)))

    # Indicador de re-orden o tipo
    if is_reorder:
        buf.extend(BOLD_ON)
        buf.extend(_enc(_two_col("TIPO: ADICIONAL / RE-ORDEN", "", WIDTH)))
        buf.extend(BOLD_OFF)
    elif order_type:
        buf.extend(_enc(_two_col(f"TIPO: {str(order_type).upper()}", "", WIDTH)))

    buf.extend(_enc("-" * WIDTH + "\n"))

    # 3. Encabezado de platos
    buf.extend(BOLD_ON)
    buf.extend(_enc("CANT  DESCRIPCION\n"))
    buf.extend(BOLD_OFF)
    buf.extend(_enc("-" * WIDTH + "\n"))
    
    # 4. Lista de platos y modificadores
    total_qty = 0
    for it in items:
        if it.get("cancelled"):
            continue
        qty = int(it.get('quantity', 1))
        total_qty += qty
        name = it.get('chit_name') or it.get('name') or ''
        name = name.strip()

        # Plato en letra grande/negrita para cocineros
        buf.extend(BOLD_ON + DOUBLE_HEIGHT)
        buf.extend(_enc(f" {qty:>2}   {name}\n"))
        buf.extend(NORMAL_SIZE + BOLD_OFF)
        
        # Modificadores indentados al estilo Aldelo
        mods = it.get('modifiers', [])
        for m in mods:
            m_name = m.get('chit_name') or m.get('name') or ''
            if m_name:
                buf.extend(_enc(f"        * {m_name.strip()}\n"))

        inst = it.get("instruction") or it.get("comment") or it.get("note")
        if inst:
            buf.extend(_enc(f"        >> {str(inst).strip()}\n"))
            
    buf.extend(_enc("-" * WIDTH + "\n"))
    buf.extend(BOLD_ON)
    buf.extend(_enc(_two_col(f"TOTAL PRODUCTOS: {total_qty}", "", WIDTH)))
    buf.extend(BOLD_OFF)
    buf.extend(_enc("=" * WIDTH + "\n"))

    # Recordatorio inferior de mesa para cocina
    buf.extend(ALIGN_CENTER)
    buf.extend(BOLD_ON + DOUBLE_SIZE)
    buf.extend(_enc(f"MESA: {table_num}\n"))
    buf.extend(NORMAL_SIZE + BOLD_OFF)
    buf.extend(_enc("=" * WIDTH + "\n"))

    buf.extend(b"\n\n\n\n")
    buf.extend(PAPER_CUT)
    
    return bytes(buf)

def print_ticket(
    target: str,
    table_num: str,
    waiter_name: str,
    guests: int,
    order_id: int,
    items: List[Dict[str, Any]],
    is_reorder: bool = False,
    order_type: str = "Mesas"
) -> bool:
    local_st = get_station_id()
    aldelo_st = get_aldelo_station_printers(local_st)
    installed = get_installed_windows_printers()
    printed = False

    if target == "kitchen":
        kitchen_list = aldelo_st.get("kitchen", [])
        valid_printers = []
        for kp in kitchen_list:
            p_name = kp.get("name")
            if p_name and p_name != "No Printer Attached" and p_name in installed:
                title_clean = kp.get("title") or f"COCINA #{kp.get('id', 1)}"
                valid_printers.append((p_name, title_clean))

        # Si ninguna impresora de cocina configurada está instalada, resolver fallback instalada
        if not valid_printers:
            fb = resolve_target_printer(local_st, role="kitchen")
            if fb:
                valid_printers.append((fb, "COCINA"))

        for p_name, title_clean in valid_printers:
            try:
                raw_data = build_esc_pos_ticket(
                    title=title_clean,
                    table_num=table_num,
                    waiter_name=waiter_name,
                    guests=guests,
                    order_id=order_id,
                    items=items,
                    station_id=local_st,
                    order_type=order_type,
                    is_reorder=is_reorder
                )
                _send_raw_to_windows(p_name, raw_data)
                print(f"[print_ticket] Comanda de cocina impresa exitosamente en '{p_name}'")
                printed = True
            except Exception as e:
                print(f"[print_ticket] Error imprimiendo comanda en {title_clean} ({p_name}): {e}")
        return printed

    elif target == "bar":
        b = aldelo_st.get("bar", {})
        p_name = b.get("name")
        target_bar = None
        if p_name and p_name != "No Printer Attached" and p_name in installed:
            target_bar = p_name
        else:
            target_bar = resolve_target_printer(local_st, role="bar")

        if target_bar:
            try:
                title_bar = b.get("title") or "BARRA"
                raw_data = build_esc_pos_ticket(
                    title=title_bar,
                    table_num=table_num,
                    waiter_name=waiter_name,
                    guests=guests,
                    order_id=order_id,
                    items=items,
                    station_id=local_st,
                    order_type=order_type,
                    is_reorder=is_reorder
                )
                _send_raw_to_windows(target_bar, raw_data)
                print(f"[print_ticket] Comanda de bar impresa exitosamente en '{target_bar}'")
                return True
            except Exception as e:
                print(f"[print_ticket] Error imprimiendo en bar ({target_bar}): {e}")
        return False
        
    return False

def print_cancellation_ticket(
    table_num: str,
    waiter_name: str,
    cancelled_items: List[Dict[str, Any]],
    order_id: Optional[int] = None,
    is_loss: bool = False,
    reason: str = ""
) -> bool:
    """Imprime una notificación de anulación idéntica a Aldelo en las impresoras de cocina."""
    ESC = b'\x1b'
    GS = b'\x1d'
    INIT = ESC + b'@'
    SELECT_CP850 = ESC + b't\x02'
    ALIGN_CENTER = ESC + b'a\x01'
    ALIGN_LEFT = ESC + b'a\x00'
    BOLD_ON = ESC + b'E\x01'
    BOLD_OFF = ESC + b'E\x00'
    DOUBLE_SIZE = ESC + b'!\x30' + GS + b'!\x11'
    DOUBLE_HEIGHT = ESC + b'!\x10' + GS + b'!\x01'
    NORMAL_SIZE = ESC + b'!\x00' + GS + b'!\x00'
    PAPER_CUT = GS + b'V\x00'
    WIDTH = 40
    
    buf = bytearray()
    buf.extend(INIT)
    buf.extend(SELECT_CP850)
    buf.extend(ALIGN_CENTER)
    buf.extend(BOLD_ON + DOUBLE_SIZE)
    buf.extend(_enc("*** ANULACION ***\n"))
    buf.extend(NORMAL_SIZE + BOLD_OFF)
    buf.extend(_enc("=" * WIDTH + "\n"))
    
    buf.extend(ALIGN_LEFT)
    if order_id:
        buf.extend(BOLD_ON + DOUBLE_HEIGHT)
        buf.extend(_enc(f"ORDEN #: {order_id}\n"))
        buf.extend(NORMAL_SIZE + BOLD_OFF)

    table_str = f"MESA: {table_num}"
    waiter_str = f"MESERO: {waiter_name}"
    buf.extend(BOLD_ON)
    buf.extend(_enc(_two_col(table_str, waiter_str, WIDTH)))
    buf.extend(BOLD_OFF)

    now = datetime.now()
    buf.extend(_enc(_two_col(f"FECHA: {now.strftime('%d/%m/%Y')}", f"HORA: {now.strftime('%I:%M %p')}", WIDTH)))
    loss_label = "PERDIDA" if is_loss else "NO PERDIDAS"
    buf.extend(BOLD_ON)
    buf.extend(_enc(f"ESTADO: {loss_label}\n"))
    if reason and reason.strip():
        buf.extend(_enc(f"RAZON: {reason.strip()}\n"))
    buf.extend(BOLD_OFF)
    buf.extend(_enc("-" * WIDTH + "\n"))

    buf.extend(BOLD_ON)
    buf.extend(_enc("** PLATOS ANULADOS / CANCELADOS **\n"))
    buf.extend(_enc("CANT  DESCRIPCION\n"))
    buf.extend(BOLD_OFF)
    buf.extend(_enc("-" * WIDTH + "\n"))

    buf.extend(BOLD_ON + DOUBLE_HEIGHT)
    for it in cancelled_items:
        qty = int(it.get('quantity', 1))
        name = it.get('name', '').strip()
        buf.extend(_enc(f" {qty:>2}   {name} (ANULADO)\n"))
    buf.extend(NORMAL_SIZE + BOLD_OFF)
    buf.extend(_enc("=" * WIDTH + "\n\n\n\n"))
    buf.extend(PAPER_CUT)
    
    raw_data = bytes(buf)
    local_st = get_station_id()
    station = get_aldelo_station_printers(local_st)
    kitchen_list = station.get("kitchen", [])
    installed = get_installed_windows_printers()
    printed = False
    for kp in kitchen_list:
        k_printer = kp.get("name")
        if k_printer and k_printer != "No Printer Attached" and k_printer in installed:
            try:
                _send_raw_to_windows(k_printer, raw_data)
                printed = True
            except Exception as e:
                print(f"[print_cancellation_ticket] Error imprimiendo anulación en {kp.get('title')}: {e}")
    if not printed:
        fb = resolve_target_printer(local_st, role="kitchen")
        if fb:
            try:
                _send_raw_to_windows(fb, raw_data)
                printed = True
            except Exception as e:
                print(f"[print_cancellation_ticket] Error imprimiendo anulación en fallback {fb}: {e}")
    return printed

def print_test_ticket() -> Dict[str, Any]:
    sample_items = [
        {"name": "Chx Fillet Sndwch", "chit_name": "Chx Fillet Sndwch", "quantity": 1, "modifiers": [{"name": "Wheat Bread"}, {"name": "French Fries"}]},
        {"name": "Buffalo Wings", "chit_name": "Buffalo Wings", "quantity": 1, "modifiers": []}
    ]
    k_res = print_ticket("kitchen", "TEST-99", "Mesero Prueba", 2, 9999, sample_items)
    b_res = print_ticket("bar", "TEST-99", "Mesero Prueba", 2, 9999, sample_items)
    return {
        "kitchen": "OK" if k_res else "No configurada o sin conectar",
        "bar": "OK" if b_res else "No configurada"
    }

def print_guest_check(order_id: int) -> bool:
    """Imprime la precuenta (Guest Check) idéntica al formato oficial de Aldelo POS."""
    from backend import db
    order = db.get_order_details(order_id)
    if not order:
        return False
        
    store = db.get_store_settings()
    station_id = order.get("station_id") or get_station_id()

    ESC = b'\x1b'
    GS = b'\x1d'
    INIT = ESC + b'@'
    SELECT_CP850 = ESC + b't\x02'
    ALIGN_CENTER = ESC + b'a\x01'
    ALIGN_LEFT = ESC + b'a\x00'
    BOLD_ON = ESC + b'E\x01'
    BOLD_OFF = ESC + b'E\x00'
    DOUBLE_SIZE = ESC + b'!\x30' + GS + b'!\x11'
    DOUBLE_HEIGHT = ESC + b'!\x10' + GS + b'!\x01'
    NORMAL_SIZE = ESC + b'!\x00' + GS + b'!\x00'
    PAPER_CUT = GS + b'V\x00'
    WIDTH = 40
    
    buf = bytearray()
    buf.extend(INIT)
    buf.extend(SELECT_CP850)
    
    # 1. Cabecera oficial del restaurante (GeneralSettings de Aldelo)
    buf.extend(ALIGN_CENTER)
    rest_name = store.get("restaurant_name") or "ALDELO RESTAURANT"
    buf.extend(BOLD_ON + DOUBLE_SIZE)
    buf.extend(_enc(f"{rest_name}\n"))
    buf.extend(NORMAL_SIZE + BOLD_OFF)

    p_addr = store.get("premise_address")
    if p_addr:
        buf.extend(_enc(f"{p_addr}\n"))

    m_addr = store.get("mailing_address")
    if m_addr:
        buf.extend(_enc(f"{m_addr}\n"))

    phone = store.get("phone_number")
    if phone:
        buf.extend(_enc(f"TEL: {phone}\n"))

    buf.extend(ALIGN_LEFT)
    buf.extend(_enc("-" * WIDTH + "\n"))

    # 2. Subtítulo: PRE-CUENTA
    buf.extend(ALIGN_CENTER)
    buf.extend(BOLD_ON)
    buf.extend(_enc("*** PRE-CUENTA ***\n"))
    buf.extend(BOLD_OFF)
    buf.extend(ALIGN_LEFT)
    buf.extend(_enc("-" * WIDTH + "\n"))
    
    # 3. Metadatos de la comanda
    table_text = order.get("table_text", "N/A")
    waiter_name = order.get("waiter_name", "Mesero")
    guests = order.get("guests", 1)
    dt_str = order.get("order_datetime") or ""
    otype = order.get("order_type", "Mesas")

    now = datetime.now()
    date_part = now.strftime("%d/%m/%Y")
    time_part = now.strftime("%I:%M %p")
    if dt_str:
        parts = dt_str.split(" ", 1)
        if len(parts) == 2:
            date_part = parts[0]
            time_part = parts[1]
        else:
            date_part = dt_str

    buf.extend(_enc(_two_col(f"Mesa: {table_text}", f"Personas: {guests}", WIDTH)))
    buf.extend(_enc(_two_col(f"Mesero: {waiter_name}", f"Estacion: {station_id}", WIDTH)))
    buf.extend(_enc(_two_col(f"Orden #: {order_id}", f"Fecha: {date_part}", WIDTH)))
    buf.extend(_enc(_two_col(f"Hora: {time_part}", f"Tipo: {otype}", WIDTH)))

    # 4. Grilla de items oficial de Aldelo
    buf.extend(_enc("=" * WIDTH + "\n"))
    buf.extend(BOLD_ON)
    buf.extend(_enc("CANT  DESCRIPCION                  TOTAL\n"))
    buf.extend(BOLD_OFF)
    buf.extend(_enc("-" * WIDTH + "\n"))
    
    for it in order.get("items", []):
        if it.get("cancelled"):
            continue
        qty = int(it.get("quantity", 1))
        name = (it.get("receipt_name") or it.get("name") or "").strip()
        price = it.get("total", it.get("unit_price", 0.0) * qty)

        qty_s = f" {qty:>2}  "  # 5 chars
        pr_s = f"{price:>8.2f}" # 8 chars
        # 40 - 5 - 8 = 27 caracteres para descripción
        name_first = name[:27]
        buf.extend(_enc(f"{qty_s}{name_first:<27}{pr_s}\n"))
        if len(name) > 27:
            buf.extend(_enc(f"     {name[27:54]}\n"))

        # Modificadores
        for m in it.get("modifiers", []):
            m_name = (m.get("receipt_name") or m.get("name") or "").strip()
            m_cost = float(m.get("cost", 0.0))
            if m_cost > 0:
                m_cost_s = f"{m_cost:>8.2f}"
                m_sub = m_name[:24]
                buf.extend(_enc(f"     - {m_sub:<24}{m_cost_s}\n"))
            else:
                buf.extend(_enc(f"     - {m_name}\n"))
            
    # 5. Totales e Impuesto
    subtotal = float(order.get("subtotal", 0.0))
    tax = float(order.get("tax", 0.0))
    total = float(order.get("total", 0.0))
    tax_rate = float(order.get("tax_rate", store.get("sales_tax_rate", 15.0)))
    
    buf.extend(_enc("-" * WIDTH + "\n"))
    buf.extend(_enc(_two_col("Subtotal:", f"${subtotal:>8.2f}", WIDTH)))
    buf.extend(_enc(_two_col(f"IVA ({tax_rate:.1f}%):", f"${tax:>8.2f}", WIDTH)))
    buf.extend(_enc("=" * WIDTH + "\n"))
    buf.extend(BOLD_ON + DOUBLE_HEIGHT)
    buf.extend(_enc(_two_col("TOTAL:", f"${total:>8.2f}", WIDTH)))
    buf.extend(NORMAL_SIZE + BOLD_OFF)
    buf.extend(_enc("=" * WIDTH + "\n"))

    # 6. Mensaje de cliente configurado en Aldelo (GuestReceiptMessage / Datos para Factura)
    msg = store.get("guest_receipt_message", "")
    if msg:
        for mline in msg.splitlines():
            buf.extend(_enc(f"{mline}\n"))
        buf.extend(_enc("-" * WIDTH + "\n"))

    # 7. Despedida
    buf.extend(ALIGN_CENTER)
    buf.extend(_enc("*** GRACIAS POR SU VISITA ***\n"))
    buf.extend(_enc("* NO VALIDO COMO FACTURA *\n"))
    buf.extend(b"\n\n\n\n")
    buf.extend(PAPER_CUT)
    
    raw_data = bytes(buf)
    local_st = get_station_id()
    target_printer = resolve_target_printer(station_id=local_st, role="receipt")
    
    if not target_printer:
        installed = get_installed_windows_printers()
        if installed:
            target_printer = installed[0]

    if not target_printer:
        print("[print_guest_check] Error: No se encontró ninguna impresora instalada en Windows.")
        return False

    try:
        _send_raw_to_windows(target_printer, raw_data)
        print(f"[print_guest_check] Precuenta impresa exitosamente en '{target_printer}' (Orden #{order_id})")
        return True
    except Exception as e:
        print(f"[print_guest_check] Error imprimiendo en '{target_printer}': {e}")
        # Intento con impresoras de respaldo instaladas
        installed = get_installed_windows_printers()
        for alt in installed:
            if alt != target_printer:
                try:
                    _send_raw_to_windows(alt, raw_data)
                    print(f"[print_guest_check] Precuenta impresa con impresora de respaldo '{alt}'")
                    return True
                except Exception:
                    pass
        return False

def print_receipt_test(station_id: Optional[int] = None) -> Dict[str, Any]:
    if station_id is None:
        station_id = get_station_id()
    from backend import db
    store = db.get_store_settings()
    aldelo_st = get_aldelo_station_printers(station_id)
    r_name = aldelo_st.get("receipt", {}).get("name")
    if not r_name or r_name == "No Printer Attached":
        installed = get_installed_windows_printers()
        if installed:
            r_name = installed[0]
        else:
            return {"success": False, "detail": "No hay impresora de recibos configurada ni instalada"}
            
    ESC = b'\x1b'
    GS = b'\x1d'
    INIT = ESC + b'@'
    SELECT_CP850 = ESC + b't\x02'
    ALIGN_CENTER = ESC + b'a\x01'
    ALIGN_LEFT = ESC + b'a\x00'
    BOLD_ON = ESC + b'E\x01'
    BOLD_OFF = ESC + b'E\x00'
    DOUBLE_SIZE = ESC + b'!\x30' + GS + b'!\x11'
    DOUBLE_HEIGHT = ESC + b'!\x10' + GS + b'!\x01'
    NORMAL_SIZE = ESC + b'!\x00' + GS + b'!\x00'
    PAPER_CUT = GS + b'V\x00'
    WIDTH = 40
    
    buf = bytearray()
    buf.extend(INIT)
    buf.extend(SELECT_CP850)
    buf.extend(ALIGN_CENTER)
    buf.extend(BOLD_ON + DOUBLE_SIZE)
    buf.extend(_enc(f"{store.get('restaurant_name', '21 GRAMOS')}\n"))
    buf.extend(NORMAL_SIZE)
    buf.extend(_enc("*** PRUEBA DE IMPRESION ALDELO ***\n"))
    buf.extend(BOLD_OFF)
    buf.extend(_enc("=" * WIDTH + "\n"))
    buf.extend(ALIGN_LEFT)
    now_str = datetime.now().strftime("%d/%m/%Y %I:%M %p")
    buf.extend(_enc(_two_col(f"Estacion: {station_id}", f"Fecha: {now_str}", WIDTH)))
    buf.extend(_enc(f"Impresora: {r_name}\n"))
    buf.extend(_enc("-" * WIDTH + "\n"))
    buf.extend(_enc("CANT  DESCRIPCION                  TOTAL\n"))
    buf.extend(_enc("-" * WIDTH + "\n"))
    buf.extend(_enc("  1   PLATILLO DE PRUEBA           10.00\n"))
    buf.extend(_enc("  1   BEBIDA DE PRUEBA              2.50\n"))
    buf.extend(_enc("-" * WIDTH + "\n"))
    buf.extend(_enc(_two_col("Subtotal:", "$12.50", WIDTH)))
    tax_r = float(store.get("sales_tax_rate", 15.0))
    tax_v = round(12.50 * (tax_r / 100.0), 2)
    tot_v = round(12.50 + tax_v, 2)
    buf.extend(_enc(_two_col(f"IVA ({tax_r:.1f}%):", f"${tax_v:>8.2f}", WIDTH)))
    buf.extend(_enc("=" * WIDTH + "\n"))
    buf.extend(BOLD_ON + DOUBLE_HEIGHT)
    buf.extend(_enc(_two_col("TOTAL:", f"${tot_v:>8.2f}", WIDTH)))
    buf.extend(NORMAL_SIZE + BOLD_OFF)
    buf.extend(_enc("=" * WIDTH + "\n"))
    buf.extend(ALIGN_CENTER)
    buf.extend(_enc("FORMATO ALDELO CONFIGURADO OK\n\n\n\n"))
    buf.extend(PAPER_CUT)
    
    try:
        _send_raw_to_windows(r_name, bytes(buf))
        return {"success": True, "printer": r_name, "printer_name": r_name}
    except Exception as e:
        return {"success": False, "detail": str(e), "printer": r_name}

def print_table_all_checks(table_id: int) -> int:
    from backend import db
    checks_data = db.get_table_checks(table_id)
    count = 0
    for chk in checks_data.get("checks", []):
        if print_guest_check(chk["order_id"]):
            count += 1
    return count
