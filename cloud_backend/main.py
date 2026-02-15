from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import uvicorn
from contextlib import asynccontextmanager
from database import init_db, get_db, SyncOrder, SyncInvoice, SyncShift
from sqlalchemy.orm import Session
from sqlalchemy import func
from dotenv import load_dotenv
import datetime

# Load secret from .env if it exists
load_dotenv()

# Secret key for simple authentication
SYNC_SECRET = os.environ.get("SYNC_SECRET", "change_me_to_secure_secret")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    yield
    # Shutdown

app = FastAPI(title="Suzz Cloud Backend", lifespan=lifespan)

# --- Frontend & Static Files ---
# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    return templates.TemplateResponse("admin/index.html", {"request": request})

# --- Dependency ---
def verify_secret(x_sync_secret: str = Header(...)):
    if x_sync_secret != SYNC_SECRET:
        raise HTTPException(status_code=403, detail="Invalid Secret")

# --- Models ---
class BatchData(BaseModel):
    table: str
    data: List[dict]

# --- Sync Endpoints (POST) ---

@app.post("/api/sync/orders", dependencies=[Depends(verify_secret)])
def sync_orders(orders: List[dict], db: Session = Depends(get_db)):
    try:
        count = 0
        for order_data in orders:
            local_id = order_data.get('id')
            existing = db.query(SyncOrder).filter(SyncOrder.local_id == local_id).first()
            if not existing:
                new_order = SyncOrder(
                    local_id=local_id,
                    order_number=order_data.get('order_number'),
                    total_amount=order_data.get('total_amount'),
                    created_at=order_data.get('created_at'),
                    status=order_data.get('status'),
                    raw_data=order_data
                )
                db.add(new_order)
                count += 1
        db.commit()
        return {"status": "success", "synced_count": count}
    except Exception as e:
        print(f"Error syncing orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sync/invoices", dependencies=[Depends(verify_secret)])
def sync_invoices(invoices: List[dict], db: Session = Depends(get_db)):
    try:
        count = 0
        for inv_data in invoices:
            local_id = inv_data.get('id')
            existing = db.query(SyncInvoice).filter(SyncInvoice.local_id == local_id).first()
            if not existing:
                new_inv = SyncInvoice(
                    local_id=local_id,
                    invoice_number=inv_data.get('invoice_number'),
                    total_amount=inv_data.get('total_amount'),
                    created_at=inv_data.get('created_at'),
                    raw_data=inv_data
                )
                db.add(new_inv)
                count += 1
        db.commit()
        return {"status": "success", "synced_count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sync/shifts", dependencies=[Depends(verify_secret)])
def sync_shifts(shifts: List[dict], db: Session = Depends(get_db)):
    try:
        count = 0
        for shift_data in shifts:
            local_id = shift_data.get('id')
            existing = db.query(SyncShift).filter(SyncShift.local_id == local_id).first()
            if not existing:
                new_shift = SyncShift(
                    local_id=local_id,
                    shift_name=shift_data.get('shift_name'),
                    total_revenue=shift_data.get('total_revenue'),
                    opened_at=shift_data.get('opened_at'),
                    closed_at=shift_data.get('closed_at'),
                    raw_data=shift_data
                )
                db.add(new_shift)
                count += 1
        db.commit()
        return {"status": "success", "synced_count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Read-Only APIs for Dashboard (GET) ---

@app.get("/api/admin/network/info")
def get_network_info():
    return {
        "local_ip": "Cloud Server",
        "main_server_url": "YOUR_CLOUD_URL", # Frontend can use window.location
        "tablet_server_url": "YOUR_CLOUD_URL"
    }

@app.get("/api/admin/statistics")
def get_statistics(db: Session = Depends(get_db)):
    now = datetime.datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Simple query implementation 
    # Note: In a real app we'd parse the date strings from SQLite correctly
    # Here we assume created_at is accessible or we fetch all and filter in python for simplicity in this demo
    
    all_orders = db.query(SyncOrder).all()
    
    # Filter for today (assuming ISO string or similar in created_at)
    # This is a bit rough but works for the demo if date format matches
    today_str = today_start.strftime("%Y-%m-%d")
    today_orders = [o for o in all_orders if str(o.created_at).startswith(today_str)]
    
    today_sales = sum(float(o.total_amount or 0) for o in today_orders if o.status != 'cancelled')
    today_count = len(today_orders)
    
    total_revenue = sum(float(o.total_amount or 0) for o in all_orders if o.status != 'cancelled')
    total_count = len(all_orders)
    
    # Recent orders
    recent_orders = sorted(all_orders, key=lambda x: x.created_at or "", reverse=True)[:5]
    
    return {
        "today": {
            "total_sales": today_sales,
            "order_count": today_count
        },
        "all_time": {
            "total_revenue": total_revenue,
            "total_orders": total_count
        },
        "pending_orders": 0,
        "total_products": 0,
        "total_categories": 0,
        "recent_orders": [
            {
                "order_number": o.order_number,
                "table_number": o.raw_data.get('table_number') if o.raw_data else 0,
                "total_amount": o.total_amount,
                "status": o.status,
                "created_at": o.created_at
            } for o in recent_orders
        ],
        "top_products": []
    }

@app.get("/api/categories")
def get_categories():
    return []

@app.get("/api/products")
def get_products():
    return []

@app.get("/api/orders")
def get_orders(limit: int = 50, db: Session = Depends(get_db)):
    orders = db.query(SyncOrder).all()
    # Sort in python as created_at might be string
    orders.sort(key=lambda x: x.created_at or "", reverse=True)
    return [
        {
            "id": o.local_id,
            "order_number": o.order_number,
            "table_number": o.raw_data.get('table_number') if o.raw_data else 0,
            "customer_name": o.raw_data.get('customer_name'),
            "customer_phone": o.raw_data.get('customer_phone'),
            "total_amount": o.total_amount,
            "discount": o.raw_data.get('discount', 0),
            "tax": o.raw_data.get('tax', 0),
            "service": o.raw_data.get('service', 0),
            "status": o.status,
            "branch_name": "Cloud",
            "cashier_name": "Sync",
            "created_at": o.created_at,
            "items": o.raw_data.get('items', []) if o.raw_data else []
        } for o in orders[:limit]
    ]

# --- Reports APIs (Mock/Simple) ---

@app.get("/api/reports/daily")
def get_daily_report(report_date: str = None, db: Session = Depends(get_db)):
    # Simple aggregation for the given date
    if not report_date:
        report_date = datetime.date.today().isoformat()
        
    orders = db.query(SyncOrder).filter(SyncOrder.created_at.startswith(report_date)).all()
    
    total_sales = sum(float(o.total_amount or 0) for o in orders if o.status != 'cancelled')
    order_count = len(orders)
    
    # Best sellers would require parsing item JSON, skipping for now
    
    return {
        "total_sales": total_sales,
        "order_count": order_count,
        "best_sellers": [] 
    }

# --- Settings & Auth Stubs ---

@app.get("/api/auth/passwords")
def get_passwords():
    # Return dummy or environment-configured passwords for cloud view
    # In a real app, these should be secured or not exposed if not needed
    return {
        "admin_password": "cloud_admin_view_only", 
        "cashier_password": "N/A"
    }

@app.get("/api/settings")
def get_settings():
    return {
        "printer_ip": "",
        "restaurant_name": "Suzz Cloud View",
        "restaurant_address": "Online",
        "footer_text": "Powered by Suzz System",
        "playstation_price_per_hour": 0,
        "playstation_price_multi": 0
    }

@app.get("/api/settings/discount_permission")
def get_discount_permission():
    return {"has_discount_permission": False}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10000)
