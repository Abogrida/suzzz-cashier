from fastapi import APIRouter, HTTPException
from db import get_db
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import math

router = APIRouter()

class PlayStationStartRequest(BaseModel):
    table_number: int
    type: str = "single" # single or multi

class PlayStationEndRequest(BaseModel):
    table_number: int
    # price_per_hour override removed or kept optional? Let's keep implicit logic based on type.

@router.post("/playstation/start")
async def start_playstation_session(request: PlayStationStartRequest):
    """Start a PlayStation session for a table"""
    db = get_db()
    try:
        cursor = db.cursor()
        
        # Check if table exists
        cursor.execute("SELECT * FROM tables WHERE table_number = ?", (request.table_number,))
        table = cursor.fetchone()
        
        if not table:
            # Create table if not exists (auto-create)
            cursor.execute("""
                INSERT INTO tables (table_number, status, created_at, updated_at)
                VALUES (?, 'open', datetime('now', 'localtime'), datetime('now', 'localtime'))
            """, (request.table_number,))
            db.commit()
            cursor.execute("SELECT * FROM tables WHERE table_number = ?", (request.table_number,))
            table = cursor.fetchone()
        
        # Check if already started
        if table["playstation_start_time"]:
             raise HTTPException(status_code=400, detail="Session already started for this table")
            
        # Update start time and type
        cursor.execute("""
            UPDATE tables 
            SET playstation_start_time = datetime('now', 'localtime'), 
                playstation_type = ?,
                status = 'open',
                updated_at = datetime('now', 'localtime')
            WHERE table_number = ?
        """, (request.type, request.table_number))
        db.commit()
        
        # Broadcast update
        try:
            from websocket_manager import manager
            # Fetch updated table
            cursor.execute("SELECT * FROM tables WHERE table_number = ?", (request.table_number,))
            updated_table = cursor.fetchone()
            
            # Construct table response dict manually to match TableResponse model
            table_dict = {
                "id": updated_table["id"],
                "table_number": updated_table["table_number"],
                "customer_name": updated_table["customer_name"],
                "phone": updated_table["phone"],
                "status": updated_table["status"],
                "order_id": updated_table["order_id"],
                "created_at": updated_table["created_at"],
                "updated_at": updated_table["updated_at"],
                "playstation_start_time": updated_table["playstation_start_time"],
                "playstation_type": updated_table["playstation_type"]
            }
            
            await manager.broadcast({"type": "table_updated", "table": table_dict})
        except Exception as e:
            print(f"Error broadcasting table update: {e}")

        return {"message": "PlayStation session started", "start_time": updated_table["playstation_start_time"], "type": request.type}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error starting PlayStation session: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if db:
            db.close()

@router.post("/playstation/end")
async def end_playstation_session(request: PlayStationEndRequest):
    """End PlayStation session, calculate cost, and add to order"""
    db = get_db()
    try:
        cursor = db.cursor()
        
        # Get table
        cursor.execute("SELECT * FROM tables WHERE table_number = ?", (request.table_number,))
        table = cursor.fetchone()
        
        if not table:
            raise HTTPException(status_code=404, detail="Table not found")
            
        if not table["playstation_start_time"]:
            raise HTTPException(status_code=400, detail="No active PlayStation session for this table")
            
        # Calculate duration
        start_time_str = table["playstation_start_time"]
        # SQLite datetime format: YYYY-MM-DD HH:MM:SS
        start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
        end_time = datetime.now()
        
        duration_seconds = (end_time - start_time).total_seconds()
        duration_minutes = duration_seconds / 60
        duration_hours = duration_minutes / 60
        
        # Determine price based on type
        ps_type = table["playstation_type"] or "single"
        price_key = "playstation_price_multi" if ps_type == "multi" else "playstation_price_per_hour"
        
        cursor.execute("SELECT value FROM settings WHERE key = ?", (price_key,))
        result = cursor.fetchone()
        price_per_hour = float(result["value"]) if result else (70.0 if ps_type == "multi" else 50.0)

        # Calculate cost
        total_price = duration_hours * price_per_hour
        
        # Create or Get Order
        order_id = table["order_id"]
        if not order_id:
            # Create new order logic (simplified duplication from orders.py for now, ideally refactor)
            # Find next order number
            cursor.execute("SELECT COALESCE(MAX(order_number), 0) + 1 FROM orders")
            order_number = cursor.fetchone()[0]
             
             # Get current shift
            from datetime import date
            today = date.today().isoformat()
            cursor.execute("SELECT id FROM shifts WHERE shift_date = ? AND status = 'open' ORDER BY opened_at DESC LIMIT 1", (today,))
            shift = cursor.fetchone()
            shift_id = shift["id"] if shift else None

            cursor.execute("""
                INSERT INTO orders (order_number, table_number, status, total_amount, branch, cashier, shift_id, created_at)
                VALUES (?, ?, 'pending', 0, 'الفرع الرئيسي', 'كاشير', ?, datetime('now', 'localtime'))
            """, (order_number, request.table_number, shift_id))
            order_id = cursor.lastrowid
            
            # Update table with new order_id
            cursor.execute("UPDATE tables SET order_id = ? WHERE id = ?", (order_id, table["id"]))
        
        # Ensure PlayStation Product exists
        product_name = "وقت بلايستيشن (مالتي)" if ps_type == "multi" else "وقت بلايستيشن"
        cursor.execute("SELECT * FROM products WHERE name = ?", (product_name,))
        ps_product = cursor.fetchone()
        
        if not ps_product:
            # Check for generic one
            cursor.execute("SELECT * FROM products WHERE name = 'وقت بلايستيشن'")
            ps_product = cursor.fetchone()

        if not ps_product:
            # Create dummy category if needed
            cursor.execute("SELECT id FROM categories LIMIT 1")
            cat_result = cursor.fetchone()
            category_id = cat_result["id"] if cat_result else 1 
            
            cursor.execute("""
                INSERT INTO products (name, price, category_id, is_enabled, has_sizes)
                VALUES (?, 0, ?, 0, 0)
            """, (product_name, category_id))
            ps_product_id = cursor.lastrowid
        else:
            ps_product_id = ps_product["id"]
            # Ensure product is hidden from cashier (disabled)
            if ps_product["is_enabled"] != 0:
                cursor.execute("UPDATE products SET is_enabled = 0 WHERE id = ?", (ps_product_id,))

        # Add Item to Order
        hours_int = int(duration_hours)
        minutes_int = int(duration_minutes % 60)
        time_str = f"{hours_int}:{minutes_int:02d}"
        
        item_notes = f"نوع: {ps_type} - الوقت: {time_str}"
        
        cursor.execute("""
            INSERT INTO order_items (order_id, product_id, product_name, quantity, price, total, notes)
            VALUES (?, ?, ?, 1, ?, ?, ?)
        """, (order_id, ps_product_id, product_name, total_price, total_price, item_notes))
        
        # Update Order Total
        cursor.execute("UPDATE orders SET total_amount = total_amount + ? WHERE id = ?", (total_price, order_id))
        
        # Clear PlayStation Session
        cursor.execute("""
            UPDATE tables 
            SET playstation_start_time = NULL,
                playstation_type = NULL,
                updated_at = datetime('now', 'localtime')
            WHERE id = ?
        """, (table["id"],))
        
        db.commit()
        
        # Broadcast Table Update
        try:
            from websocket_manager import manager
            cursor.execute("SELECT * FROM tables WHERE id = ?", (table["id"],))
            updated_table = cursor.fetchone()
             # Construct table response dict
            table_dict = {
                "id": updated_table["id"],
                "table_number": updated_table["table_number"],
                "customer_name": updated_table["customer_name"],
                "phone": updated_table["phone"],
                "status": updated_table["status"],
                "order_id": updated_table["order_id"],
                "created_at": updated_table["created_at"],
                "updated_at": updated_table["updated_at"],
                "playstation_start_time": None,
                 "playstation_type": None
            }
            await manager.broadcast({"type": "table_updated", "table": table_dict})
            
            # Broadcast Order Update 
            # (In a real app, we'd broadcast full order. Here relying on client reload)
            
        except Exception as e:
            print(f"Error broadcasting updates: {e}")

        return {
            "message": "Session ended", 
            "duration_str": time_str, 
            "total_price": total_price,
            "order_id": order_id
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error ending PlayStation session: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if db:
            db.close()
