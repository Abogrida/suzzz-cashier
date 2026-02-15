from fastapi import APIRouter, HTTPException
from db import get_db
from models import OrderCreate, OrderResponse, OrderItemResponse
from datetime import datetime
from websocket_manager import manager
from pydantic import BaseModel
from typing import Optional
import sqlite3

router = APIRouter()

class OrderCompleteRequest(BaseModel):
    payment_method: str = "cash"
    paid_amount: Optional[float] = None
    tip: float = 0.0

@router.get("/orders", response_model=list[OrderResponse])
def get_orders(
    status: Optional[str] = None,
    date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    order_number: Optional[str] = None,
    customer_name: Optional[str] = None,
    customer_phone: Optional[str] = None,
    table_number: Optional[str] = None,
    branch: Optional[str] = None,
    cashier: Optional[str] = None
):
    db = get_db()
    cursor = db.cursor()
    query = "SELECT * FROM orders WHERE 1=1"
    params = []
    
    if status:
        query += " AND status = ?"
        params.append(status)
    if date:
        query += " AND DATE(created_at) = ?"
        params.append(date)
    if start_date:
        query += " AND DATE(created_at) >= ?"
        params.append(start_date)
    if end_date:
        query += " AND DATE(created_at) <= ?"
        params.append(end_date)
    if order_number:
        try:
            order_num_val = int(order_number)
            query += " AND order_number = ?"
            params.append(order_num_val)
        except:
            pass
    if customer_name:
        query += " AND customer_name LIKE ?"
        params.append(f"%{customer_name}%")
    if customer_phone:
        query += " AND customer_phone LIKE ?"
        params.append(f"%{customer_phone}%")
    if table_number:
        try:
            table_num_val = int(table_number)
            query += " AND table_number = ?"
            params.append(table_num_val)
        except:
            pass
    if branch:
        query += " AND branch LIKE ?"
        params.append(f"%{branch}%")
    if cashier:
        query += " AND cashier LIKE ?"
        params.append(f"%{cashier}%")
    
    query += " ORDER BY created_at DESC"
    cursor.execute(query, params)
    orders = cursor.fetchall()
    
    result = []
    for order in orders:
        cursor.execute("""
            SELECT * FROM order_items WHERE order_id = ?
        """, (order["id"],))
        items = cursor.fetchall()
        
        # Safely get values from sqlite3.Row (doesn't support .get())
        table_number = order["table_number"] if "table_number" in order.keys() else 0
        customer_name = order["customer_name"] if "customer_name" in order.keys() and order["customer_name"] else None
        customer_phone = order["customer_phone"] if "customer_phone" in order.keys() and order["customer_phone"] else None
        notes = order["notes"] if "notes" in order.keys() and order["notes"] else None
        invoice_number = order["invoice_number"] if "invoice_number" in order.keys() and order["invoice_number"] else None
        branch = order["branch"] if "branch" in order.keys() and order["branch"] else "الفرع الرئيسي"
        cashier = order["cashier"] if "cashier" in order.keys() and order["cashier"] else "كاشير"
        discount_amount = float(order["discount_amount"]) if "discount_amount" in order.keys() and order["discount_amount"] else 0.0
        tax_amount = float(order["tax_amount"]) if "tax_amount" in order.keys() and order["tax_amount"] else 0.0
        vat_amount = float(order["vat_amount"]) if "vat_amount" in order.keys() and order["vat_amount"] else 0.0
        completed_at = order["completed_at"] if "completed_at" in order.keys() and order["completed_at"] else None
        
        result.append(OrderResponse(
            id=order["id"],
            order_number=order["order_number"],
            table_number=table_number or 0,
            customer_name=customer_name,
            customer_phone=customer_phone,
            notes=notes,
            status=order["status"],
            total_amount=float(order["total_amount"]),
            invoice_number=invoice_number,
            branch=branch,
            cashier=cashier,
            discount_amount=discount_amount,
            tax_amount=tax_amount,
            vat_amount=vat_amount,
            created_at=order["created_at"],
            completed_at=completed_at,
            items=[OrderItemResponse(
                id=item["id"],
                product_id=item["product_id"],
                product_name=item["product_name"],
                quantity=item["quantity"],
                price=item["price"],
                total=item["total"],
                size=item["size"] if "size" in item.keys() and item["size"] else None,
                additions=item["additions"] if "additions" in item.keys() and item["additions"] else None,
                notes=item["notes"] if "notes" in item.keys() and item["notes"] else None
            ) for item in items]
        ))
    db.close()
    return result

@router.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(order_id: int):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        if not order:
            db.close()
            raise HTTPException(status_code=404, detail="Order not found")
        
        cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
        items = cursor.fetchall()
        
        # Process items safely
        processed_items = []
        for item in items:
            try:
                # Safely get values with fallbacks
                item_id = item["id"] if "id" in item.keys() else 0
                product_id = item["product_id"] if "product_id" in item.keys() else 0
                product_name = item["product_name"] if "product_name" in item.keys() else "منتج غير معروف"
                quantity = item["quantity"] if "quantity" in item.keys() else 0
                price = float(item["price"]) if "price" in item.keys() else 0.0
                total = float(item["total"]) if "total" in item.keys() else 0.0
                size = item["size"] if "size" in item.keys() and item["size"] else None
                additions = item["additions"] if "additions" in item.keys() and item["additions"] else None
                notes = item["notes"] if "notes" in item.keys() and item["notes"] else None
                
                processed_items.append(OrderItemResponse(
                    id=item_id,
                    product_id=product_id,
                    product_name=product_name,
                    quantity=quantity,
                    price=price,
                    total=total,
                    size=size,
                    additions=additions,
                    notes=notes
                ))
            except Exception as e:
                item_id_str = item["id"] if "id" in item.keys() else "unknown"
                print(f"Error processing order item {item_id_str}: {e}")
                import traceback
                traceback.print_exc()
                # Skip invalid items but continue processing
                continue
        
        # Safely get order values from sqlite3.Row (doesn't support .get())
        order_id_val = order["id"]
        order_number = order["order_number"]
        table_number = order["table_number"] if "table_number" in order.keys() else 0
        customer_name = order["customer_name"] if "customer_name" in order.keys() and order["customer_name"] else None
        customer_phone = order["customer_phone"] if "customer_phone" in order.keys() and order["customer_phone"] else None
        notes = order["notes"] if "notes" in order.keys() and order["notes"] else None
        status = order["status"]
        total_amount = float(order["total_amount"]) if "total_amount" in order.keys() and order["total_amount"] else 0.0
        invoice_number = order["invoice_number"] if "invoice_number" in order.keys() and order["invoice_number"] else None
        branch = order["branch"] if "branch" in order.keys() and order["branch"] else "الفرع الرئيسي"
        cashier = order["cashier"] if "cashier" in order.keys() and order["cashier"] else "كاشير"
        discount_amount = float(order["discount_amount"]) if "discount_amount" in order.keys() and order["discount_amount"] else 0.0
        tax_amount = float(order["tax_amount"]) if "tax_amount" in order.keys() and order["tax_amount"] else 0.0
        vat_amount = float(order["vat_amount"]) if "vat_amount" in order.keys() and order["vat_amount"] else 0.0
        created_at = order["created_at"]
        completed_at = order["completed_at"] if "completed_at" in order.keys() and order["completed_at"] else None
        
        db.close()
        
        return OrderResponse(
            id=order_id_val,
            order_number=order_number,
            table_number=table_number,
            customer_name=customer_name,
            customer_phone=customer_phone,
            notes=notes,
            status=status,
            total_amount=total_amount,
            invoice_number=invoice_number,
            branch=branch,
            cashier=cashier,
            discount_amount=discount_amount,
            tax_amount=tax_amount,
            vat_amount=vat_amount,
            created_at=created_at,
            completed_at=completed_at,
            items=processed_items
        )
    except HTTPException:
        raise
    except Exception as e:
        db.close()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error loading order: {str(e)}")

@router.post("/orders", response_model=OrderResponse)
async def create_order(order: OrderCreate):
    # Validate order has items
    if not order.items or len(order.items) == 0:
        raise HTTPException(status_code=400, detail="Order must have at least one item")
    
    db = get_db()
    try:
        cursor = db.cursor()
        
        # Get next order number - find the first available number
        # Start from 1 and find the first gap or next number
        order_number = 1
        max_attempts = 1000
        attempt = 0
        
        while attempt < max_attempts:
            # Check if this order number exists
            cursor.execute("SELECT COUNT(*) FROM orders WHERE order_number = ?", (order_number,))
            exists = cursor.fetchone()[0]
            
            if exists == 0:
                # This number is available
                break
            
            # Try next number
            order_number += 1
            attempt += 1
        
        if attempt >= max_attempts:
            # Fallback: use max + 1
            cursor.execute("SELECT COALESCE(MAX(order_number), 0) FROM orders")
            max_order_num_result = cursor.fetchone()[0]
            try:
                max_order_num = int(max_order_num_result) if max_order_num_result is not None else 0
            except (ValueError, TypeError):
                max_order_num = 0
            order_number = max_order_num + 1
        
        # Calculate total
        total_amount = 0
        items_data = []
        for item in order.items:
            cursor.execute("SELECT * FROM products WHERE id = ?", (item.product_id,))
            product = cursor.fetchone()
            if not product:
                raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
            if not product["is_enabled"]:
                raise HTTPException(status_code=400, detail=f"Product {product['name']} is disabled")
            
            # Determine price based on size - use direct access for sqlite3.Row
            try:
                price = float(product["price"])
                if item.size:
                    try:
                        if item.size == 'S':
                            price_s_val = product["price_s"] if "price_s" in product.keys() else None
                            if price_s_val is not None and float(price_s_val) > 0:
                                price = float(price_s_val)
                        elif item.size == 'M':
                            price_m_val = product["price_m"] if "price_m" in product.keys() else None
                            if price_m_val is not None and float(price_m_val) > 0:
                                price = float(price_m_val)
                        elif item.size == 'L':
                            price_l_val = product["price_l"] if "price_l" in product.keys() else None
                            if price_l_val is not None and float(price_l_val) > 0:
                                price = float(price_l_val)
                    except (KeyError, TypeError, ValueError) as e:
                        print(f"Error getting size price: {e}, using default price")
                        # Fallback to default price if size price not available
                        pass
            except (KeyError, TypeError, ValueError) as e:
                raise HTTPException(status_code=400, detail=f"Error getting product price: {str(e)}")
            
            total = price * item.quantity
            total_amount += total
            items_data.append({
                "product_id": item.product_id,
                "product_name": product["name"],
                "quantity": item.quantity,
                "price": price,
                "total": total,
                "size": item.size,  # Include size
                "additions": item.additions if hasattr(item, 'additions') else None,
                "notes": item.notes if hasattr(item, 'notes') else None
            })
        
        # Create order with retry mechanism
        max_retries = 3
        order_id = None
        for attempt in range(max_retries):
            try:
                # Get current shift
                # Get current shift - find ANY open shift regardless of date
                cursor.execute("SELECT id FROM shifts WHERE status = 'open' ORDER BY opened_at DESC LIMIT 1")
                shift = cursor.fetchone()
                shift_id = shift["id"] if shift and "id" in shift.keys() else None
                
                cursor.execute("""
                    INSERT INTO orders (order_number, table_number, customer_name, customer_phone, notes, status, total_amount, branch, cashier, shift_id, created_at)
                    VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, datetime('now', 'localtime'))
                """, (order_number, order.table_number, order.customer_name, getattr(order, 'customer_phone', None), order.notes, total_amount, 'الفرع الرئيسي', 'كاشير', shift_id))
                order_id = cursor.lastrowid
                break
            except sqlite3.IntegrityError as e:
                # UNIQUE constraint failed - order_number already exists, try next number
                if "order_number" in str(e).lower() or "UNIQUE" in str(e).upper():
                    order_number += 1
                    if attempt < max_retries - 1:
                        continue
                    else:
                        raise HTTPException(status_code=500, detail="Failed to create order: unable to find available order number")
                else:
                    raise
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower() and attempt < max_retries - 1:
                    import time
                    time.sleep(0.2 * (attempt + 1))
                    continue
                else:
                    raise
        
        if order_id is None:
            raise HTTPException(status_code=500, detail="Failed to create order after retries")
        
        # Don't create invoice here - invoice will be created only when order is completed
        # Order status remains 'pending' until completed
        
        # Create order items
        for item_data in items_data:
            max_item_retries = 3
            for attempt in range(max_item_retries):
                try:
                    # Check if item already exists in this order (same product_id, size, additions, notes)
                    cursor.execute("""
                        SELECT id, quantity, total FROM order_items 
                        WHERE order_id = ? AND product_id = ? AND size = ? AND additions = ? AND notes = ?
                    """, (order_id, item_data["product_id"], item_data.get("size"), 
                          item_data.get("additions"), item_data.get("notes")))
                    existing_item = cursor.fetchone()

                    if existing_item:
                        # Update quantity and total, and reset is_printed to 0 so it prints again (for kitchen)
                        new_qty = existing_item["quantity"] + item_data["quantity"]
                        new_total = existing_item["total"] + item_data["total"]
                        cursor.execute("UPDATE order_items SET quantity = ?, total = ?, is_printed = 0 WHERE id = ?", 
                                     (new_qty, new_total, existing_item["id"]))
                    else:
                        # Insert new
                        cursor.execute("""
                            INSERT INTO order_items (order_id, product_id, product_name, quantity, price, total, size, additions, notes, is_printed)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                        """, (order_id, item_data["product_id"], item_data["product_name"], 
                              item_data["quantity"], item_data["price"], item_data["total"], 
                              item_data.get("size") if "size" in item_data else None,
                              item_data.get("additions") if "additions" in item_data else None,
                              item_data.get("notes") if "notes" in item_data else None))
                    break
                except sqlite3.OperationalError as e:
                    if "locked" in str(e).lower() and attempt < max_item_retries - 1:
                        import time
                        time.sleep(0.1 * (attempt + 1))
                        continue
                    else:
                        raise
        
        db.commit()
        
        # If order has a table number > 0, update/create table
        if order.table_number > 0:
            try:
                # Check if table exists
                cursor.execute("SELECT * FROM tables WHERE table_number = ?", (order.table_number,))
                existing_table = cursor.fetchone()
                
                if existing_table:
                    # Update existing table with order_id
                    cursor.execute("""
                    UPDATE tables 
                    SET order_id = ?, status = 'open', updated_at = datetime('now', 'localtime')
                    WHERE table_number = ?
                    """, (order_id, order.table_number))
                else:
                    # Create new table
                    cursor.execute("""
                        INSERT INTO tables (table_number, customer_name, status, order_id)
                        VALUES (?, ?, 'open', ?)
                    """, (order.table_number, order.customer_name, order_id))
                
                db.commit()
            except Exception as e:
                print(f"Error updating/creating table: {e}")
                # Continue even if table update fails
        
        # Get full order
        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        order_result = cursor.fetchone()
        cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
        items_result = cursor.fetchall()
        
        # طباعة ريسيت المطبخ تلقائياً للطلبات الجديدة (من التابلت أو الكاشير)
        print_preview_data = None
        try:
            from printing import print_kitchen_receipt
            print_result = print_kitchen_receipt(order_id)
            if isinstance(print_result, dict) and "print_preview" in print_result:
                print_preview_data = print_result["print_preview"]
            
            location_info = f"table {order.table_number}" if order.table_number > 0 else "takeaway"
            print(f"✅ تمت طباعة ريسيت المطبخ تلقائياً لـ {location_info} (طلب #{order_result['order_number']})")
        except Exception as e:
            print(f"⚠️ خطأ في طباعة ريسيت المطبخ: {e}")
            import traceback
            traceback.print_exc()
            # الاستمرار حتى لو فشلت الطباعة - لا تمنع إنشاء الطلب

        order_response = OrderResponse(
            id=order_result["id"],
            order_number=order_result["order_number"],
            table_number=order_result["table_number"],
            status=order_result["status"],
            total_amount=order_result["total_amount"],
            created_at=order_result["created_at"],
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
            ) for item in items_result],
            print_preview=print_preview_data
        )
        
        # Broadcast new order via WebSocket
        await manager.broadcast({"type": "new_order", "order": order_response.dict()})
        
        # If order has table, broadcast table update
        if order.table_number > 0:
            try:
                cursor.execute("SELECT * FROM tables WHERE table_number = ?", (order.table_number,))
                table_data = cursor.fetchone()
                if table_data:
                    await manager.broadcast({
                        "type": "table_updated",
                        "table": {
                            "id": table_data["id"],
                            "table_number": table_data["table_number"],
                            "customer_name": table_data["customer_name"],
                            "phone": table_data["phone"],
                            "status": table_data["status"],
                            "order_id": table_data["order_id"]
                        }
                    })
            except Exception as e:
                print(f"Error broadcasting table update: {e}")
        
        return order_response
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Error creating order: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error creating order: {str(e)}")
    finally:
        if db:
            db.close()

@router.post("/orders/{order_id}/complete")
async def complete_order(order_id: int, payment_data: Optional[OrderCompleteRequest] = None):
    db = get_db()
    try:
        cursor = db.cursor()
        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        cursor.execute("""
            UPDATE orders SET status = 'completed', completed_at = datetime('now', 'localtime')
            WHERE id = ?
        """, (order_id,))
        
        # Get payment info
        payment_method = "cash"
        paid_amount = float(order["total_amount"])
        tip = 0.0
        
        if payment_data:
            payment_method = payment_data.payment_method if payment_data.payment_method else "cash"
            if payment_data.paid_amount is not None:
                paid_amount = float(payment_data.paid_amount)
            if payment_data.tip is not None:
                tip = float(payment_data.tip)
        
        # Store table number before deletion (if it's a table order)
        table_number_to_delete = order["table_number"] if order["table_number"] > 0 else None
        
        # Create invoice when order is completed
        try:
            # Get next invoice number - start from 1 if no invoices exist
            cursor.execute("SELECT COUNT(*) FROM invoices")
            invoices_count = cursor.fetchone()[0]
            
            if invoices_count == 0:
                # No invoices exist - start from 1
                invoice_number = "1"
            else:
                # Get max invoice number (handle both numeric and INV prefix formats)
                cursor.execute("""
                    SELECT COALESCE(MAX(
                        CASE 
                            WHEN invoice_number GLOB '[0-9]*' THEN CAST(invoice_number AS INTEGER)
                            WHEN invoice_number LIKE 'INV%' THEN CAST(SUBSTR(invoice_number, 4) AS INTEGER)
                            ELSE 0
                        END
                    ), 0) FROM invoices
                """)
                max_invoice_num_result = cursor.fetchone()[0]
                # Convert to int (handle both int and string)
                try:
                    max_invoice_num = int(max_invoice_num_result) if max_invoice_num_result is not None else 0
                except (ValueError, TypeError):
                    max_invoice_num = 0
                
                # If max number is too high (likely old data), reset to 1
                if max_invoice_num > 10000:
                    print(f"⚠️  Warning: Max invoice number is {max_invoice_num}, resetting to 1")
                    invoice_number = "1"
                else:
                    # Next invoice number is max + 1
                    next_invoice_num = max_invoice_num + 1
                    invoice_number = str(next_invoice_num)
            
            # Get order items to calculate quantities
            cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
            items = cursor.fetchall()
            total_quantity = sum(item["quantity"] for item in items)
            
            # Get order fields from sqlite3.Row (doesn't support .get())
            customer_phone = order["customer_phone"] if "customer_phone" in order.keys() and order["customer_phone"] else None
            branch = order["branch"] if "branch" in order.keys() and order["branch"] else "الفرع الرئيسي"
            cashier = order["cashier"] if "cashier" in order.keys() and order["cashier"] else "كاشير"
            discount_amount = float(order["discount_amount"]) if "discount_amount" in order.keys() and order["discount_amount"] else 0.0
            tax_amount = float(order["tax_amount"]) if "tax_amount" in order.keys() and order["tax_amount"] else 0.0
            vat_amount = float(order["vat_amount"]) if "vat_amount" in order.keys() and order["vat_amount"] else 0.0
            table_number = order["table_number"] if "table_number" in order.keys() else 0
            customer_name = order["customer_name"] if "customer_name" in order.keys() and order["customer_name"] else None
            
            # Calculate amounts
            total_with_tip = float(order["total_amount"]) + float(tip)
            total_before_vat = total_with_tip - vat_amount - tax_amount - discount_amount
            net_amount = total_with_tip
            
            # Determine invoice location
            invoice_location = "سفری"  # Default: takeaway/delivery
            if table_number > 0:
                invoice_location = f"طاولة {table_number}"
            
            # CRITICAL FIX: Always attribute order to the CURRENT active shift when completing
            # This handles cases where order was created in a previous shift but completed in a new one
            current_shift_id = None
            try:
                cursor.execute("SELECT id FROM shifts WHERE status = 'open' ORDER BY opened_at DESC LIMIT 1")
                current_shift = cursor.fetchone()
                if current_shift:
                    current_shift_id = current_shift["id"]
                    
                    # Update order with new shift_id
                    cursor.execute("UPDATE orders SET shift_id = ? WHERE id = ?", (current_shift_id, order_id))
                    # Update our local order object to reflect only the shift_id change
                    # (we don't need to re-fetch everything, just use the new ID for invoice)
                    print(f"✅ Assigned order {order['order_number']} to current active shift ID: {current_shift_id}")
                else:
                    print(f"⚠️ No active shift found when completing order {order['order_number']}. Keeping original shift ID: {order['shift_id']}")
                    current_shift_id = order["shift_id"]
            except Exception as e:
                print(f"Error updating order shift: {e}")
                current_shift_id = order["shift_id"] if "shift_id" in order.keys() else None

            # Use the determined shift_id (either new active one or original)
            shift_id = current_shift_id
            
            cursor.execute("""
                INSERT INTO invoices (
                    invoice_number, order_id, order_number, table_number, customer_name, customer_phone,
                    invoice_location, quantity, discount_amount, tax_amount, total_before_vat,
                    vat_amount, net_amount, total_amount, status, payment_method, branch, cashier, shift_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'paid', ?, ?, ?, ?)
            """, (
                invoice_number, order["id"], str(order["order_number"]), table_number,
                customer_name, customer_phone, invoice_location, total_quantity,
                discount_amount, tax_amount, total_before_vat, vat_amount, net_amount,
                total_with_tip, payment_method, branch, cashier, shift_id
            ))
            
            # Update order with invoice number if column exists
            try:
                cursor.execute("UPDATE orders SET invoice_number = ? WHERE id = ?", (invoice_number, order_id))
            except:
                pass  # Column might not exist yet
            
            # Printing moved to after commit to ensure data visibility
        except Exception as e:
            print(f"Error creating invoice: {e}")
            import traceback
            traceback.print_exc()
            # Continue even if invoice creation fails
        
        # If order is for a table (table_number > 0), delete the table after invoice is saved
        if table_number_to_delete:
            try:
                print(f"Deleting table {table_number_to_delete} after order completion")
                # Get table info before deletion for broadcast
                cursor.execute("SELECT * FROM tables WHERE table_number = ?", (table_number_to_delete,))
                table_data = cursor.fetchone()
                
                if table_data:
                    # Delete the table (invoice is already saved, so table can be removed)
                    cursor.execute("DELETE FROM tables WHERE table_number = ?", (table_number_to_delete,))
                    print(f"Table {table_number_to_delete} deleted successfully")
                    
                    # Prepare table data for broadcast
                    table_broadcast_data = {
                        "id": table_data["id"],
                        "table_number": table_data["table_number"],
                        "customer_name": table_data["customer_name"],
                        "phone": table_data["phone"],
                        "status": "deleted",
                        "order_id": None
                    }
                else:
                    print(f"Table {table_number_to_delete} not found (may have been already deleted)")
                    table_broadcast_data = None
            except Exception as e:
                print(f"Error deleting table: {e}")
                import traceback
                traceback.print_exc()
                table_broadcast_data = None
                # Continue even if table deletion fails
        
        db.commit()

        # تنفيذ عملية الطباعة الكاملة (فتح الدرج + ريسيت صغير + فاتورة + مطبخ)
        # Must be done AFTER commit so that the new invoice is visible to the printing process
        print_preview_data = None
        try:
            from printing import process_checkout
            # Use a slight delay or retry if needed, but usually commit is enough
            result = process_checkout(order_id)
            if isinstance(result, dict) and "print_preview" in result:
                print_preview_data = result["print_preview"]
                print(f"✅ تمت عملية الطباعة (معاينة المتصفح) للطلب {invoice_number}")
            elif result:
                print(f"✅ تمت عملية الطباعة الكاملة للطلب {invoice_number}")
            else:
                 print(f"⚠️ فشلت عملية الطباعة للطلب {invoice_number}")
        except Exception as e:
            print(f"Error executing checkout printing flow: {e}")
            import traceback
            traceback.print_exc()
        
        # Broadcast table deletion after commit
        if table_number_to_delete and table_broadcast_data:
            try:
                print(f"Broadcasting table_deleted event for table {table_broadcast_data['table_number']}")
                await manager.broadcast({
                    "type": "table_deleted",
                    "table": table_broadcast_data
                })
            except Exception as e:
                print(f"Error broadcasting table_deleted: {e}")
        
        # Get updated order
        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        order_result = cursor.fetchone()
        cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
        items_result = cursor.fetchall()
        
        order_response = OrderResponse(
            id=order_result["id"],
            order_number=order_result["order_number"],
            table_number=order_result["table_number"],
            status=order_result["status"],
            total_amount=order_result["total_amount"],
            invoice_number=invoice_number if invoice_number else order_result["invoice_number"],
            # Note: invoice_number is the one we just generated and saved.
            # But we just verified we select from orders.
            # Actually, we should probably fetch the invoice to be sure, or rely on what we put in DB.
            branch=order_result["branch"],
            cashier=order_result["cashier"],
            discount_amount=order_result["discount_amount"],
            tax_amount=order_result["tax_amount"],
            vat_amount=order_result["vat_amount"],
            created_at=order_result["created_at"],
            completed_at=order_result["completed_at"],
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
            ) for item in items_result],
            print_preview=print_preview_data
        )
        
        # Broadcast order completion
        await manager.broadcast({"type": "order_completed", "order": order_response.dict()})
        
        return order_response
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Error completing order: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error completing order: {str(e)}")
    finally:
        if db:
            db.close()

@router.put("/orders/{order_id}", response_model=OrderResponse)
async def update_order(order_id: int, order: OrderCreate):
    """Update an existing order with new items"""
    db = get_db()
    try:
        cursor = db.cursor()
        
        # Check if order exists
        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        existing_order = cursor.fetchone()
        if not existing_order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        if existing_order["status"] != "pending":
            raise HTTPException(status_code=400, detail="Can only update pending orders")
        
        # Calculate total for new items
        total_amount = float(existing_order["total_amount"])
        items_data = []
        
        for item in order.items:
            cursor.execute("SELECT * FROM products WHERE id = ?", (item.product_id,))
            product = cursor.fetchone()
            if not product:
                raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
            if not product["is_enabled"]:
                raise HTTPException(status_code=400, detail=f"Product {product['name']} is disabled")
            
            # Determine price based on size
            try:
                price = float(product["price"])
                if item.size:
                    try:
                        if item.size == 'S':
                            price_s_val = product["price_s"] if "price_s" in product.keys() else None
                            if price_s_val is not None and float(price_s_val) > 0:
                                price = float(price_s_val)
                        elif item.size == 'M':
                            price_m_val = product["price_m"] if "price_m" in product.keys() else None
                            if price_m_val is not None and float(price_m_val) > 0:
                                price = float(price_m_val)
                        elif item.size == 'L':
                            price_l_val = product["price_l"] if "price_l" in product.keys() else None
                            if price_l_val is not None and float(price_l_val) > 0:
                                price = float(price_l_val)
                    except (KeyError, TypeError, ValueError) as e:
                        print(f"Error getting size price: {e}, using default price")
                        pass
            except (KeyError, TypeError, ValueError) as e:
                raise HTTPException(status_code=400, detail=f"Error getting product price: {str(e)}")
            
            total = price * item.quantity
            total_amount += total
            items_data.append({
                "product_id": item.product_id,
                "product_name": product["name"],
                "quantity": item.quantity,
                "price": price,
                "total": total,
                "size": item.size,  # Include size
                "additions": item.additions if hasattr(item, 'additions') else None,
                "notes": item.notes if hasattr(item, 'notes') else None
            })
        
        # Add new items to order or update existing ones
        for item_data in items_data:
            max_item_retries = 3
            for attempt in range(max_item_retries):
                try:
                    # Check if item exists (same product, size, additions, notes)
                    # We treat NULL and empty string as same for comparison usually, but SQL handles NULL differently
                    # Here we use precise matching.
                    
                    query = """
                        SELECT id, quantity, total FROM order_items 
                        WHERE order_id = ? AND product_id = ? 
                        AND (size IS ? OR size = ?)
                        AND (additions IS ? OR additions = ?)
                        AND (notes IS ? OR notes = ?)
                    """
                    params = (order_id, item_data["product_id"], 
                              item_data.get("size"), item_data.get("size"),
                              item_data.get("additions"), item_data.get("additions"),
                              item_data.get("notes"), item_data.get("notes"))
                              
                    cursor.execute(query, params)
                    existing_item = cursor.fetchone()
                    
                    if existing_item:
                        # Update quantity and total
                        new_qty = existing_item["quantity"] + item_data["quantity"]
                        new_total = existing_item["total"] + item_data["total"]
                        cursor.execute("UPDATE order_items SET quantity = ?, total = ? WHERE id = ?", 
                                     (new_qty, new_total, existing_item["id"]))
                        # Also mark as not printed if we want to reprint kitchen ticket for new qty?
                        # The kitchen logic handles printing by checking new items or we need to handle "delta" printing separately.
                        # The print_kitchen_receipt logic checks for unprinted items. 
                        # If we update an existing printed item, it remains "printed".
                        # We might need to mark it as unprinted or handle partial printing.
                        # For now, let's keep it simple: Update quantity. 
                        # Kitchen print logic usually prints NEW items passed to it, or checks unprinted.
                        # If we update quantity, we might miss printing the extra quantity if we rely on "is_printed" flag of the row.
                        # But wait, existing logic prints based on "new_items" passed to API or unprinted rows.
                        # If we merge, we lose the "unprinted" status of the NEW part.
                        
                        # Fix: If we merge, we should probably set is_printed=0 so it picked up? 
                        # But then it reprints the WHOLE quantity.
                        # Ideally, we should insert a NEW row if we want track printing separately?
                        # But user complained about "Ghost Items" (duplicates).
                        # Ghost item usually means I have "Burger" and "Burger".
                        # Merging is cleaner for the Invoice.
                        # For Kitchen, we might need to handle it.
                        
                        # Let's stick to merging to fix the "Ghost Item" invoice issue first.
                        pass
                    else:
                        # Insert new
                        cursor.execute("""
                            INSERT INTO order_items (order_id, product_id, product_name, quantity, price, total, size, additions, notes, is_printed)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                        """, (order_id, item_data["product_id"], item_data["product_name"], 
                              item_data["quantity"], item_data["price"], item_data["total"], 
                              item_data.get("size") if "size" in item_data else None,
                              item_data.get("additions") if "additions" in item_data else None,
                              item_data.get("notes") if "notes" in item_data else None))
                    
                    break
                except sqlite3.OperationalError as e:
                    if "locked" in str(e).lower() and attempt < max_item_retries - 1:
                        import time
                        time.sleep(0.1 * (attempt + 1))
                        continue
                    else:
                        raise
        
        # Update order total
        cursor.execute("UPDATE orders SET total_amount = ? WHERE id = ?", (total_amount, order_id))
        
        # If order is for a table, update table's updated_at timestamp to reflect real-time
        if existing_order["table_number"] > 0:
            try:
                cursor.execute("""
                    UPDATE tables 
                    SET updated_at = datetime('now', 'localtime')
                    WHERE table_number = ?
                """, (existing_order["table_number"],))
                print(f"Updated table {existing_order['table_number']} timestamp after order update")
            except Exception as e:
                print(f"Error updating table timestamp: {e}")
        
        # طباعة ريسيت المطبخ للمنتجات الجديدة فقط (من التابلت أو الكاشير)
        # Printing moved to after commit
        
        db.commit()
        
        # طباعة ريسيت المطبخ للمنتجات الجديدة فقط (بعد الحفظ لضمان ظهورها)
        print_preview_data = None
        if items_data:
            try:
                from printing import print_kitchen_receipt
                # We need to pass the new items explicitly because if they were merged with existing items,
                # they won't be flagged as 'is_printed=0', so the printer would skip them.
                # items_data IS ALREADY a list of dicts (based on usage above), so passing it directly.
                
                # Call print with new_items_only to force printing this batch
                print_result = print_kitchen_receipt(order_id, new_items_only=items_data)
                
                if isinstance(print_result, dict) and "print_preview" in print_result:
                   # print_preview_data = print_result["print_preview"]
                   pass
                
                print(f"✅ تمت طباعة ريسيت المطبخ للمنتجات الجديدة (طلب #{existing_order['order_number']})")
            except Exception as e:
                print(f"⚠️ خطأ في طباعة ريسيت المطبخ للمنتجات الجديدة: {e}")
                import traceback
                traceback.print_exc()
        
        # Get updated order
        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        order_result = cursor.fetchone()
        cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
        items_result = cursor.fetchall()
        
        order_response = OrderResponse(
            id=order_result["id"],
            order_number=order_result["order_number"],
            table_number=order_result["table_number"],
            status=order_result["status"],
            total_amount=order_result["total_amount"],
            created_at=order_result["created_at"],
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
            ) for item in items_result],
            print_preview=print_preview_data
        )
        
        # Broadcast order update
        await manager.broadcast({"type": "order_updated", "order": order_response.dict()})
        
        # Note: Printing is already handled above for new items only
        
        # If order has table, broadcast table update
        if order_result["table_number"] > 0:
            try:
                cursor.execute("SELECT * FROM tables WHERE table_number = ?", (order_result["table_number"],))
                table_data = cursor.fetchone()
                if table_data:
                    await manager.broadcast({
                        "type": "table_updated",
                        "table": {
                            "id": table_data["id"],
                            "table_number": table_data["table_number"],
                            "customer_name": table_data["customer_name"],
                            "phone": table_data["phone"],
                            "status": table_data["status"],
                            "order_id": table_data["order_id"]
                        }
                    })
            except Exception as e:
                print(f"Error broadcasting table update: {e}")
        
        return order_response
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Error updating order: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error updating order: {str(e)}")
    finally:
        if db:
            db.close()

@router.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: int):
    db = get_db()
    try:
        cursor = db.cursor()
        cursor.execute("UPDATE orders SET status = 'cancelled' WHERE id = ?", (order_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Order not found")
        db.commit()
        
        # Broadcast order cancellation
        await manager.broadcast({"type": "order_cancelled", "order_id": order_id})
        
        return {"message": "Order cancelled"}
    finally:
        if db:
            db.close()

