from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import List, Optional
import os
import uvicorn
from contextlib import asynccontextmanager
from database import init_db, get_db, SyncOrder, SyncInvoice, SyncShift
from sqlalchemy.orm import Session
from dotenv import load_dotenv

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

# --- Dependency ---
def verify_secret(x_sync_secret: str = Header(...)):
    if x_sync_secret != SYNC_SECRET:
        raise HTTPException(status_code=403, detail="Invalid Secret")

# --- Models ---
# Receives raw dict data from local DB
class BatchData(BaseModel):
    table: str
    data: List[dict]

# --- Endpoints ---

@app.get("/")
def read_root():
    return {"status": "online", "service": "Suzz Cloud Backend"}

@app.post("/api/sync/orders", dependencies=[Depends(verify_secret)])
def sync_orders(orders: List[dict], db: Session = Depends(get_db)):
    try:
        count = 0
        for order_data in orders:
            # Check if exists
            local_id = order_data.get('id')
            existing = db.query(SyncOrder).filter(SyncOrder.local_id == local_id).first()
            
            if not existing:
                new_order = SyncOrder(
                    local_id=local_id,
                    order_number=order_data.get('order_number'),
                    total_amount=order_data.get('total_amount'),
                    created_at=order_data.get('created_at'),
                    status=order_data.get('status'),
                    raw_data=order_data # Store full JSON for flexibility
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10000)
