import os
import sys
import winreg
import pythoncom
import win32com.client
import json
import threading
import functools
from datetime import datetime
import uuid
from typing import List, Dict, Any, Optional

db_lock = threading.RLock()

def with_db_lock(func):
    """Garantiza acceso serializado thread-safe a Microsoft Access para soportar 5, 10 o más tablets concurrentes sin bloqueos ni colisiones OLEDB."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with db_lock:
            return func(*args, **kwargs)
    return wrapper

from backend.paths import get_config_path, get_static_dir, get_app_dir

CONFIG_PATH = get_config_path()
DEFAULT_MDB_PATH = r"C:\ProgramData\Aldelo\Aldelo For Restaurants\Databases\Samples\Standard\adResDemo.mdb"
IMG_BASE_URL = "/static/img"
STATIC_IMG_DIR = os.path.join(get_static_dir(), "img")
IMG_LOOKUP: Dict[str, str] = {}
if os.path.exists(STATIC_IMG_DIR):
    for root, dirs, files in os.walk(STATIC_IMG_DIR):
        for f in files:
            if f.lower().endswith(".png"):
                rel = os.path.relpath(os.path.join(root, f), STATIC_IMG_DIR).replace("\\", "/")
                key = os.path.splitext(f)[0].lower().strip()
                IMG_LOOKUP[key] = f"{IMG_BASE_URL}/{rel}"

def get_aldelo_registry_database_path() -> Optional[str]:
    """Reads the active database path directly from Aldelo Windows Registry in HKCU or HKLM:"""
    subkeys = [
        r"Software\VB and VBA Program Settings\Aldelo For Restaurants\Version 3",
        r"Software\VB and VBA Program Settings\Aldelo For Restaurants\3",
        r"SOFTWARE\WOW6432Node\VB and VBA Program Settings\Aldelo For Restaurants\Version 3",
        r"SOFTWARE\WOW6432Node\VB and VBA Program Settings\Aldelo For Restaurants\3"
    ]
    roots = [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]
    for root in roots:
        for subkey in subkeys:
            try:
                key = winreg.OpenKey(root, subkey)
                val, _ = winreg.QueryValueEx(key, "Data Source")
                winreg.CloseKey(key)
                if val and os.path.exists(str(val).strip()):
                    return str(val).strip()
            except Exception:
                pass
    return None

def get_database_path() -> str:
    # 1. ALWAYS PRIORITIZE the active database configured in Aldelo's Windows Registry!
    reg_path = get_aldelo_registry_database_path()
    if reg_path:
        return reg_path

    # 2. Check config.json override
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                custom = cfg.get("database_path")
                if custom and os.path.exists(custom):
                    return custom
        except Exception:
            pass

    # 3. Check environment variable
    env_path = os.environ.get("ALDELO_DB_PATH")
    if env_path and os.path.exists(env_path):
        return env_path

    # 4. Fallback default
    return DEFAULT_MDB_PATH

def get_aldelo_registry_station_id() -> Optional[int]:
    """Reads the active Station ID directly from Aldelo Windows Registry in HKCU or HKLM."""
    subkeys = [
        r"Software\VB and VBA Program Settings\Aldelo For Restaurants\Version 3",
        r"Software\VB and VBA Program Settings\Aldelo For Restaurants\3",
        r"SOFTWARE\WOW6432Node\VB and VBA Program Settings\Aldelo For Restaurants\Version 3",
        r"SOFTWARE\WOW6432Node\VB and VBA Program Settings\Aldelo For Restaurants\3"
    ]
    roots = [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]
    for root in roots:
        for subkey in subkeys:
            try:
                key = winreg.OpenKey(root, subkey)
                val, _ = winreg.QueryValueEx(key, "Station ID")
                winreg.CloseKey(key)
                if val is not None and str(val).strip() != "":
                    return int(str(val).strip())
            except Exception:
                pass
    return None

def get_station_id() -> int:
    reg_st = get_aldelo_registry_station_id()
    if reg_st is not None:
        return reg_st
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if cfg.get("station_id"):
                    return int(cfg["station_id"])
        except Exception:
            pass
    return 1

@with_db_lock
def get_all_station_ids() -> List[int]:
    """Returns list of all configured stations in StationSettings."""
    try:
        conn = get_connection()
        rs = win32com.client.Dispatch("ADODB.Recordset")
        rs.Open("SELECT StationID FROM StationSettings ORDER BY StationID ASC", conn)
        stations = []
        while not rs.EOF:
            sid = rs.Fields("StationID").Value
            if sid is not None:
                stations.append(int(sid))
            rs.MoveNext()
        rs.Close()
        conn.Close()
        return stations if stations else [1]
    except Exception:
        return [1]

def get_connection():
    pythoncom.CoInitialize()
    conn = win32com.client.Dispatch("ADODB.Connection")
    db_path = get_database_path()
    conn.Open(f"Provider=Microsoft.ACE.OLEDB.12.0;Data Source={db_path};Mode=Share Deny None;Persist Security Info=False;")
    return conn

@with_db_lock
def get_security_setting(setting_name: str, default_level: int = 1) -> int:
    """Reads minimum security level from SecuritySettings table in Aldelo Access database."""
    try:
        conn = get_connection()
        rs = win32com.client.Dispatch("ADODB.Recordset")
        safe_name = setting_name.replace("'", "''")
        rs.Open(f"SELECT MinSecLevel, SecurityEnforced FROM SecuritySettings WHERE SecuritySettingText = '{safe_name}'", conn)
        if not rs.EOF:
            enforced = rs.Fields("SecurityEnforced").Value
            msl = rs.Fields("MinSecLevel").Value
            rs.Close()
            conn.Close()
            if enforced is False:
                return 0
            if msl is not None:
                try:
                    return int(str(msl).strip())
                except Exception:
                    return default_level
            return default_level
        rs.Close()
        conn.Close()
    except Exception as e:
        print(f"[get_security_setting] Note: {e}")
    return default_level

@with_db_lock
def get_employees():
    conn = get_connection()
    rs = win32com.client.Dispatch("ADODB.Recordset")
    rs.Open("SELECT EmployeeID, FirstName, LastName, AccessCode, SecurityLevel, IsAServer, DineInNotAvail FROM EmployeeFiles WHERE EmployeeInActive = False ORDER BY FirstName", conn)
    employees = []
    while not rs.EOF:
        raw_pin = rs.Fields("AccessCode").Value
        pin_str = str(raw_pin).strip() if raw_pin is not None else ""
        if not pin_str:
            rs.MoveNext()
            continue

        sec_raw = rs.Fields("SecurityLevel").Value
        try:
            sec_lvl = int(str(sec_raw).strip()) if sec_raw is not None else 1
        except Exception:
            sec_lvl = 1

        is_server = bool(rs.Fields("IsAServer").Value) if rs.Fields("IsAServer").Value is not None else True
        dine_in_not_avail = bool(rs.Fields("DineInNotAvail").Value) if rs.Fields("DineInNotAvail").Value is not None else False

        employees.append({
            "id": int(rs.Fields("EmployeeID").Value),
            "first_name": str(rs.Fields("FirstName").Value or "").strip(),
            "last_name": str(rs.Fields("LastName").Value or "").strip(),
            "pin": pin_str,
            "security_level": sec_lvl,
            "is_server": is_server,
            "dine_in_not_avail": dine_in_not_avail,
            "can_serve": not dine_in_not_avail
        })
        rs.MoveNext()
    rs.Close()
    conn.Close()
    return employees

@with_db_lock
def verify_pin(pin: str, action: Optional[str] = None) -> Dict[str, Any]:
    pin_clean = str(pin).strip()
    if not pin_clean:
        raise ValueError("Debe ingresar un PIN de acceso")

    employees = get_employees()
    target_emp = None
    for emp in employees:
        if emp["pin"] == pin_clean:
            target_emp = emp
            break

    # Master Admin fallback: si el usuario ingresa PIN "1" (acceso máximo)
    # y no hay un empleado con PIN "1", asociar al Administrador (ID 1 o primer nivel 5)
    if not target_emp and pin_clean == "1":
        target_emp = next((e for e in employees if e.get("id") == 1 and e.get("security_level") == 5), None)
        if not target_emp:
            target_emp = next((e for e in employees if e.get("security_level") == 5), None)

    if not target_emp:
        raise ValueError("Código de acceso incorrecto o mesero no registrado")

    sec_lvl = target_emp.get("security_level", 1)

    if action:
        act = action.lower().strip()
        if act in ["mesas", "dinein", "order", "mesero", "meseros"]:
            min_sec = get_security_setting("Enter New Order", 1)
            if sec_lvl < min_sec:
                raise PermissionError(f"Nivel de seguridad insuficiente ({sec_lvl} < {min_sec}) para acceder a Mesas")
            if target_emp.get("dine_in_not_avail", False):
                raise PermissionError("Acceso al Comedor desactivado para este empleado")

        elif act in ["revisar", "recall", "orders"]:
            min_sec = get_security_setting("Recall Order", 1)
            if sec_lvl < min_sec:
                raise PermissionError(f"Nivel de seguridad insuficiente ({sec_lvl} < {min_sec}) para Revisar Órdenes")

        elif act in ["backoffice", "oficina", "gerente", "manager"]:
            min_sec = get_security_setting("Back Office", 4)
            if sec_lvl < min_sec and sec_lvl < 4:
                raise PermissionError(f"Acceso denegado: Se requiere nivel de Gerente / Administrador ({min_sec})")

        elif act in ["void", "anular"]:
            min_sec = get_security_setting("Void Order", 3)
            if sec_lvl < min_sec:
                raise PermissionError(f"Se requiere nivel de Supervisor ({min_sec}) para anular")

    return target_emp

@with_db_lock
def get_table_groups():
    conn = get_connection()
    rs = win32com.client.Dispatch("ADODB.Recordset")
    rs.Open("SELECT TableGroupID, TableGroupText FROM DineInTableGroups ORDER BY TableGroupID", conn)
    groups = []
    while not rs.EOF:
        groups.append({
            "id": int(rs.Fields("TableGroupID").Value),
            "name": str(rs.Fields("TableGroupText").Value or "").strip()
        })
        rs.MoveNext()
    rs.Close()
    conn.Close()
    return groups

@with_db_lock
def get_tables():
    conn = get_connection()
    # 1. Fetch active orders grouped by table
    rs_ord = win32com.client.Dispatch("ADODB.Recordset")
    rs_ord.Open("SELECT OrderID, DineInTableID, EmployeeID, GuestNumber, SubTotal, AmountDue FROM OrderHeaders WHERE OrderStatus = '1' ORDER BY OrderID ASC", conn)
    active_orders_map = {}
    while not rs_ord.EOF:
        tid = rs_ord.Fields("DineInTableID").Value
        if tid is not None:
            tid = int(tid)
            if tid not in active_orders_map:
                active_orders_map[tid] = []
            active_orders_map[tid].append({
                "order_id": int(rs_ord.Fields("OrderID").Value),
                "employee_id": int(rs_ord.Fields("EmployeeID").Value or 0),
                "guests": int(rs_ord.Fields("GuestNumber").Value or 0),
                "subtotal": float(rs_ord.Fields("SubTotal").Value or 0),
                "total": float(rs_ord.Fields("AmountDue").Value or 0)
            })
        rs_ord.MoveNext()
    rs_ord.Close()

    # 2. Fetch tables
    rs = win32com.client.Dispatch("ADODB.Recordset")
    rs.Open("SELECT DineInTableID, DineInTableText, TableGroupID, DisplayIndex, MaxGuests FROM DineInTables WHERE DineInTableInActive = False ORDER BY DisplayIndex", conn)
    tables = []
    while not rs.EOF:
        tid = int(rs.Fields("DineInTableID").Value)
        disp_idx = int(rs.Fields("DisplayIndex").Value or 1)
        grid_col = (disp_idx - 1) % 9
        grid_row = (disp_idx - 1) // 9
        orders_for_table = active_orders_map.get(tid, [])
        tables.append({
            "id": tid,
            "number": str(rs.Fields("DineInTableText").Value or str(tid)).strip(),
            "group_id": int(rs.Fields("TableGroupID").Value or 1),
            "display_index": disp_idx,
            "grid_row": grid_row,
            "grid_col": grid_col,
            "max_guests": int(rs.Fields("MaxGuests").Value or 4),
            "is_occupied": len(orders_for_table) > 0,
            "order_count": len(orders_for_table),
            "active_orders": orders_for_table,
            "active_order": orders_for_table[0] if orders_for_table else None
        })
        rs.MoveNext()
    rs.Close()
    conn.Close()
    return tables

@with_db_lock
def get_table_checks(table_id: int) -> Dict[str, Any]:
    conn = get_connection()
    # Get table info
    rs_t = win32com.client.Dispatch("ADODB.Recordset")
    rs_t.Open(f"SELECT DineInTableID, DineInTableText FROM DineInTables WHERE DineInTableID = {table_id}", conn)
    table_text = str(rs_t.Fields("DineInTableText").Value or str(table_id)).strip() if not rs_t.EOF else str(table_id)
    rs_t.Close()
    
    # Query all open orders on this table
    rs_o = win32com.client.Dispatch("ADODB.Recordset")
    rs_o.Open(f"SELECT OrderID FROM OrderHeaders WHERE DineInTableID = {table_id} AND OrderStatus = '1' ORDER BY OrderID ASC", conn)
    order_ids = []
    while not rs_o.EOF:
        order_ids.append(int(rs_o.Fields("OrderID").Value))
        rs_o.MoveNext()
    rs_o.Close()
    conn.Close()
    
    total_checks = len(order_ids)
    checks = []
    for idx, oid in enumerate(order_ids):
        det = get_order_details(oid)
        if det:
            det["check_label"] = f"{idx + 1}/{total_checks}"
            det["check_index"] = idx + 1
            det["total_checks"] = total_checks
            checks.append(det)
            
    return {
        "table_id": table_id,
        "table_number": table_text,
        "total_checks": total_checks,
        "checks": checks
    }

def _convert_pic_path(pic_name: Optional[str]) -> Optional[str]:
    if not pic_name:
        return None
    p = pic_name.replace("\\", "/").strip()
    base, _ = os.path.splitext(p)
    key = os.path.basename(base).lower().strip()
    if key in IMG_LOOKUP:
        return IMG_LOOKUP[key]
    return f"{IMG_BASE_URL}/{base}.png"

def _convert_color_to_hex(val: Optional[int]) -> Optional[str]:
    if val is None or val < 0 or val == 11198973:
        return "#0080ff"
    r = val & 0xFF
    g = (val >> 8) & 0xFF
    b = (val >> 16) & 0xFF
    return f"#{r:02x}{g:02x}{b:02x}"

@with_db_lock
def get_menu_groups():
    conn = get_connection()
    rs = win32com.client.Dispatch("ADODB.Recordset")
    rs.Open(
        "SELECT MenuGroupID, MenuGroupText, DisplayIndex, PictureName, ButtonColor "
        "FROM MenuGroups "
        "WHERE MenuGroupInActive = False AND DisplayIndex >= 0 "
        "ORDER BY DisplayIndex ASC, MenuGroupID ASC",
        conn
    )
    groups = []
    while not rs.EOF:
        disp_idx = int(rs.Fields("DisplayIndex").Value or 0)
        btn_col = rs.Fields("ButtonColor").Value
        groups.append({
            "id": int(rs.Fields("MenuGroupID").Value),
            "name": str(rs.Fields("MenuGroupText").Value or "").strip(),
            "display_index": disp_idx,
            "image": _convert_pic_path(rs.Fields("PictureName").Value),
            "color": _convert_color_to_hex(btn_col)
        })
        rs.MoveNext()
    rs.Close()
    conn.Close()
    return groups

@with_db_lock
def get_menu_items(group_id: Optional[int] = None):
    conn = get_connection()
    rs = win32com.client.Dispatch("ADODB.Recordset")
    sql = "SELECT MenuItemID, MenuItemText, MenuGroupID, MenuCategoryID, DisplayIndex, DefaultUnitPrice, PictureName, HasModifierPopUps, MenuItemType, ButtonColor FROM MenuItems WHERE MenuItemInActive = False AND DisplayIndex >= 0"
    if group_id:
        sql += f" AND MenuGroupID = {group_id}"
    sql += " ORDER BY DisplayIndex ASC"
    rs.Open(sql, conn)
    items = []
    while not rs.EOF:
        mtype = int(rs.Fields("MenuItemType").Value or 1)
        disp_idx = int(rs.Fields("DisplayIndex").Value or 0)
        gid = int(rs.Fields("MenuGroupID").Value or 0)
        btn_color = _convert_color_to_hex(rs.Fields("ButtonColor").Value)
        
        # En Aldelo POS, la pantalla de ítems SIEMPRE tiene 4 columnas:
        # Columna: disp_idx % 4 (0, 1, 2, 3)
        # Fila: disp_idx // 4 (0..7)
        grid_row = disp_idx // 4
        grid_col = disp_idx % 4

        items.append({
            "id": int(rs.Fields("MenuItemID").Value),
            "name": str(rs.Fields("MenuItemText").Value or "").strip(),
            "group_id": gid,
            "category_id": int(rs.Fields("MenuCategoryID").Value or 0),
            "price": round(float(rs.Fields("DefaultUnitPrice").Value or 0), 2),
            "image": _convert_pic_path(rs.Fields("PictureName").Value),
            "button_color": btn_color,
            "has_modifiers": bool(rs.Fields("HasModifierPopUps").Value),
            "has_choices": (mtype == 2),
            "display_index": disp_idx,
            "grid_row": grid_row,
            "grid_col": grid_col
        })
        rs.MoveNext()
    rs.Close()
    conn.Close()
    return items

@with_db_lock
def get_item_popup_choices(item_id: int) -> List[Dict[str, Any]]:
    conn = get_connection()
    rs = win32com.client.Dispatch("ADODB.Recordset")
    rs.Open(f"SELECT MenuItemID, MenuItemText, MenuItemPopUpChoiceText, DefaultUnitPrice, PictureName, HasModifierPopUps FROM MenuItems WHERE MenuItemPopUpHeaderID = {item_id} AND MenuItemInActive = False ORDER BY MenuItemID ASC", conn)
    choices = []
    while not rs.EOF:
        choices.append({
            "id": int(rs.Fields("MenuItemID").Value),
            "name": str(rs.Fields("MenuItemText").Value or "").strip(),
            "choice_text": str(rs.Fields("MenuItemPopUpChoiceText").Value or rs.Fields("MenuItemText").Value).strip(),
            "price": round(float(rs.Fields("DefaultUnitPrice").Value or 0), 2),
            "image": _convert_pic_path(rs.Fields("PictureName").Value),
            "has_modifiers": bool(rs.Fields("HasModifierPopUps").Value)
        })
        rs.MoveNext()
    rs.Close()
    conn.Close()
    return choices

@with_db_lock
def get_item_modifiers(item_id: int):
    conn = get_connection()
    rs = win32com.client.Dispatch("ADODB.Recordset")
    sql = f"""
    SELECT mmp.PopUpSequenceOrder, mm.MenuModifierID, mm.MenuModifierText, mm.AdditionalCost
    FROM MenuModifierPopUps mmp
    INNER JOIN MenuModifiers mm ON mmp.MenuModifierID = mm.MenuModifierID
    WHERE mmp.MenuItemID = {item_id} AND mm.MenuModifierInActive = False
    ORDER BY mmp.PopUpSequenceOrder, mm.MenuModifierText
    """
    rs.Open(sql, conn)
    steps_dict = {}
    while not rs.EOF:
        seq = int(rs.Fields("PopUpSequenceOrder").Value or 1)
        if seq not in steps_dict:
            steps_dict[seq] = []
        cost = rs.Fields("AdditionalCost").Value
        steps_dict[seq].append({
            "id": int(rs.Fields("MenuModifierID").Value),
            "name": str(rs.Fields("MenuModifierText").Value or "").strip(),
            "cost": round(float(cost), 2) if cost is not None else 0.0
        })
        rs.MoveNext()
    rs.Close()
    conn.Close()
    
    # Format as list of step groups
    steps = []
    for seq in sorted(steps_dict.keys()):
        steps.append({
            "sequence": seq,
            "title": f"Seleccione Modificador #{seq}",
            "options": steps_dict[seq]
        })
    return steps

@with_db_lock
def get_tax_rate():
    conn = get_connection()
    rs = win32com.client.Dispatch("ADODB.Recordset")
    rs.Open("SELECT TOP 1 SalesTaxRate FROM GeneralSettings", conn)
    rate = float(rs.Fields("SalesTaxRate").Value or 7.5)
    rs.Close()
    conn.Close()
    return rate

@with_db_lock
def create_order(table_id: int, employee_id: int, guests: int, items: List[Dict[str, Any]]):
    conn = get_connection()
    tax_rate = get_tax_rate()
    
    # Calculate subtotal
    subtotal = 0.0
    for item in items:
        unit_price = float(item.get("unit_price", 0))
        qty = float(item.get("quantity", 1))
        mod_cost = sum(float(m.get("cost", 0)) for m in item.get("modifiers", []))
        item_total = (unit_price + mod_cost) * qty
        subtotal += item_total
    
    subtotal = round(subtotal, 2)
    tax_amount = round(subtotal * (tax_rate / 100.0), 2)
    total_due = round(subtotal + tax_amount, 2)
    
    conn.BeginTrans()
    try:
        # 1. Insert into OrderHeaders
        rs_h = win32com.client.Dispatch("ADODB.Recordset")
        rs_h.Open("OrderHeaders", conn, 1, 3, 2)
        rs_h.AddNew()
        now = datetime.now()
        rs_h.Fields("OrderDateTime").Value = now
        rs_h.Fields("EmployeeID").Value = employee_id
        rs_h.Fields("StationID").Value = get_station_id()
        rs_h.Fields("OrderType").Value = "1" # DineIn
        rs_h.Fields("DineInTableID").Value = table_id
        rs_h.Fields("GuestNumber").Value = guests
        rs_h.Fields("SalesTaxRate").Value = tax_rate
        rs_h.Fields("OrderStatus").Value = "1" # Open
        rs_h.Fields("SubTotal").Value = subtotal
        rs_h.Fields("SalesTaxAmountUsed").Value = tax_amount
        rs_h.Fields("AmountDue").Value = total_due
        rs_h.Fields("ParentOrderID").Value = int(now.strftime("%H%M%S")) # unique order tracking number
        rs_h.Fields("Kitchen1AlreadyPrinted").Value = False # Kitchen needs to print this!
        rs_h.Fields("Kitchen2AlreadyPrinted").Value = False
        rs_h.Fields("BarAlreadyPrinted").Value = False
        rs_h.Fields("RowGUID").Value = f"{{{str(uuid.uuid4()).upper()}}}"
        rs_h.Update()
        order_id = int(rs_h.Fields("OrderID").Value)
        rs_h.Close()

        # 2. Insert line items into OrderTransactions
        rs_tx = win32com.client.Dispatch("ADODB.Recordset")
        rs_tx.Open("OrderTransactions", conn, 1, 3, 2)
        for item in items:
            rs_tx.AddNew()
            unit_price = float(item.get("unit_price", 0))
            qty = float(item.get("quantity", 1))
            mods = item.get("modifiers", [])
            mod_cost = sum(float(m.get("cost", 0)) for m in mods)
            ext_price = round((unit_price + mod_cost) * qty, 2)

            rs_tx.Fields("OrderID").Value = order_id
            rs_tx.Fields("MenuItemID").Value = int(item["item_id"])
            rs_tx.Fields("MenuItemUnitPrice").Value = unit_price
            rs_tx.Fields("Quantity").Value = qty
            rs_tx.Fields("ExtendedPrice").Value = ext_price
            rs_tx.Fields("TransactionStatus").Value = "1"
            rs_tx.Fields("NotificationStatus").Value = "2"
            rs_tx.Fields("DiscountTaxable").Value = True
            rs_tx.Fields("RemoteOrigRowID").Value = 1
            rs_tx.Fields("GlobalID").Value = "5"
            rs_tx.Fields("RowVer").Value = "Kitchen"
            rs_tx.Fields("RowGUID").Value = f"{{{str(uuid.uuid4()).upper()}}}"

            # Assign up to 20 modifiers if present
            for idx, m in enumerate(mods[:20]):
                mod_slot = idx + 1
                rs_tx.Fields(f"Mod{mod_slot}ID").Value = int(m["id"])
                rs_tx.Fields(f"Mod{mod_slot}Cost").Value = float(m.get("cost", 0))

            rs_tx.Update()
        rs_tx.Close()

        conn.CommitTrans()
        return {
            "success": True,
            "order_id": order_id,
            "subtotal": subtotal,
            "tax": tax_amount,
            "total": total_due,
            "items_count": len(items)
        }
    except Exception as e:
        conn.RollbackTrans()
        raise e
    finally:
        conn.Close()

@with_db_lock
def add_items_to_order(order_id: int, new_items: List[Dict[str, Any]]):
    """Appends new items to an existing order in OrderTransactions and updates OrderHeaders totals."""
    conn = get_connection()
    tax_rate = get_tax_rate()
    conn.BeginTrans()
    try:
        rs_tx = win32com.client.Dispatch("ADODB.Recordset")
        rs_tx.Open("OrderTransactions", conn, 1, 3, 2)
        for item in new_items:
            rs_tx.AddNew()
            unit_price = float(item.get("unit_price", 0))
            qty = float(item.get("quantity", 1))
            mods = item.get("modifiers", [])
            mod_cost = sum(float(m.get("cost", 0)) for m in mods)
            ext_price = round((unit_price + mod_cost) * qty, 2)

            rs_tx.Fields("OrderID").Value = order_id
            rs_tx.Fields("MenuItemID").Value = int(item["item_id"])
            rs_tx.Fields("MenuItemUnitPrice").Value = unit_price
            rs_tx.Fields("Quantity").Value = qty
            rs_tx.Fields("ExtendedPrice").Value = ext_price
            rs_tx.Fields("TransactionStatus").Value = "1"
            rs_tx.Fields("NotificationStatus").Value = "2"
            rs_tx.Fields("DiscountTaxable").Value = True
            rs_tx.Fields("RemoteOrigRowID").Value = 1
            rs_tx.Fields("GlobalID").Value = "5"
            rs_tx.Fields("RowVer").Value = "Kitchen"
            rs_tx.Fields("RowGUID").Value = f"{{{str(uuid.uuid4()).upper()}}}"

            for idx, m in enumerate(mods[:20]):
                mod_slot = idx + 1
                rs_tx.Fields(f"Mod{mod_slot}ID").Value = int(m["id"])
                rs_tx.Fields(f"Mod{mod_slot}Cost").Value = float(m.get("cost", 0))

            rs_tx.Update()
        rs_tx.Close()

        # Recalculate totals across all active items
        rs_sum = win32com.client.Dispatch("ADODB.Recordset")
        rs_sum.Open(f"SELECT SUM(ExtendedPrice) AS SubTot FROM OrderTransactions WHERE OrderID = {order_id} AND TransactionStatus <> '2'", conn)
        subtotal = round(float(rs_sum.Fields("SubTot").Value or 0.0), 2)
        rs_sum.Close()

        tax_amount = round(subtotal * (tax_rate / 100.0), 2)
        total_due = round(subtotal + tax_amount, 2)

        # Update OrderHeaders
        rs_h = win32com.client.Dispatch("ADODB.Recordset")
        rs_h.Open(f"SELECT * FROM OrderHeaders WHERE OrderID = {order_id}", conn, 1, 3)
        if not rs_h.EOF:
            rs_h.Fields("SubTotal").Value = subtotal
            rs_h.Fields("SalesTaxAmountUsed").Value = tax_amount
            rs_h.Fields("AmountDue").Value = total_due
            rs_h.Fields("Kitchen1AlreadyPrinted").Value = False
            rs_h.Fields("Kitchen2AlreadyPrinted").Value = False
            rs_h.Fields("BarAlreadyPrinted").Value = False
            rs_h.Update()
        rs_h.Close()

        conn.CommitTrans()
        return {
            "success": True,
            "order_id": order_id,
            "subtotal": subtotal,
            "tax": tax_amount,
            "total": total_due,
            "items_added": len(new_items)
        }
    except Exception as e:
        conn.RollbackTrans()
        raise e
    finally:
        conn.Close()
@with_db_lock
def get_open_orders(order_type: Optional[str] = None, search: Optional[str] = None, search_mode: Optional[str] = "account") -> List[Dict[str, Any]]:
    conn = get_connection()
    rs = win32com.client.Dispatch("ADODB.Recordset")
    
    search_clean = str(search).strip() if search else ""
    
    select_fields = """
        oh.OrderID, oh.OrderDateTime, oh.OrderStatus, oh.OrderType, oh.DineInTableID, dt.DineInTableText, 
        oh.EmployeeID, ef.FirstName, ef.LastName, oh.GuestNumber, oh.SubTotal, oh.SalesTaxAmountUsed, oh.AmountDue,
        oh.ParentOrderID
    """
    from_clause = """
    FROM ((OrderHeaders oh
    LEFT JOIN DineInTables dt ON oh.DineInTableID = dt.DineInTableID)
    LEFT JOIN EmployeeFiles ef ON oh.EmployeeID = ef.EmployeeID)
    """
    
    if search_clean:
        # Búsqueda específica: Buscar entre TODAS las órdenes (abiertas y pagadas/cerradas)
        safe_search = search_clean.replace("'", "''")
        if search_mode == "order":
            if safe_search.isdigit():
                search_int = int(safe_search)
                where_clause = f"WHERE (oh.OrderID = {search_int} OR CStr(oh.OrderID) LIKE '%{safe_search}%')"
                order_by = f"ORDER BY IIf(oh.OrderID = {search_int}, 0, 1), oh.OrderID DESC"
            else:
                where_clause = f"WHERE CStr(oh.OrderID) LIKE '%{safe_search}%'"
                order_by = "ORDER BY oh.OrderID DESC"
        else: # "account" mode (default)
            if safe_search.isdigit():
                search_int = int(safe_search)
                where_clause = f"WHERE (oh.OrderID = {search_int} OR oh.ParentOrderID = {search_int} OR oh.DineInTableID = {search_int} OR dt.DineInTableText LIKE '%{safe_search}%' OR CStr(oh.OrderID) LIKE '%{safe_search}%')"
                order_by = f"ORDER BY IIf(oh.OrderID = {search_int} OR oh.ParentOrderID = {search_int}, 0, 1), oh.OrderID DESC"
            else:
                where_clause = f"WHERE (dt.DineInTableText LIKE '%{safe_search}%' OR ef.FirstName LIKE '%{safe_search}%' OR ef.LastName LIKE '%{safe_search}%' OR CStr(oh.OrderID) LIKE '%{safe_search}%')"
                order_by = "ORDER BY oh.OrderID DESC"

        if order_type and order_type != "all":
            where_clause += f" AND oh.OrderType = '{order_type}'"

        sql = f"SELECT TOP 50 {select_fields} {from_clause} {where_clause} {order_by}"
    else:
        # Sin búsqueda: Mostrar ÚNICAMENTE órdenes abiertas (OrderStatus = '1')
        where_clause = "WHERE oh.OrderStatus = '1'"
        if order_type and order_type != "all":
            where_clause += f" AND oh.OrderType = '{order_type}'"
        sql = f"SELECT {select_fields} {from_clause} {where_clause} ORDER BY oh.OrderID DESC"
    
    rs.Open(sql, conn)
    orders = []
    type_map = {
        "1": "Mesas",
        "2": "Bar",
        "3": "Para Llevar",
        "4": "Drive-In",
        "5": "Domicilio"
    }
    status_map = {
        "1": "Abierta",
        "2": "Pagada",
        "3": "Anulada"
    }
    
    now = datetime.now()
    while not rs.EOF:
        oid = int(rs.Fields("OrderID").Value)
        status_code = str(rs.Fields("OrderStatus").Value or "1").strip()
        status_text = status_map.get(status_code, "Cerrada")
        is_paid = (status_code == "2")

        otype = str(rs.Fields("OrderType").Value or "1").strip()
        otype_text = type_map.get(otype, "Mesas")
        tbl_id = rs.Fields("DineInTableID").Value
        t_text = str(rs.Fields("DineInTableText").Value or tbl_id or "").strip()
        fn = str(rs.Fields("FirstName").Value or "").strip()
        ln = str(rs.Fields("LastName").Value or "").strip()
        emp_name = f"{fn} {ln[:1]}".strip() if ln else fn or "Mesero"
        
        subtotal = float(rs.Fields("SubTotal").Value or 0.0)
        tax = float(rs.Fields("SalesTaxAmountUsed").Value or 0.0)
        amt = float(rs.Fields("AmountDue").Value or 0.0)
        if amt == 0.0 and subtotal > 0:
            amt = subtotal + tax

        odt = rs.Fields("OrderDateTime").Value
        parent_oid = rs.Fields("ParentOrderID").Value or 0
        
        time_str = ""
        elapsed_text = "Transcurrido: Nueva"
        if odt:
            try:
                dt_obj = datetime.fromtimestamp(odt.timestamp()) if hasattr(odt, "timestamp") else odt
                time_str = dt_obj.strftime("%I:%M %p").lower().replace("am", "a. m.").replace("pm", "p. m.")
                
                if is_paid:
                    elapsed_text = f"Pagada ({dt_obj.strftime('%d/%m/%Y')})"
                elif status_code == "3":
                    elapsed_text = "Anulada"
                else:
                    diff_min = int((now - dt_obj).total_seconds() // 60)
                    if diff_min <= 5:
                        elapsed_text = "Transcurrido: Nueva"
                    elif diff_min >= 60:
                        hrs = diff_min / 60.0
                        elapsed_text = f"Transcurrido: {hrs:.2f} Hora"
                    else:
                        elapsed_text = f"Transcurrido: {diff_min} Minutos"
            except Exception:
                if is_paid:
                    elapsed_text = "Pagada"
        elif is_paid:
            elapsed_text = "Pagada"

        orders.append({
            "order_id": oid,
            "status_code": status_code,
            "status_text": status_text,
            "is_paid": is_paid,
            "order_type": otype_text,
            "order_type_id": otype,
            "table_id": int(tbl_id) if tbl_id else 0,
            "table": t_text,
            "parent_order_id": parent_oid,
            "waiter": emp_name,
            "amount": round(amt, 2),
            "elapsed": elapsed_text,
            "time": time_str,
            "guests": int(rs.Fields("GuestNumber").Value or 1)
        })
        rs.MoveNext()
        
    rs.Close()

    # Calcular número de cuenta (T# / Track Number) idéntico a Aldelo POS (T#1, T#2, T#3, T#4...)
    open_orders_seq = {}
    try:
        rs_seq = win32com.client.Dispatch("ADODB.Recordset")
        rs_seq.Open("SELECT OrderID FROM OrderHeaders WHERE OrderStatus = '1' ORDER BY OrderID ASC", conn)
        seq_idx = 1
        while not rs_seq.EOF:
            oid_val = int(rs_seq.Fields("OrderID").Value)
            open_orders_seq[oid_val] = seq_idx
            seq_idx += 1
            rs_seq.MoveNext()
        rs_seq.Close()
    except Exception:
        pass

    conn.Close()

    for o in orders:
        oid = o.get("order_id")
        acct = open_orders_seq.get(oid, 1)
        o["account_number"] = acct
        o["total_accounts"] = len(open_orders_seq) if open_orders_seq else 1

    return orders

@with_db_lock
def get_order_details(order_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    rs_h = win32com.client.Dispatch("ADODB.Recordset")
    rs_h.Open(f"""
    SELECT oh.OrderID, oh.OrderDateTime, oh.OrderStatus, oh.OrderType, oh.DineInTableID, dt.DineInTableText, 
           oh.EmployeeID, ef.FirstName, ef.LastName, oh.GuestNumber, oh.SubTotal, oh.SalesTaxRate, oh.SalesTaxAmountUsed, oh.AmountDue
    FROM ((OrderHeaders oh
    LEFT JOIN DineInTables dt ON oh.DineInTableID = dt.DineInTableID)
    LEFT JOIN EmployeeFiles ef ON oh.EmployeeID = ef.EmployeeID)
    WHERE oh.OrderID = {order_id}
    """, conn)
    
    if rs_h.EOF:
        rs_h.Close()
        conn.Close()
        return None
        
    status_code = str(rs_h.Fields("OrderStatus").Value or "1").strip()
    status_map = {"1": "Abierta", "2": "Pagada", "3": "Anulada"}
    status_text = status_map.get(status_code, "Cerrada")
    is_paid = (status_code == "2")

    tax_rate = float(rs_h.Fields("SalesTaxRate").Value or get_tax_rate())
    dt_val = rs_h.Fields("OrderDateTime").Value
    try:
        dt_str = dt_val.strftime("%d/%m/%Y %I:%M %p").lower().replace("am", "a. m.").replace("pm", "p. m.")
    except Exception:
        dt_str = str(dt_val) if dt_val else ""

    otype_raw = str(rs_h.Fields("OrderType").Value or "1").strip()
    type_map = {"1": "Mesas", "2": "Bar", "3": "Para Llevar", "4": "Drive-In", "5": "Domicilio"}
    otype_text = type_map.get(otype_raw, "Mesas")

    fn = str(rs_h.Fields('FirstName').Value or '').strip()
    ln = str(rs_h.Fields('LastName').Value or '').strip()
    waiter_display = f"{fn} {ln[:1]}".strip() if ln else fn or "Oscar"

    subtot = float(rs_h.Fields("SubTotal").Value or 0.0)
    tax_amt = float(rs_h.Fields("SalesTaxAmountUsed").Value or 0.0)
    tot = float(rs_h.Fields("AmountDue").Value or 0.0)
    if tot == 0.0 and subtot > 0:
        tot = subtot + tax_amt

    tbl_id = int(rs_h.Fields("DineInTableID").Value or 0)
    acct_num = 1
    tot_accts = 1
    try:
        rs_chk = win32com.client.Dispatch("ADODB.Recordset")
        rs_chk.Open("SELECT OrderID FROM OrderHeaders WHERE OrderStatus = '1' ORDER BY OrderID ASC", conn)
        open_oids = []
        while not rs_chk.EOF:
            open_oids.append(int(rs_chk.Fields("OrderID").Value))
            rs_chk.MoveNext()
        rs_chk.Close()
        if order_id in open_oids:
            acct_num = open_oids.index(order_id) + 1
            tot_accts = len(open_oids)
    except Exception:
        pass

    order_data = {
        "order_id": int(rs_h.Fields("OrderID").Value),
        "account_number": acct_num,
        "total_accounts": tot_accts,
        "status_code": status_code,
        "status_text": status_text,
        "is_paid": is_paid,
        "order_datetime": dt_str,
        "order_type": otype_text,
        "table_id": tbl_id,
        "table_text": str(rs_h.Fields("DineInTableText").Value or "").strip(),
        "waiter_id": int(rs_h.Fields("EmployeeID").Value or 0),
        "waiter_name": waiter_display,
        "guests": int(rs_h.Fields("GuestNumber").Value or 1),
        "tax_rate": tax_rate,
        "subtotal": round(subtot, 2),
        "tax": round(tax_amt, 2),
        "total": round(tot, 2),
        "items": []
    }
    rs_h.Close()
    
    # Query transactions
    rs_tx = win32com.client.Dispatch("ADODB.Recordset")
    rs_tx.Open(f"""
    SELECT ot.OrderTransactionID, ot.MenuItemID, mi.MenuItemText, ot.MenuItemUnitPrice, ot.Quantity, ot.ExtendedPrice,
           ot.TransactionStatus, ot.Mod1ID, ot.Mod2ID, ot.Mod3ID, ot.Mod4ID
    FROM OrderTransactions ot
    LEFT JOIN MenuItems mi ON ot.MenuItemID = mi.MenuItemID
    WHERE ot.OrderID = {order_id}
    ORDER BY ot.OrderTransactionID
    """, conn)
    
    mod_ids = set()
    raw_txs = []
    while not rs_tx.EOF:
        st = str(rs_tx.Fields("TransactionStatus").Value or "1").strip()
        tx = {
            "tx_id": int(rs_tx.Fields("OrderTransactionID").Value),
            "item_id": int(rs_tx.Fields("MenuItemID").Value),
            "name": str(rs_tx.Fields("MenuItemText").Value or "").strip(),
            "unit_price": float(rs_tx.Fields("MenuItemUnitPrice").Value or 0.0),
            "quantity": float(rs_tx.Fields("Quantity").Value or 1.0),
            "total": float(rs_tx.Fields("ExtendedPrice").Value or 0.0),
            "cancelled": (st == "2"),
            "mods": []
        }
        for i in range(1, 5):
            mid = rs_tx.Fields(f"Mod{i}ID").Value
            if mid:
                mid = int(mid)
                tx["mods"].append(mid)
                mod_ids.add(mid)
        raw_txs.append(tx)
        rs_tx.MoveNext()
    rs_tx.Close()
    
    # Lookup modifier names
    mod_name_map = {}
    if mod_ids:
        mid_list_str = ",".join(str(m) for m in mod_ids)
        rs_m = win32com.client.Dispatch("ADODB.Recordset")
        rs_m.Open(f"SELECT MenuModifierID, MenuModifierText FROM MenuModifiers WHERE MenuModifierID IN ({mid_list_str})", conn)
        while not rs_m.EOF:
            mod_name_map[int(rs_m.Fields("MenuModifierID").Value)] = str(rs_m.Fields("MenuModifierText").Value or "").strip()
            rs_m.MoveNext()
        rs_m.Close()
        
    for tx in raw_txs:
        order_data["items"].append({
            "tx_id": tx["tx_id"],
            "item_id": tx["item_id"],
            "name": tx["name"],
            "unit_price": tx["unit_price"],
            "quantity": tx["quantity"],
            "cancelled": tx["cancelled"],
            "modifiers": [{"id": mid, "name": mod_name_map.get(mid, f"Mod #{mid}")} for mid in tx["mods"]]
        })
        
    conn.Close()
    return order_data

@with_db_lock
def void_order_transactions(order_id: int, transaction_ids: List[int]) -> Dict[str, Any]:
    """Marks specified transaction lines as CANCELLED (TransactionStatus='2') and recalculates totals."""
    conn = get_connection()
    tax_rate = get_tax_rate()
    conn.BeginTrans()
    try:
        for tx_id in transaction_ids:
            conn.Execute(f"UPDATE OrderTransactions SET TransactionStatus = '2', NotificationStatus = '2' WHERE OrderTransactionID = {int(tx_id)} AND OrderID = {int(order_id)}")
        
        # Calculate active subtotal (excluding cancelled lines)
        rs_calc = win32com.client.Dispatch("ADODB.Recordset")
        rs_calc.Open(f"SELECT SUM(ExtendedPrice) AS ActSub FROM OrderTransactions WHERE OrderID = {int(order_id)} AND (TransactionStatus = '1' OR TransactionStatus IS NULL)", conn)
        active_subtotal = float(rs_calc.Fields("ActSub").Value or 0.0)
        rs_calc.Close()
        
        active_subtotal = round(active_subtotal, 2)
        active_tax = round(active_subtotal * (tax_rate / 100.0), 2)
        active_total = round(active_subtotal + active_tax, 2)
        
        conn.Execute(f"""
            UPDATE OrderHeaders 
            SET SubTotal = {active_subtotal}, 
                SalesTaxRate = {tax_rate}, 
                SalesTaxAmountUsed = {active_tax}, 
                AmountDue = {active_total}
            WHERE OrderID = {int(order_id)}
        """)
        conn.CommitTrans()
        conn.Close()
        return {
            "success": True,
            "order_id": order_id,
            "subtotal": active_subtotal,
            "tax": active_tax,
            "total": active_total
        }
    except Exception as e:
        conn.RollbackTrans()
        conn.Close()
        raise e

@with_db_lock
def reduce_order_transaction_qty(order_id: int, tx_id: int) -> Dict[str, Any]:
    """Reduces the quantity of a transaction line by 1; if quantity <= 1, voids it."""
    conn = get_connection()
    tax_rate = get_tax_rate()
    conn.BeginTrans()
    try:
        rs_tx = win32com.client.Dispatch("ADODB.Recordset")
        rs_tx.Open(f"SELECT MenuItemUnitPrice, Quantity, ExtendedPrice, TransactionStatus FROM OrderTransactions WHERE OrderTransactionID = {int(tx_id)} AND OrderID = {int(order_id)}", conn, 1, 3)
        if not rs_tx.EOF:
            qty = float(rs_tx.Fields("Quantity").Value or 1.0)
            uprice = float(rs_tx.Fields("MenuItemUnitPrice").Value or 0.0)
            if qty > 1.0:
                new_qty = qty - 1.0
                new_ext = round(new_qty * uprice, 2)
                rs_tx.Fields("Quantity").Value = new_qty
                rs_tx.Fields("ExtendedPrice").Value = new_ext
                rs_tx.Update()
            else:
                rs_tx.Fields("TransactionStatus").Value = "2"
                rs_tx.Fields("NotificationStatus").Value = "2"
                rs_tx.Update()
        rs_tx.Close()
        
        # Recalculate
        rs_calc = win32com.client.Dispatch("ADODB.Recordset")
        rs_calc.Open(f"SELECT SUM(ExtendedPrice) AS ActSub FROM OrderTransactions WHERE OrderID = {int(order_id)} AND (TransactionStatus = '1' OR TransactionStatus IS NULL)", conn)
        active_subtotal = float(rs_calc.Fields("ActSub").Value or 0.0)
        rs_calc.Close()
        
        active_subtotal = round(active_subtotal, 2)
        active_tax = round(active_subtotal * (tax_rate / 100.0), 2)
        active_total = round(active_subtotal + active_tax, 2)
        
        conn.Execute(f"""
            UPDATE OrderHeaders 
            SET SubTotal = {active_subtotal}, 
                SalesTaxRate = {tax_rate}, 
                SalesTaxAmountUsed = {active_tax}, 
                AmountDue = {active_total}
            WHERE OrderID = {int(order_id)}
        """)
        conn.CommitTrans()
        conn.Close()
        return {
            "success": True,
            "order_id": order_id,
            "subtotal": active_subtotal,
            "tax": active_tax,
            "total": active_total
        }
    except Exception as e:
        conn.RollbackTrans()
        conn.Close()
        raise e
@with_db_lock
def update_station_printers(
    kitchen_printers: List[Dict[str, Any]], 
    bar_printer: Optional[Dict[str, Any]] = None, 
    receipt_printer: Optional[Dict[str, Any]] = None,
    station_id: Optional[int] = None
):
    if station_id is None:
        station_id = get_station_id()
    pythoncom.CoInitialize()
    conn = get_connection()
    rs = win32com.client.Dispatch("ADODB.Recordset")
    rs.Open(f"SELECT * FROM StationSettings WHERE StationID = {station_id}", conn, 1, 3)
    if not rs.EOF:
        # 1. Impresora de recibos
        if receipt_printer:
            r_name = str(receipt_printer.get("name", "") or "").strip()
            r_type = str(receipt_printer.get("type", "") or "").strip()
            rs.Fields("ReceiptPrinterName").Value = r_name if (r_name and r_name != "No Printer Attached") else "No Printer Attached"
            if r_type and r_type != "None":
                try:
                    rs.Fields("ReceiptPrinterType").Value = int(r_type)
                except Exception:
                    pass

        # 2. Impresoras de cocina (1..6)
        for k in kitchen_printers:
            idx = int(k.get("id", 1))
            title = str(k.get("title", "") or "").strip()
            name = str(k.get("name", "") or "").strip()
            ptype = str(k.get("type", "") or "").strip()
            
            rs.Fields(f"KitchenPrinter{idx}Title").Value = title if title else None
            rs.Fields(f"KitchenPrinter{idx}Name").Value = name if (name and name != "No Printer Attached") else "No Printer Attached"
            try:
                rs.Fields(f"KitchenPrinter{idx}Type").Value = int(ptype) if (ptype and ptype != "None") else 20006
            except Exception:
                rs.Fields(f"KitchenPrinter{idx}Type").Value = 20006
                
        # 3. Impresora de barra
        if bar_printer:
            b_name = str(bar_printer.get("name", "") or "").strip()
            b_type = str(bar_printer.get("type", "") or "").strip()
            rs.Fields("BarPrinterName").Value = b_name if (b_name and b_name != "No Printer Attached") else "No Printer Attached"
            try:
                rs.Fields("BarPrinterType").Value = int(b_type) if (b_type and b_type != "None") else 20006
            except Exception:
                rs.Fields("BarPrinterType").Value = 20006
                
        rs.Update()
    rs.Close()
    conn.Close()
    return True
