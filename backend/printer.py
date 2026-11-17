import os
import json
import socket
from datetime import datetime
from typing import Dict, Any, List, Optional
import win32print
import pythoncom
import win32com.client
from backend.db import get_database_path, get_station_id
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
        conn = win32com.client.Dispatch("ADODB.Connection")
        db_path = get_database_path()
        conn.Open(f"Provider=Microsoft.ACE.OLEDB.12.0;Data Source={db_path};Mode=Share Deny None;Persist Security Info=False;")
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

def build_esc_pos_ticket(title: str, table_num: str, waiter_name: str, guests: int, order_id: int, items: List[Dict[str, Any]]) -> bytes:
    ESC = b'\x1b'
    GS = b'\x1d'
    
    INIT = ESC + b'@'
    ALIGN_CENTER = ESC + b'a\x01'
    ALIGN_LEFT = ESC + b'a\x00'
    BOLD_ON = ESC + b'E\x01'
    BOLD_OFF = ESC + b'E\x00'
    DOUBLE_SIZE = GS + b'!\x11'
    NORMAL_SIZE = GS + b'!\x00'
    PAPER_CUT = GS + b'V\x00'
    
    buf = bytearray()
    buf.extend(INIT)
    
    # Header
    buf.extend(ALIGN_CENTER)
    buf.extend(BOLD_ON + DOUBLE_SIZE)
    buf.extend(f"*** {title} ***\n".encode('ascii', 'replace'))
    buf.extend(NORMAL_SIZE + BOLD_OFF)
    buf.extend(b"================================\n")
    
    # Meta
    buf.extend(ALIGN_LEFT)
    buf.extend(BOLD_ON + DOUBLE_SIZE)
    buf.extend(f"MESA: {table_num}\n".encode('ascii', 'replace'))
    buf.extend(NORMAL_SIZE + BOLD_OFF)
    
    now_str = datetime.now().strftime("%d/%m/%Y %I:%M %p")
    buf.extend(f"Mesero: {waiter_name}  Pax: {guests}\n".encode('ascii', 'replace'))
    buf.extend(f"Orden #: {order_id}   Hora: {now_str}\n".encode('ascii', 'replace'))
    buf.extend(b"--------------------------------\n")
    
    # Line items
    for it in items:
        qty = int(it.get('quantity', 1))
        name = it.get('name', '')
        buf.extend(BOLD_ON)
        buf.extend(f"{qty}x {name}\n".encode('ascii', 'replace'))
        buf.extend(BOLD_OFF)
        
        # Modifiers
        mods = it.get('modifiers', [])
        for m in mods:
            m_name = m.get('name', '')
            buf.extend(f"   >> {m_name}\n".encode('ascii', 'replace'))
            
    buf.extend(b"================================\n")
    buf.extend(b"\n\n\n\n")
    buf.extend(PAPER_CUT)
    
    return bytes(buf)

def print_ticket(target: str, table_num: str, waiter_name: str, guests: int, order_id: int, items: List[Dict[str, Any]]) -> bool:
    aldelo_st = get_aldelo_station_printers()
    printed = False

    if target == "kitchen":
        kitchen_list = aldelo_st.get("kitchen", [])
        for kp in kitchen_list:
            p_name = kp.get("name")
            if p_name and p_name != "No Printer Attached":
                try:
                    title_clean = kp.get("title") or f"COCINA #{kp.get('id', 1)}"
                    raw_data = build_esc_pos_ticket(title_clean.upper(), table_num, waiter_name, guests, order_id, items)
                    _send_raw_to_windows(p_name, raw_data)
                    printed = True
                except Exception as e:
                    print(f"Error printing to {kp.get('title')}: {e}")
        return printed
    elif target == "bar":
        b = aldelo_st.get("bar", {})
        p_name = b.get("name")
        if p_name and p_name != "No Printer Attached":
            try:
                raw_data = build_esc_pos_ticket("BARRA", table_num, waiter_name, guests, order_id, items)
                _send_raw_to_windows(p_name, raw_data)
                return True
            except Exception as e:
                print(f"Error printing to bar: {e}")
        return False
        
    return False

def print_cancellation_ticket(table_num: str, waiter_name: str, cancelled_items: List[Dict[str, Any]]) -> bool:
    """Prints a cancellation notification ticket to all attached kitchen printers."""
    ESC = b'\x1b'
    GS = b'\x1d'
    INIT = ESC + b'@'
    ALIGN_CENTER = ESC + b'a\x01'
    ALIGN_LEFT = ESC + b'a\x00'
    BOLD_ON = ESC + b'E\x01'
    BOLD_OFF = ESC + b'E\x00'
    DOUBLE_SIZE = GS + b'!\x11'
    NORMAL_SIZE = GS + b'!\x00'
    PAPER_CUT = GS + b'V\x00'
    
    buf = bytearray()
    buf.extend(INIT)
    buf.extend(ALIGN_CENTER)
    buf.extend(BOLD_ON + DOUBLE_SIZE)
    buf.extend(b"*** ANULACION / CANCELADO ***\n")
    buf.extend(NORMAL_SIZE + BOLD_OFF)
    buf.extend(b"================================\n")
    buf.extend(ALIGN_LEFT)
    buf.extend(BOLD_ON + DOUBLE_SIZE)
    buf.extend(f"MESA: {table_num}\n".encode('ascii', 'replace'))
    buf.extend(NORMAL_SIZE + BOLD_OFF)
    now_str = datetime.now().strftime("%d/%m/%Y %I:%M %p")
    buf.extend(f"Mesero: {waiter_name}  Hora: {now_str}\n".encode('ascii', 'replace'))
    buf.extend(b"--------------------------------\n")
    buf.extend(BOLD_ON)
    for it in cancelled_items:
        qty = int(it.get('quantity', 1))
        name = it.get('name', '')
        buf.extend(f"** CANCELAR: {qty}x {name} **\n".encode('ascii', 'replace'))
    buf.extend(BOLD_OFF)
    buf.extend(b"================================\n\n\n\n")
    buf.extend(PAPER_CUT)
    
    station = get_aldelo_station_printers()
    kitchen_list = station.get("kitchen", [])
    printed = False
    for kp in kitchen_list:
        k_printer = kp.get("name")
        if k_printer and k_printer != "No Printer Attached":
            try:
                _send_raw_to_windows(k_printer, bytes(buf))
                printed = True
            except Exception as e:
                print(f"Error printing cancellation to {kp.get('title')}: {e}")
    return printed

def print_test_ticket() -> Dict[str, Any]:
    sample_items = [
        {"name": "Chx Fillet Sndwch", "quantity": 1, "modifiers": [{"name": "Wheat Bread"}, {"name": "French Fries"}]},
        {"name": "Buffalo Wings", "quantity": 1, "modifiers": []}
    ]
    k_res = print_ticket("kitchen", "TEST-99", "Mesero Prueba", 2, 9999, sample_items)
    b_res = print_ticket("bar", "TEST-99", "Mesero Prueba", 2, 9999, sample_items)
    return {
        "kitchen": "OK" if k_res else "No configurada o sin conectar",
        "bar": "OK" if b_res else "No configurada"
    }

def print_guest_check(order_id: int) -> bool:
    """Prints a pre-bill / guest receipt for the given order_id."""
    from backend import db
    order = db.get_order_details(order_id)
    if not order:
        return False
        
    ESC = b'\x1b'
    GS = b'\x1d'
    INIT = ESC + b'@'
    ALIGN_CENTER = ESC + b'a\x01'
    ALIGN_LEFT = ESC + b'a\x00'
    BOLD_ON = ESC + b'E\x01'
    BOLD_OFF = ESC + b'E\x00'
    DOUBLE_SIZE = GS + b'!\x11'
    NORMAL_SIZE = GS + b'!\x00'
    PAPER_CUT = GS + b'V\x00'
    
    buf = bytearray()
    buf.extend(INIT)
    buf.extend(ALIGN_CENTER)
    buf.extend(BOLD_ON + DOUBLE_SIZE)
    buf.extend(b"ALDELO RESTAURANT\n")
    buf.extend(NORMAL_SIZE)
    buf.extend(b"*** PRE-CUENTA ***\n")
    buf.extend(BOLD_OFF)
    buf.extend(b"================================\n")
    buf.extend(ALIGN_LEFT)
    
    table_text = order.get("table_text", "N/A")
    waiter_name = order.get("waiter_name", "Mesero")
    guests = order.get("guests", 1)
    dt_str = order.get("order_datetime") or datetime.now().strftime("%d/%m/%Y %I:%M %p")
    
    buf.extend(f"Mesa: {table_text:<10} Personas: {guests}\n".encode('ascii', 'replace'))
    buf.extend(f"Mesero: {waiter_name:<10} Estacion: 1\n".encode('ascii', 'replace'))
    buf.extend(f"Orden: #{order_id}\n".encode('ascii', 'replace'))
    buf.extend(f"Fecha: {dt_str}\n".encode('ascii', 'replace'))
    buf.extend(b"--------------------------------\n")
    
    for it in order.get("items", []):
        if it.get("cancelled"):
            continue
        qty = int(it.get("quantity", 1))
        name = it.get("name", "")
        price = it.get("unit_price", 0.0) * qty
        line = f"{qty}x {name:<18} ${price:>6.2f}\n"
        buf.extend(line.encode('ascii', 'replace'))
        for m in it.get("modifiers", []):
            m_name = m.get("name", "")
            buf.extend(f"   {m_name}\n".encode('ascii', 'replace'))
            
    buf.extend(b"--------------------------------\n")
    subtotal = order.get("subtotal", 0.0)
    tax = order.get("tax", 0.0)
    total = order.get("total", 0.0)
    tax_rate = order.get("tax_rate", 15.0)
    
    buf.extend(f"Subtotal:               ${subtotal:>7.2f}\n".encode('ascii', 'replace'))
    buf.extend(f"Impuesto ({tax_rate:.1f}%):        ${tax:>7.2f}\n".encode('ascii', 'replace'))
    buf.extend(BOLD_ON + DOUBLE_SIZE)
    buf.extend(f"TOTAL:      ${total:>7.2f}\n".encode('ascii', 'replace'))
    buf.extend(NORMAL_SIZE + BOLD_OFF)
    buf.extend(b"================================\n")
    buf.extend(ALIGN_CENTER)
    buf.extend(b"Gracias por su visita\n\n\n\n")
    buf.extend(PAPER_CUT)
    
    raw_data = bytes(buf)
    aldelo_st = get_aldelo_station_printers()
    installed = get_installed_windows_printers()
    target_printer = None
    
    # 1. Priorizar impresora de recibos oficial de Aldelo (ReceiptPrinterName)
    r_name = aldelo_st.get("receipt", {}).get("name")
    if r_name and r_name != "No Printer Attached":
        target_printer = r_name
    elif aldelo_st.get("kitchen") and aldelo_st["kitchen"][0].get("name") != "No Printer Attached":
        target_printer = aldelo_st["kitchen"][0]["name"]
    elif installed:
        target_printer = installed[0]
        
    if target_printer:
        try:
            _send_raw_to_windows(target_printer, raw_data)
            return True
        except Exception as e:
            print(f"Error printing guest check: {e}")
            return False
    return False

def print_receipt_test(station_id: Optional[int] = None) -> Dict[str, Any]:
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
    ALIGN_CENTER = ESC + b'a\x01'
    ALIGN_LEFT = ESC + b'a\x00'
    BOLD_ON = ESC + b'E\x01'
    BOLD_OFF = ESC + b'E\x00'
    DOUBLE_SIZE = GS + b'!\x11'
    NORMAL_SIZE = GS + b'!\x00'
    PAPER_CUT = GS + b'V\x00'
    
    buf = bytearray()
    buf.extend(INIT)
    buf.extend(ALIGN_CENTER)
    buf.extend(BOLD_ON + DOUBLE_SIZE)
    buf.extend(b"ALDELO POS\n")
    buf.extend(NORMAL_SIZE)
    buf.extend(b"PRUEBA DE IMPRESORA DE RECIBOS\n")
    buf.extend(BOLD_OFF)
    buf.extend(b"================================\n")
    buf.extend(ALIGN_LEFT)
    now_str = datetime.now().strftime("%d/%m/%Y %I:%M %p")
    st_id = aldelo_st.get("station_id", 1)
    buf.extend(f"Estacion: {st_id}   Fecha: {now_str}\n".encode('ascii', 'replace'))
    buf.extend(f"Impresora: {r_name}\n".encode('ascii', 'replace'))
    buf.extend(b"--------------------------------\n")
    buf.extend(b"1x PLATILLO DE PRUEBA      $10.00\n")
    buf.extend(b"1x BEBIDA DE PRUEBA         $2.50\n")
    buf.extend(b"--------------------------------\n")
    buf.extend(f"Subtotal:                  $12.50\n".encode('ascii', 'replace'))
    buf.extend(f"Impuesto (15%):             $1.88\n".encode('ascii', 'replace'))
    buf.extend(BOLD_ON + DOUBLE_SIZE)
    buf.extend(f"TOTAL:                     $14.38\n".encode('ascii', 'replace'))
    buf.extend(NORMAL_SIZE + BOLD_OFF)
    buf.extend(b"================================\n")
    buf.extend(ALIGN_CENTER)
    buf.extend(b"IMPRESION DE RECIBO CORRECTA\n\n\n\n")
    buf.extend(PAPER_CUT)
    
    try:
        _send_raw_to_windows(r_name, bytes(buf))
        return {"success": True, "printer": r_name}
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
