import os
import sys
from datetime import datetime
from typing import List, Dict, Optional
import base64
import io

# Function to check if browser print mode is enabled
def is_browser_print_mode():
    """Check if BROWSER_PRINT is selected in settings"""
    try:
        from db import get_db
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'printer_ip'")
        result = cursor.fetchone()
        db.close()
        
        if result and result["value"] == "BROWSER_PRINT":
            return True
        return False
    except Exception as e:
        print(f"[WARN] Error checking browser print mode: {e}")
        return False

# Add backend directory to path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from db import get_db
from hybrid_printer import HybridPrinter
from exact_renderer import ExactRenderer

def open_cash_drawer(print_slip=False):
    """فتح درج الكاشير"""
    try:
        printer = HybridPrinter()
        printer.kick_drawer()
        
        if print_slip:
            try:
                renderer = ExactRenderer()
                slip_img = renderer.render_drawer_slip()
                printer.printer.image(slip_img)
                printer.cut()
            except Exception as e:
                print(f"[WARN] Failed to print drawer slip: {e}")
                
        printer.close()
        print("[OK] Drawer open command sent")
        return True
    except Exception as e:
        print(f"[ERROR] Error opening drawer: {e}")
        return False

def process_checkout(order_id: int):
    """
    Unified Checkout Flow:
    1. Open Drawer
    2. Print Drawer Slip
    3. Print Customer Invoice (Exact Layout)
    4. Print Kitchen Receipt (Exact Layout)
    """
    print(f"[Checkout] Processing order {order_id}...")
    
    try:
        # 1. Open Drawer
        open_cash_drawer()
        
        # Connect to printer once for all jobs if possible, or separate
        # HybridPrinter handles connection per instance.
        
        # Prepare Data
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        order_row = cursor.fetchone()
        
        cursor.execute("SELECT * FROM invoices WHERE order_id = ?", (order_id,))
        invoice_row = cursor.fetchone()
        
        cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
        items_rows = cursor.fetchall()
        
        db.close()
        
        if not order_row or not invoice_row:
            print("[ERROR] Order or Invoice not found")
            return False
            
        renderer = ExactRenderer()
        
        # 3. Print Customer Invoice
        print("[Checkout] Printing Customer Invoice...")
        invoice_img = renderer.render_customer_invoice(order_row, invoice_row, items_rows)
        
        # Check for Browser Print Mode
        if is_browser_print_mode():
            print("[Checkout] BROWSER PRINT MODE ENABLED - Returning Image Data")
            
            # Convert PIL Image to Base64
            buffered = io.BytesIO()
            invoice_img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            
            # 4. Print Kitchen Receipt (Still print to physical kitchen printer if needed, 
            # or we could return both? For now, let's just assume kitchen prints physically or we skip)
            # If we want kitchen to also be browser printed, we'd need to return multiple images.
            # For this request, user asked for "Fawateer" (Invoices) in browser.
            # But let's assume we might still want kitchen to print physically if possible, 
            # or just skip it if no printer.
            # print_kitchen_receipt(order_id) 
            
            print("[Checkout] Done! (Browser Mode)")
            return {"success": True, "print_preview": img_str}
            
        printer = HybridPrinter()
        printer.printer.image(invoice_img)
        printer.cut()
        
        printer.close() # Close here as print_kitchen_receipt opens its own connection
        
        # 4. Print Kitchen Receipt (Incremental - only unprinted items)
        print("[Checkout] Printing Kitchen Receipt...")
        print_kitchen_receipt(order_id)
        
        print("[Checkout] Done!")
        return True
        
    except Exception as e:
        print(f"[ERROR] Checkout process failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# Keep these for individual calls if needed, but redirect to ExactRenderer
def print_kitchen_receipt(order_id: int, new_items_only: List[Dict] = None):
    """Print kitchen receipt for unprinted items only"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Get Order
        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        order_row = cursor.fetchone()
        if not order_row: return False

        # Get Unprinted Items
        # If new_items_only is passed (legacy), use it, otherwise check DB
        if new_items_only:
            items_rows = new_items_only
            # We should mark these as printed too if they have IDs
        else:
            cursor.execute("SELECT * FROM order_items WHERE order_id = ? AND (is_printed = 0 OR is_printed IS NULL)", (order_id,))
            items_rows = cursor.fetchall()
            
        if not items_rows:
            print("[INFO] No new items to print for kitchen.")
            db.close()
            return True
            
        # Render and Print
        renderer = ExactRenderer()
        img = renderer.render_kitchen_receipt(order_row, items_rows)
        
        if is_browser_print_mode():
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            
            # Mark items as printed even in browser mode, assuming user will print it
            # Or should we wait? Usually better to mark as printed to avoid re-printing
            item_ids = [item['id'] for item in items_rows if 'id' in item.keys()]
            if item_ids:
                placeholders = ','.join(['?'] * len(item_ids))
                cursor.execute(f"UPDATE order_items SET is_printed = 1 WHERE id IN ({placeholders})", item_ids)
                db.commit()
            
            db.close()
            return {"success": True, "print_preview": img_str}

        printer = HybridPrinter()
        printer.printer.image(img)
        printer.cut()
        printer.close()
        
        # Mark items as printed
        item_ids = [item['id'] for item in items_rows if 'id' in item.keys()]
        if item_ids:
            placeholders = ','.join(['?'] * len(item_ids))
            cursor.execute(f"UPDATE order_items SET is_printed = 1 WHERE id IN ({placeholders})", item_ids)
            db.commit()
            
        db.close()
        return True
    except Exception as e:
        print(f"Error printing kitchen receipt: {e}")
        import traceback
        traceback.print_exc()
        return False

def print_customer_invoice(order_id: int):
    # Redirect to process_checkout if this is the main "Finish" action
    # But if it's just "Reprint Invoice", we should just print invoice.
    # For now, let's keep it specific.
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        order_row = cursor.fetchone()
        cursor.execute("SELECT * FROM invoices WHERE order_id = ?", (order_id,))
        invoice_row = cursor.fetchone()
        cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
        items_rows = cursor.fetchall()
        db.close()
        
        # Handle legacy orders or missing invoices:
        # If order is completed but no invoice row exists, construct a fake one
        # so it prints as an Invoice, not a "Check"
        if not invoice_row and order_row and order_row['status'] == 'completed':
            invoice_row = {
                'invoice_number': order_row['invoice_number'] or str(order_row['order_number']),
                'cashier': order_row['cashier'] or 'Admin',
                'invoice_location': 'Local',
                'created_at': order_row['completed_at'] or order_row['created_at'],
                'total_amount': order_row['total_amount'],
                'discount_amount': order_row['discount_amount'] if 'discount_amount' in order_row.keys() else 0,
                'tax_amount': order_row['tax_amount'] if 'tax_amount' in order_row.keys() else 0,
                'vat_amount': order_row['vat_amount'] if 'vat_amount' in order_row.keys() else 0,
                'net_amount': order_row['total_amount'], # Assumption
                'payment_method': 'cash'
            }
        
        renderer = ExactRenderer()
        img = renderer.render_customer_invoice(order_row, invoice_row, items_rows)
        
        if is_browser_print_mode():
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            return {"success": True, "print_preview": img_str}
            
        printer = HybridPrinter()
        printer.printer.image(img)
        printer.cut()
        printer.close()
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

def print_order_check(order_id: int):
    """Print provisional check for an order, even if not completed"""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        order_row = cursor.fetchone()
        
        # Get Items
        cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
        items_rows = cursor.fetchall()
        db.close()
        
        if not order_row:
            print("[ERROR] Order found")
            return False
            
        renderer = ExactRenderer()
        printer = HybridPrinter()
        # Pass None as invoice to trigger "Check" mode
        img = renderer.render_customer_invoice(order_row, None, items_rows)
        
        if is_browser_print_mode():
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            return {"success": True, "print_preview": img_str}
            
        printer.printer.image(img)
        printer.cut()
        printer.close()
        return True
    except Exception as e:
        print(f"Error printing check: {e}")
        return False

def print_shift_report(shift_id: int):
    """Print detailed shift report using ExactRenderer"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        # 1. Get Shift Info
        cursor.execute("SELECT * FROM shifts WHERE id = ?", (shift_id,))
        shift = cursor.fetchone()
        if not shift: return False
        
        # 2. Get Sales Data (Invoices)
        cursor.execute("SELECT * FROM invoices WHERE shift_id = ?", (shift_id,))
        invoices = cursor.fetchall()
        
        total_revenue = 0.0
        total_cash = 0.0
        total_card = 0.0
        total_tax = 0.0
        total_vat = 0.0
        total_discount = 0.0
        invoice_count = len(invoices)
        
        for inv in invoices:
            net = float(inv['net_amount'])
            total_revenue += net
            total_tax += float(inv['tax_amount']) if inv['tax_amount'] else 0
            total_vat += float(inv['vat_amount']) if inv['vat_amount'] else 0
            total_discount += float(inv['discount_amount']) if inv['discount_amount'] else 0
            
            pm = inv['payment_method']
            if pm == 'cash':
                total_cash += net
            elif pm == 'card':
                total_card += net
            elif pm and pm.startswith('mixed'):
                # Simple parsing for mixed
                try:
                    parts = pm.split('_')
                    cash_val = float(parts[2])
                    card_val = float(parts[4])
                    total_cash += cash_val
                    total_card += card_val
                except:
                    pass
                    
        # 3. Get Categories Breakdown
        # Join order_items -> products -> categories
        # We need to link order_items to invoices or orders in this shift
        cursor.execute("""
            SELECT c.name, SUM(oi.quantity) as qty, SUM(oi.total) as total
            FROM order_items oi
            JOIN invoices inv ON oi.order_id = inv.order_id
            JOIN products p ON oi.product_id = p.id
            JOIN categories c ON p.category_id = c.id
            WHERE inv.shift_id = ?
            GROUP BY c.id
        """, (shift_id,))
        categories_data = cursor.fetchall()
        
        categories_list = []
        for cat in categories_data:
            categories_list.append({
                "name": cat['name'],
                "qty": cat['qty'],
                "total": float(cat['total'])
            })
            
        db.close()
        
        # Prepare Data Dictionary
        data = {
            "shift_number": shift['shift_number'],
            "shift_name": shift['shift_name'],
            "start_date": shift['opened_at'].split()[0] if shift['opened_at'] else "",
            "start_time": datetime.strptime(shift['opened_at'], "%Y-%m-%d %H:%M:%S").strftime("%I:%M %p") if shift['opened_at'] else "",
            "end_date": shift['closed_at'].split()[0] if shift['closed_at'] else datetime.now().strftime("%Y-%m-%d"),
            "end_time": datetime.strptime(shift['closed_at'], "%Y-%m-%d %H:%M:%S").strftime("%I:%M %p") if shift['closed_at'] else datetime.now().strftime("%I:%M %p"),
            "branch": "الفرع الرئيسي", # Hardcoded for now
            "cashier": shift['opened_by'] or "كاشير",
            "sales": {
                "count": invoice_count,
                "total": total_revenue,
                "cash": total_cash,
                "card": total_card,
                "tax": total_tax,
                "vat": total_vat,
                "delivery": 0.00, # Not tracked yet
                "discount": total_discount
            },
            "expenses": {
                "count": 0,
                "debit": 0.00,
                "credit": 0.00
            },
            "reconciliation": {
                "total_expenses": 0.00,
                "total_income": 0.00,
                "cash_sales": total_cash,
                "net_amount": total_revenue,
                "cashier_cash": float(shift['cash_drawer_amount']) if shift['cash_drawer_amount'] else 0.0,
                "cash_diff": float(shift['cash_difference']) if shift['cash_difference'] else 0.0,
                "card_sales": total_card,
                "device_total": total_card, # Assuming device total matches card sales
                "device_diff": 0.00,
                "cash_tips": 0.00,
                "card_tips": 0.00
            },
            "categories": categories_list,
            "returns": {
                "invoices": 0,
                "items": 0
            }
        }
        
        # Render and Print
        renderer = ExactRenderer()
        img = renderer.render_shift_report(data)
        
        if is_browser_print_mode():
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            return {"success": True, "print_preview": img_str}
        
        printer = HybridPrinter()
        printer.printer.image(img)
        printer.cut()
        printer.close()
        
        return True
        
    except Exception as e:
        print(f"Error printing shift report: {e}")
        import traceback
        traceback.print_exc()
        return False
