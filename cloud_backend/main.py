from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import uvicorn
from contextlib import asynccontextmanager
from database import init_db, get_db, SyncOrder, SyncInvoice, SyncShift, SyncCategory, SyncProduct, SyncSetting
from sqlalchemy.orm import Session
from sqlalchemy import func
from dotenv import load_dotenv
import datetime

# Load secret from .env if it exists
load_dotenv()

# Secret key for simple authentication
# Ensure this matches the local agent
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
        "pending_orders": len([o for o in all_orders if o.status == 'pending']),
        "total_products": db.query(SyncProduct).count(),
        "total_categories": db.query(SyncCategory).count(),
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
def get_categories(db: Session = Depends(get_db)):
    categories = db.query(SyncCategory).all()
    return [
        {
            "id": c.local_id,
            "name": c.name,
            "created_at": c.raw_data.get('created_at') if c.raw_data else None,
            "updated_at": c.raw_data.get('updated_at') if c.raw_data else None
        } for c in categories
    ]

@app.get("/api/products")
def get_products(db: Session = Depends(get_db)):
    products = db.query(SyncProduct).all()
    return [
        {
            "id": p.local_id,
            "name": p.name,
            "price": p.price,
            "category_id": p.category_id,
            "enabled": p.raw_data.get('enabled', 1) if p.raw_data else 1,
            "sizes": p.raw_data.get('sizes') if p.raw_data else None,
            "created_at": p.raw_data.get('created_at') if p.raw_data else None,
            "updated_at": p.raw_data.get('updated_at') if p.raw_data else None
        } for p in products
    ]

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

@app.get("/api/shifts")
def get_shifts(db: Session = Depends(get_db)):
    shifts = db.query(SyncShift).all()
    shifts_sorted = sorted(shifts, key=lambda x: x.opened_at or "", reverse=True)
    return [
        {
            "id": s.local_id,
            "shift_name": s.shift_name,
            "total_revenue": s.total_revenue,
            "opened_at": s.opened_at,
            "closed_at": s.closed_at,
            "opened_by": s.raw_data.get('opened_by') if s.raw_data else None,
            "closed_by": s.raw_data.get('closed_by') if s.raw_data else None,
            "initial_cash": s.raw_data.get('initial_cash', 0) if s.raw_data else 0
        } for s in shifts_sorted
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
    
@app.post("/api/sync/heartbeat")
def sync_heartbeat(db: Session = Depends(get_db)):
    # Store heartbeat timestamp in settings
    try:
        current_time = datetime.datetime.now().isoformat()
        heartbeat_setting = db.query(SyncSetting).filter(SyncSetting.key == "last_heartbeat").first()
        if heartbeat_setting:
            heartbeat_setting.value = current_time
            heartbeat_setting.updated_at = current_time
        else:
            new_setting = SyncSetting(
                key="last_heartbeat",
                value=current_time,
                updated_at=current_time,
                raw_data={}
            )
            db.add(new_setting)
        db.commit()
        return {"status": "online", "timestamp": current_time}
    except Exception as e:
        print(f"Error saving heartbeat: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/admin/network/status")
def get_connection_status(db: Session = Depends(get_db)):
    try:
        heartbeat_setting = db.query(SyncSetting).filter(SyncSetting.key == "last_heartbeat").first()
        if not heartbeat_setting:
            return {"connected": False, "last_seen": "Never"}
            
        last_heartbeat_str = heartbeat_setting.value
        if not last_heartbeat_str:
            return {"connected": False, "last_seen": "Never"}
            
        last_heartbeat = datetime.datetime.fromisoformat(last_heartbeat_str)
        now = datetime.datetime.now()
        diff = (now - last_heartbeat).total_seconds()
        
        # Consider connected if heartbeat within last 30 seconds (sync interval is 10s)
        is_connected = diff < 30
        
        return {
            "connected": is_connected,
            "last_seen": last_heartbeat_str,
            "seconds_ago": int(diff)
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}

# --- Settings & Auth Stubs ---

@app.post("/api/sync/products", dependencies=[Depends(verify_secret)])
def sync_products(products: List[dict], db: Session = Depends(get_db)):
    try:
        count = 0
        for prod_data in products:
            local_id = prod_data.get('id')
            existing = db.query(SyncProduct).filter(SyncProduct.local_id == local_id).first()
            if existing:
                # Update existing
                existing.name = prod_data.get('name')
                existing.price = prod_data.get('price')
                existing.category_id = prod_data.get('category_id')
                existing.raw_data = prod_data
            else:
                # Create new
                new_prod = SyncProduct(
                    local_id=local_id,
                    name=prod_data.get('name'),
                    price=prod_data.get('price'),
                    category_id=prod_data.get('category_id'),
                    raw_data=prod_data
                )
                db.add(new_prod)
            count += 1
        db.commit()
        return {"status": "success", "synced_count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sync/categories", dependencies=[Depends(verify_secret)])
def sync_categories(categories: List[dict], db: Session = Depends(get_db)):
    try:
        count = 0
        for cat_data in categories:
            local_id = cat_data.get('id')
            existing = db.query(SyncCategory).filter(SyncCategory.local_id == local_id).first()
            if existing:
                existing.name = cat_data.get('name')
                existing.raw_data = cat_data
            else:
                new_cat = SyncCategory(
                    local_id=local_id,
                    name=cat_data.get('name'),
                    raw_data=cat_data
                )
                db.add(new_cat)
            count += 1
        db.commit()
        return {"status": "success", "synced_count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sync/settings", dependencies=[Depends(verify_secret)])
def sync_settings(settings: List[dict], db: Session = Depends(get_db)):
    try:
        count = 0
        for set_data in settings:
            key = set_data.get('key')
            # For settings, key is unique enough, or we check local_id if strictly following others
            # But let's stick to key
            existing = db.query(SyncSetting).filter(SyncSetting.key == key).first()
            if existing:
                existing.value = set_data.get('value')
                existing.updated_at = set_data.get('updated_at')
                existing.raw_data = set_data
            else:
                new_set = SyncSetting(
                    key=key,
                    value=set_data.get('value'),
                    updated_at=set_data.get('updated_at'),
                    raw_data=set_data
                )
                db.add(new_set)
            count += 1
        db.commit()
        return {"status": "success", "synced_count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sync/heartbeat")
def sync_heartbeat():
    # Just a ping to check connection
    return {"status": "online", "timestamp": str(datetime.datetime.now())}

@app.get("/api/auth/passwords")
def get_passwords(db: Session = Depends(get_db)):
    # Try to get from synced settings
    admin_pass = db.query(SyncSetting).filter(SyncSetting.key == "admin_password").first()
    cashier_pass = db.query(SyncSetting).filter(SyncSetting.key == "cashier_password").first()
    
    return {
        "admin_password": admin_pass.value if admin_pass else "Wait for Sync...",
        "cashier_password": cashier_pass.value if cashier_pass else "Wait for Sync..."
    }

@app.get("/api/settings")
def get_settings(db: Session = Depends(get_db)):
    settings_list = db.query(SyncSetting).all()
    settings_dict = {s.key: s.value for s in settings_list}
    
    # Fill defaults if missing
    return {
        "printer_ip": settings_dict.get("printer_ip", ""),
        "restaurant_name": settings_dict.get("restaurant_name", "Suzz Cloud View"),
        "restaurant_address": settings_dict.get("restaurant_address", "Online"),
        "footer_text": settings_dict.get("footer_text", "Powered by Suzz System"),
        "playstation_price_per_hour": settings_dict.get("playstation_price_per_hour", 0),
        "playstation_price_multi": settings_dict.get("playstation_price_multi", 0)
    }

@app.get("/api/settings/discount_permission")
def get_discount_permission():
    return {"has_discount_permission": False}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10000)
