from fastapi import APIRouter, HTTPException
from db import get_db
from models import TableCreate, TableUpdate, TableResponse, OrderResponse, OrderItemResponse
from datetime import datetime
from websocket_manager import manager
from typing import Optional
import sqlite3

router = APIRouter()

@router.get("/tables", response_model=list[TableResponse])
async def get_tables(status: Optional[str] = None):
    """Get all tables with optional status filter"""
    db = get_db()
    cursor = db.cursor()
    
    query = "SELECT * FROM tables WHERE 1=1"
    params = []
    if status:
        if status == 'open':
            # For 'open' status, only show tables that are not closed
            query += " AND status != 'closed'"
        else:
            query += " AND status = ?"
            params.append(status)
    query += " ORDER BY table_number"
    
    cursor.execute(query, params)
    tables = cursor.fetchall()
    
    result = []
    for table in tables:
        order = None
        if table["order_id"]:
            # Get order details
            cursor.execute("SELECT * FROM orders WHERE id = ?", (table["order_id"],))
            order_data = cursor.fetchone()
            if order_data:
                cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (table["order_id"],))
                items_data = cursor.fetchall()
                order = OrderResponse(
                    id=order_data["id"],
                    order_number=order_data["order_number"],
                    table_number=order_data["table_number"],
                    status=order_data["status"],
                    total_amount=order_data["total_amount"],
                    created_at=order_data["created_at"],
                    items=[OrderItemResponse(
                        id=item["id"],
                        product_id=item["product_id"],
                        product_name=item["product_name"],
                        quantity=item["quantity"],
                        price=item["price"],
                        total=item["total"],
                        size=item["size"] if "size" in item.keys() else None,
                        additions=item["additions"] if "additions" in item.keys() else None,
                        notes=item["notes"] if "notes" in item.keys() else None
                    ) for item in items_data]
                )
        
        result.append(TableResponse(
            id=table["id"],
            table_number=table["table_number"],
            customer_name=table["customer_name"],
            phone=table["phone"],
            status=table["status"],
            order_id=table["order_id"],
            created_at=table["created_at"],
            updated_at=table["updated_at"],
            playstation_start_time=table["playstation_start_time"] if "playstation_start_time" in table.keys() else None,
            playstation_type=table["playstation_type"] if "playstation_type" in table.keys() else None,
            order=order
        ))
    
    db.close()
    print(f"Returning {len(result)} tables (status filter: {status})")
    return result

@router.get("/tables/{table_number}", response_model=TableResponse)
def get_table(table_number: int):
    """Get a specific table by table number"""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("SELECT * FROM tables WHERE table_number = ?", (table_number,))
    table = cursor.fetchone()
    
    if not table:
        db.close()
        raise HTTPException(status_code=404, detail="Table not found")
    
    order = None
    if table["order_id"]:
        cursor.execute("SELECT * FROM orders WHERE id = ?", (table["order_id"],))
        order_data = cursor.fetchone()
        if order_data:
            cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (table["order_id"],))
            items_data = cursor.fetchall()
            order = OrderResponse(
                id=order_data["id"],
                order_number=order_data["order_number"],
                table_number=order_data["table_number"],
                status=order_data["status"],
                total_amount=order_data["total_amount"],
                created_at=order_data["created_at"],
                items=[OrderItemResponse(
                    id=item["id"],
                    product_id=item["product_id"],
                    product_name=item["product_name"],
                    quantity=item["quantity"],
                    price=item["price"],
                    total=item["total"],
                    size=item["size"] if "size" in item.keys() else None,
                    additions=item["additions"] if "additions" in item.keys() else None,
                    notes=item["notes"] if "notes" in item.keys() else None
                ) for item in items_data]
            )
    
    db.close()
    return TableResponse(
        id=table["id"],
        table_number=table["table_number"],
        customer_name=table["customer_name"],
        phone=table["phone"],
        status=table["status"],
        order_id=table["order_id"],
        created_at=table["created_at"],
        updated_at=table["updated_at"],
        playstation_start_time=table["playstation_start_time"] if "playstation_start_time" in table.keys() else None,
        playstation_type=table["playstation_type"] if "playstation_type" in table.keys() else None,
        order=order
    )

@router.post("/tables", response_model=TableResponse)
async def create_table(table: TableCreate):
    """Create a new table"""
    print(f"Creating table: {table.table_number}, customer: {table.customer_name}, phone: {table.phone}")
    db = get_db()
    try:
        cursor = db.cursor()
        
        # Check if table number already exists with an active order (not completed)
        cursor.execute("SELECT * FROM tables WHERE table_number = ?", (table.table_number,))
        existing = cursor.fetchone()
        if existing:
            # Check if the table has an order that is not completed
            if existing["order_id"]:
                cursor.execute("SELECT * FROM orders WHERE id = ?", (existing["order_id"],))
                order_data = cursor.fetchone()
                if order_data:
                    if order_data["status"] != "completed":
                        db.close()
                        print(f"Table {table.table_number} already exists with active order (status: {order_data['status']})")
                        raise HTTPException(status_code=400, detail=f"الطاولة رقم {table.table_number} موجودة بالفعل وفاتورتها لم تنتهِ")
                    else:
                        # Order is completed but table still exists - this shouldn't happen, but delete it
                        print(f"Table {table.table_number} exists with completed order - deleting old table")
                        cursor.execute("DELETE FROM tables WHERE table_number = ?", (table.table_number,))
                        db.commit()
            else:
                # Table exists but has no order - delete it and create new one
                print(f"Table {table.table_number} exists but has no order - deleting old table")
                cursor.execute("DELETE FROM tables WHERE table_number = ?", (table.table_number,))
                db.commit()
        
        # Create table
        cursor.execute("""
            INSERT INTO tables (table_number, customer_name, phone, status, created_at, updated_at)
            VALUES (?, ?, ?, 'open', datetime('now', 'localtime'), datetime('now', 'localtime'))
        """, (table.table_number, table.customer_name, table.phone))
        table_id = cursor.lastrowid
        
        db.commit()
        print(f"Table created with ID: {table_id}")
        
        # Get created table
        cursor.execute("SELECT * FROM tables WHERE id = ?", (table_id,))
        table_data = cursor.fetchone()
        
        if not table_data:
            db.close()
            raise HTTPException(status_code=500, detail="فشل في إنشاء الطاولة")
        
        result = TableResponse(
            id=table_data["id"],
            table_number=table_data["table_number"],
            customer_name=table_data["customer_name"],
            phone=table_data["phone"],
            status=table_data["status"],
            order_id=table_data["order_id"],
            created_at=table_data["created_at"],
            updated_at=table_data["updated_at"],
            order=None
        )
        
        # Broadcast new table via WebSocket
        try:
            await manager.broadcast({"type": "table_created", "table": result.dict()})
        except Exception as ws_error:
            print(f"WebSocket broadcast error (non-critical): {ws_error}")
        
        db.close()
        print(f"Table created successfully: {result.table_number}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        if db:
            db.close()
        print(f"Error creating table: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"خطأ في إنشاء الطاولة: {str(e)}")

@router.put("/tables/{table_number}", response_model=TableResponse)
async def update_table(table_number: int, table_update: TableUpdate):
    """Update a table"""
    db = get_db()
    try:
        cursor = db.cursor()
        
        # Get existing table
        cursor.execute("SELECT * FROM tables WHERE table_number = ?", (table_number,))
        existing = cursor.fetchone()
        if not existing:
            db.close()
            raise HTTPException(status_code=404, detail="Table not found")
        
        # Update fields
        customer_name = table_update.customer_name if table_update.customer_name is not None else existing["customer_name"]
        phone = table_update.phone if table_update.phone is not None else existing["phone"]
        status = table_update.status if table_update.status is not None else existing["status"]
        order_id = table_update.order_id if table_update.order_id is not None else existing["order_id"]
        
        cursor.execute("""
            UPDATE tables 
            SET customer_name = ?, phone = ?, status = ?, order_id = ?, updated_at = datetime('now', 'localtime')
            WHERE table_number = ?
        """, (customer_name, phone, status, order_id, table_number))
        
        db.commit()
        
        # Get updated table
        cursor.execute("SELECT * FROM tables WHERE table_number = ?", (table_number,))
        table_data = cursor.fetchone()
        
        # Get order if exists
        order = None
        if table_data["order_id"]:
            cursor.execute("SELECT * FROM orders WHERE id = ?", (table_data["order_id"],))
            order_data = cursor.fetchone()
            if order_data:
                cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (table_data["order_id"],))
                items_data = cursor.fetchall()
                order = OrderResponse(
                    id=order_data["id"],
                    order_number=order_data["order_number"],
                    table_number=order_data["table_number"],
                    status=order_data["status"],
                    total_amount=order_data["total_amount"],
                    created_at=order_data["created_at"],
                    items=[OrderItemResponse(
                        id=item["id"],
                        product_id=item["product_id"],
                        product_name=item["product_name"],
                        quantity=item["quantity"],
                        price=item["price"],
                        total=item["total"],
                        size=item["size"] if "size" in item.keys() else None,
                        additions=item["additions"] if "additions" in item.keys() else None,
                        notes=item["notes"] if "notes" in item.keys() else None
                    ) for item in items_data]
                )
        
        result = TableResponse(
            id=table_data["id"],
            table_number=table_data["table_number"],
            customer_name=table_data["customer_name"],
            phone=table_data["phone"],
            status=table_data["status"],
            order_id=table_data["order_id"],
            created_at=table_data["created_at"],
            updated_at=table_data["updated_at"],
            playstation_start_time=table_data["playstation_start_time"] if "playstation_start_time" in table_data.keys() else None,
            playstation_type=table_data["playstation_type"] if "playstation_type" in table_data.keys() else None,
            order=order
        )
        
        # Broadcast update via WebSocket
        await manager.broadcast({"type": "table_updated", "table": result.dict()})
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        db.close()
        print(f"Error updating table: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error updating table: {str(e)}")
    finally:
        if db:
            db.close()

@router.delete("/tables/{table_number}")
async def delete_table(table_number: int):
    """Delete/Close a table"""
    db = get_db()
    try:
        cursor = db.cursor()
        cursor.execute("UPDATE tables SET status = 'closed', updated_at = datetime('now', 'localtime') WHERE table_number = ?", (table_number,))
        if cursor.rowcount == 0:
            db.close()
            raise HTTPException(status_code=404, detail="Table not found")
        db.commit()
        
        # Broadcast table closed via WebSocket
        await manager.broadcast({"type": "table_closed", "table_number": table_number})
        
        return {"message": "Table closed"}
    except HTTPException:
        raise
    except Exception as e:
        db.close()
        print(f"Error closing table: {e}")
        raise HTTPException(status_code=500, detail=f"Error closing table: {str(e)}")

@router.post("/tables/{table_number}/call-waiter")
async def call_waiter(table_number: int):
    """Call waiter for a table - broadcasts notification to tablet"""
    try:
        # Verify table exists
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM tables WHERE table_number = ?", (table_number,))
        table = cursor.fetchone()
        db.close()
        
        if not table:
            raise HTTPException(status_code=404, detail=f"Table {table_number} not found")
        
        # Broadcast order_ready event to all connected clients (especially tablet)
        await manager.broadcast({
            "type": "order_ready",
            "table_number": table_number,
            "message": "طلبك جاهز للاستلام"
        })
        
        return {"message": f"Waiter called for table {table_number}", "table_number": table_number}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error calling waiter: {e}")
        raise HTTPException(status_code=500, detail=f"Error calling waiter: {str(e)}")
    finally:
        if db:
            db.close()

