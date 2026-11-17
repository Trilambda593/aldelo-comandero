import os
import socket
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.paths import get_static_dir
from backend import db
from backend import printer

app = FastAPI(title="Aldelo Comandero Móvil API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = get_static_dir()
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
if os.path.exists(os.path.join(STATIC_DIR, "css")):
    app.mount("/css", StaticFiles(directory=os.path.join(STATIC_DIR, "css")), name="css")
if os.path.exists(os.path.join(STATIC_DIR, "js")):
    app.mount("/js", StaticFiles(directory=os.path.join(STATIC_DIR, "js")), name="js")
if os.path.exists(os.path.join(STATIC_DIR, "img")):
    app.mount("/img", StaticFiles(directory=os.path.join(STATIC_DIR, "img")), name="img")

def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

class PinAuthRequest(BaseModel):
    pin: str
    action: Optional[str] = None

class ModifierItem(BaseModel):
    id: int
    name: str
    cost: float = 0.0

class OrderLineItem(BaseModel):
    item_id: int
    name: str
    unit_price: float
    quantity: float = 1.0
    modifiers: List[ModifierItem] = []

class CreateOrderRequest(BaseModel):
    order_id: Optional[int] = None
    table_id: int
    employee_id: int
    guests: int
    items: List[OrderLineItem]

@app.get("/")
def read_root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/manifest.json")
def get_manifest():
    return FileResponse(os.path.join(STATIC_DIR, "manifest.json"), media_type="application/manifest+json")

@app.get("/sw.js")
def get_sw():
    return FileResponse(os.path.join(STATIC_DIR, "sw.js"), media_type="application/javascript")

@app.get("/apple-touch-icon.png")
def get_apple_icon():
    return FileResponse(os.path.join(STATIC_DIR, "img", "apple-touch-icon.png"), media_type="image/png")

@app.get("/api/info")
def get_info():
    ip = get_local_ip()
    tax_rate = db.get_tax_rate()
    db_path = db.get_database_path()
    db_name = os.path.basename(db_path)
    station_id = db.get_station_id()
    return {
        "status": "online",
        "system": "Aldelo POS Bridge",
        "local_ip": ip,
        "tax_rate": tax_rate,
        "station_id": station_id,
        "database_name": db_name,
        "database_path": db_path,
        "mobile_url": f"http://{ip}:8000"
    }

class VoidItemsRequest(BaseModel):
    transaction_ids: List[int]
    items: List[Dict[str, Any]] = []
    notify_kitchen: bool = False
    table_num: str = ""
    waiter_name: str = ""

@app.post("/api/orders/{order_id}/void-items")
def void_items(order_id: int, req: VoidItemsRequest):
    try:
        res = db.void_order_transactions(order_id, req.transaction_ids)
        if req.notify_kitchen and req.items:
            printer.print_cancellation_ticket(req.table_num, req.waiter_name, req.items)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ReduceQtyRequest(BaseModel):
    tx_id: int
    item_name: str = ""
    notify_kitchen: bool = False
    table_num: str = ""
    waiter_name: str = ""

@app.post("/api/orders/{order_id}/reduce-qty")
def reduce_qty(order_id: int, req: ReduceQtyRequest):
    try:
        res = db.reduce_order_transaction_qty(order_id, req.tx_id)
        if req.notify_kitchen:
            printer.print_cancellation_ticket(req.table_num, req.waiter_name, [{"name": req.item_name, "quantity": 1}])
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/pin")
def auth_pin(req: PinAuthRequest):
    try:
        emp = db.verify_pin(req.pin, req.action)
        return {
            "success": True,
            "employee": {
                "id": emp["id"],
                "name": f"{emp['first_name']} {emp['last_name']}".strip(),
                "first_name": emp["first_name"],
                "last_name": emp["last_name"],
                "security_level": emp["security_level"],
                "can_serve": emp["can_serve"],
                "is_manager": emp["security_level"] >= 5
            }
        }
    except ValueError as ve:
        raise HTTPException(status_code=401, detail=str(ve))
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/auth/employees-summary")
def get_employees_summary():
    emps = db.get_employees()
    return [
        {
            "id": e["id"],
            "name": f"{e['first_name']} {e['last_name']}".strip(),
            "first_name": e["first_name"],
            "security_level": e["security_level"],
            "can_serve": e["can_serve"],
            "is_manager": e["security_level"] >= 5
        }
        for e in emps
    ]

@app.get("/api/table-groups")
def get_table_groups():
    return db.get_table_groups()

@app.get("/api/tables")
def get_tables():
    return db.get_tables()

@app.get("/api/menu/groups")
def get_menu_groups():
    return db.get_menu_groups()

@app.get("/api/menu/items")
def get_menu_items(group_id: Optional[int] = Query(None)):
    return db.get_menu_items(group_id)

@app.get("/api/menu/items/{item_id}/modifiers")
def get_modifiers(item_id: int):
    return db.get_item_modifiers(item_id)

@app.get("/api/menu/items/{item_id}/choices")
def get_choices(item_id: int):
    return db.get_item_popup_choices(item_id)

@app.get("/api/recall-orders")
def get_recall_orders(
    type_filter: Optional[str] = Query(None), 
    search: Optional[str] = Query(None),
    search_mode: Optional[str] = Query("account")
):
    return db.get_open_orders(order_type=type_filter, search=search, search_mode=search_mode)

@app.get("/api/orders/{order_id}")
def get_order(order_id: int):
    order = db.get_order_details(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    return order
def get_printers_config():
    cfg = printer.load_printer_config()
    installed = printer.get_installed_windows_printers()
    return {
        "config": cfg,
        "installed_printers": installed
    }

class ReceiptStationItem(BaseModel):
    title: str = "Impresora de recibos"
    name: str = "No Printer Attached"
    type: str = "20006"

class KitchenStationItem(BaseModel):
    id: int
    title: str = ""
    name: str = "No Printer Attached"
    type: str = "20006"

class BarStationItem(BaseModel):
    title: str = "Bar"
    name: str = "No Printer Attached"
    type: str = "20006"

class BackOfficePrinterSaveRequest(BaseModel):
    station_id: Optional[int] = None
    receipt_printer: Optional[ReceiptStationItem] = None
    kitchen_printers: List[KitchenStationItem] = []
    bar_printer: Optional[BarStationItem] = None

@app.get("/api/backoffice/printers")
def get_backoffice_printers(station_id: Optional[int] = Query(None)):
    active_station = db.get_station_id()
    target_station = station_id if station_id is not None else active_station
    aldelo_st = printer.get_aldelo_station_printers(station_id=target_station)
    installed = printer.get_installed_windows_printers()
    available_stations = db.get_all_station_ids()
    presets = [
        {"id": "20015", "name": "Epson TM-T88II/III Large Font Autocut"},
        {"id": "20035", "name": "Epson TM-U200 Large Font Autocut"},
        {"id": "20006", "name": "Epson TM-U200 Small Font Autocut"},
        {"id": "20021", "name": "Epson TM-U200 Small Font"},
        {"id": "20014", "name": "Epson TM-T88 Autocut"},
        {"id": "20001", "name": "Epson Small Font Autocut"},
        {"id": "20002", "name": "Epson TM-T88II/III Large Font Autocut"},
        {"id": "20005", "name": "Epson TM-U200 Small Font"},
        {"id": "20007", "name": "Epson TM-U200 Large Font"},
        {"id": "20008", "name": "Epson TM-U200 Large Font Autocut"},
        {"id": "30001", "name": "Star Micronics Autocut"},
        {"id": "10001", "name": "Generica / Texto Plano ESC-POS"}
    ]
    return {
        "active_station_id": active_station,
        "selected_station_id": target_station,
        "available_stations": available_stations,
        "current": aldelo_st,
        "installed_printers": installed,
        "presets": presets
    }

@app.post("/api/backoffice/printers")
def save_backoffice_printers(req: BackOfficePrinterSaveRequest):
    try:
        k_list = [k.dict() for k in req.kitchen_printers]
        b_dict = req.bar_printer.dict() if req.bar_printer else None
        r_dict = req.receipt_printer.dict() if req.receipt_printer else None
        target_station = req.station_id if req.station_id is not None else db.get_station_id()
        db.update_station_printers(
            kitchen_printers=k_list,
            bar_printer=b_dict,
            receipt_printer=r_dict,
            station_id=target_station
        )
        return {"success": True, "station_id": target_station}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/printers/test-receipt")
def test_receipt_printer(station_id: Optional[int] = Query(None)):
    res = printer.print_receipt_test(station_id=station_id)
    return res

@app.post("/api/printers/config")
def save_printers_config(cfg: Dict[str, Any]):
    printer.save_printer_config(cfg)
    return {"success": True}

@app.post("/api/printers/test")
def test_printers():
    res = printer.print_test_ticket()
    return {"results": res}

@app.get("/api/tables/{table_id}/checks")
def get_table_checks(table_id: int):
    return db.get_table_checks(table_id)

@app.post("/api/orders/{order_id}/print-check")
def print_check(order_id: int):
    success = printer.print_guest_check(order_id)
    return {"success": success}

@app.post("/api/tables/{table_id}/print-all-checks")
def print_all_checks(table_id: int):
    count = printer.print_table_all_checks(table_id)
    return {"success": True, "count": count}

@app.post("/api/orders")
def post_order(req: CreateOrderRequest):
    if not req.items:
        raise HTTPException(status_code=400, detail="La orden no contiene ningún ítem")
    try:
        items_dict = [it.dict() for it in req.items]
        if req.order_id:
            res = db.add_items_to_order(req.order_id, items_dict)
            target_order_id = req.order_id
        else:
            res = db.create_order(
                table_id=req.table_id,
                employee_id=req.employee_id,
                guests=req.guests,
                items=items_dict
            )
            target_order_id = res["order_id"]

        # Trigger automatic kitchen print!
        try:
            det = db.get_order_details(target_order_id)
            table_num = det.get("table_text") if det else str(req.table_id)
            waiter_name = det.get("waiter_name") if det else "Mesero"

            printer.print_ticket(
                target="kitchen",
                table_num=table_num,
                waiter_name=waiter_name,
                guests=req.guests,
                order_id=target_order_id,
                items=items_dict
            )
        except Exception as pe:
            print(f"Non-fatal printer error: {pe}")

        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
