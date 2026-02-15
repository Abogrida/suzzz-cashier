from fastapi import APIRouter, HTTPException
from db import get_db
from models import SettingsUpdate, LoginRequest
from pydantic import BaseModel
from fastapi import UploadFile, File
import shutil
import os
import sys

router = APIRouter()

class AuthRequest(BaseModel):
    password: str
    page_type: str  # 'cashier' or 'admin'

class DiscountPermissionUpdate(BaseModel):
    enabled: bool

class ReceiptSettingsUpdate(BaseModel):
    restaurant_name: str | None = None
    restaurant_address: str | None = None
    footer_text: str | None = None

@router.get("/settings")
def get_settings():
    db = get_db()
    try:
        cursor = db.cursor()
        cursor.execute("SELECT key, value FROM settings")
        settings_dict = {row["key"]: row["value"] for row in cursor.fetchall()}
        return settings_dict
    except Exception as e:
        print(f"Error getting settings: {e}")
        return {}
    finally:
        db.close()

# ... (update_settings is already fixed) ...

@router.get("/auth/passwords")
def get_passwords():
    """Get current passwords (admin only)"""
    db = get_db()
    try:
        cursor = db.cursor()
        
        cursor.execute("SELECT value FROM settings WHERE key = 'admin_password'")
        admin_result = cursor.fetchone()
        admin_password = admin_result["value"] if admin_result else "12345"
        
        cursor.execute("SELECT value FROM settings WHERE key = 'cashier_password'")
        cashier_result = cursor.fetchone()
        cashier_password = cashier_result["value"] if cashier_result else "1234"
        
        return {
            "admin_password": admin_password,
            "cashier_password": cashier_password
        }
    except Exception as e:
        print(f"Error getting passwords: {e}")
        return {}
    finally:
        db.close()

@router.get("/settings/discount_permission")
def get_discount_permission():
    """Get discount permission status"""
    db = get_db()
    try:
        cursor = db.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'cashier_discount_permission'")
        result = cursor.fetchone()
        has_permission = result and result["value"] == "1" if result else False
        return {"has_discount_permission": has_permission}
    except Exception as e:
        print(f"Error getting discount permission: {e}")
        return {"has_discount_permission": False}
    finally:
        if db:
            db.close()

@router.put("/settings")
def update_settings(settings: SettingsUpdate):
    print(f"DEBUG: update_settings called with: {settings.dict()}")
    db = get_db()
    try:
        cursor = db.cursor()
        
        # Helper to execute update within the same transaction
        def update_single_key(key, value):
            print(f"DEBUG: Updating {key} -> {value}")
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))

        if settings.admin_password:
            update_single_key('admin_password', settings.admin_password)
        
        if settings.cashier_password:
            update_single_key('cashier_password', settings.cashier_password)
            
        if settings.owner_password:
            update_single_key('owner_password', settings.owner_password)
        
        if settings.printer_ip:
            update_single_key('printer_ip', settings.printer_ip)
            
        if settings.restaurant_name:
            update_single_key('restaurant_name', settings.restaurant_name)
            
        if settings.restaurant_address:
            update_single_key('restaurant_address', settings.restaurant_address)
            
        if settings.footer_text:
            update_single_key('footer_text', settings.footer_text)
            
        if settings.logo_path:
            update_single_key('logo_path', settings.logo_path)

        # explicit check for not None ensures we don't skip valid 0 values if that were allowed, 
        # though prices usually > 0.
        if settings.playstation_price_per_hour is not None:
            update_single_key('playstation_price_per_hour', str(settings.playstation_price_per_hour))
        else:
            print("DEBUG: playstation_price_per_hour is None")

        if settings.playstation_price_multi is not None:
            update_single_key('playstation_price_multi', str(settings.playstation_price_multi))
        else:
             print("DEBUG: playstation_price_multi is None")

        if settings.playstation_enabled is not None:
             update_single_key('playstation_enabled', str(settings.playstation_enabled))
        
        db.commit()
        print("DEBUG: Settings committed successfully")
        return {"message": "Settings updated"}
    except Exception as e:
        db.rollback()
        print(f"Error updating settings: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.post("/settings/reset-data")
def reset_data_endpoint(auth: AuthRequest):
    """
    Reset Data: Clears all transactional data (Orders, Invoices, Shifts).
    Keeps Products, Categories, Settings, Tables.
    """
    # Verify Admin Password
    db = get_db()
    try:
        cursor = db.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'admin_password'")
        row = cursor.fetchone()
        admin_pass = row["value"] if row else "12345"
        
        if auth.password != admin_pass:
            raise HTTPException(status_code=401, detail="كلمة المرور غير صحيحة")
            
        # Delete Transactional Data
        cursor.execute("DELETE FROM order_items")
        cursor.execute("DELETE FROM invoices")
        cursor.execute("DELETE FROM orders")
        cursor.execute("DELETE FROM shifts")
        
        # Reset Tables Status
        # Tables table has order_id, not current_order_id
        cursor.execute("UPDATE tables SET status = 'open', order_id = NULL")
        
        db.commit()
        
        # Vacuum to reclaim space (must be outside transaction)
        old_isolation = db.isolation_level
        db.isolation_level = None
        cursor.execute("VACUUM")
        db.isolation_level = old_isolation
        
        return {"message": "تم تصفير البيانات بنجاح", "success": True}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error resetting data: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.post("/settings/factory-reset")
def factory_reset_endpoint(auth: AuthRequest):
    """
    Factory Reset: Clears EVERYTHING including Menu.
    Keeps only critical settings (passwords).
    """
    # Verify Admin Password
    db = get_db()
    try:
        cursor = db.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'admin_password'")
        row = cursor.fetchone()
        admin_pass = row["value"] if row else "12345"
        
        if auth.password != admin_pass:
            raise HTTPException(status_code=401, detail="كلمة المرور غير صحيحة")
            
        # 1. Clear Transactions
        cursor.execute("DELETE FROM order_items")
        cursor.execute("DELETE FROM invoices")
        cursor.execute("DELETE FROM orders")
        cursor.execute("DELETE FROM shifts")
        
        # 2. Clear Menu
        cursor.execute("DELETE FROM products")
        cursor.execute("DELETE FROM categories")
        cursor.execute("DELETE FROM product_additions")
        
        # 3. Reset Tables (Delete all and re-insert defaults 1-10 for clean start)
        cursor.execute("DELETE FROM tables") 
        # Insert defaults safely
        default_tables = [(i, 'open') for i in range(1, 11)]
        cursor.executemany("INSERT INTO tables (table_number, status) VALUES (?, ?)", default_tables)
         
        # 4. Clear Settings
        # Keep passwords
        cursor.execute("""
            DELETE FROM settings 
            WHERE key NOT IN ('admin_password', 'cashier_password', 'owner_password')
        """)
        
        db.commit()
        
        # Vacuum
        old_isolation = db.isolation_level
        db.isolation_level = None
        cursor.execute("VACUUM")
        db.isolation_level = old_isolation
        
        return {"message": "تم إعادة ضبط المصنع بنجاح", "success": True}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error factory reset: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

# update_single_setting is no longer needed for this endpoint but kept if used elsewhere, 
# though it's better to rely on the endpoint logic above. 
# We can leave it for now or remove if unused elsewhere. 
# It seems unused elsewhere in this file, but to be safe we can leave it or just let the function above handle it.

def update_single_setting(key, value):
    db = get_db()
    try:
        cursor = db.cursor()
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        db.commit()
    finally:
        db.close()

@router.post("/auth/login")
def login(auth: AuthRequest):
    db = get_db()
    try:
        cursor = db.cursor()
        
        # Check Owner Password first (special case)
        cursor.execute("SELECT value FROM settings WHERE key = 'owner_password'")
        owner_result = cursor.fetchone()
        owner_pass = owner_result["value"] if owner_result else "2212"
        
        if auth.password == owner_pass:
            return {"success": True, "message": "Login successful", "role": "owner"}

        # Get the appropriate password for other roles
        password_key = 'admin_password' if auth.page_type == 'admin' else 'cashier_password'
        cursor.execute("SELECT value FROM settings WHERE key = ?", (password_key,))
        result = cursor.fetchone()
        
        # If no password set, use defaults
        if not result:
            default_password = '12345' if auth.page_type == 'admin' else '1234'
            if auth.password != default_password:
                raise HTTPException(status_code=401, detail="Invalid password")
        else:
            if result["value"] != auth.password:
                raise HTTPException(status_code=401, detail="Invalid password")
        
        return {"success": True, "message": "Login successful", "role": auth.page_type}
    finally:
        if db:
            db.close()

@router.get("/auth/passwords")
def get_passwords():
    """Get current passwords (admin only)"""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("SELECT value FROM settings WHERE key = 'admin_password'")
    admin_result = cursor.fetchone()
    admin_password = admin_result["value"] if admin_result else "12345"
    
    cursor.execute("SELECT value FROM settings WHERE key = 'cashier_password'")
    cashier_result = cursor.fetchone()
    cashier_password = cashier_result["value"] if cashier_result else "1234"
    
    db.close()
    return {
        "admin_password": admin_password,
        "cashier_password": cashier_password
    }

@router.get("/settings/discount_permission")
def get_discount_permission():
    """Get discount permission status"""
    db = get_db()
    try:
        cursor = db.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'cashier_discount_permission'")
        result = cursor.fetchone()
        has_permission = result and result["value"] == "1" if result else False
        return {"has_discount_permission": has_permission}
    except Exception as e:
        print(f"Error getting discount permission: {e}")
        return {"has_discount_permission": False}
    finally:
        if db:
            db.close()

@router.put("/settings/discount_permission")
def update_discount_permission(permission: DiscountPermissionUpdate):
    """Update discount permission for cashier (admin only)"""
    db = get_db()
    try:
        enabled = permission.enabled
        cursor = db.cursor()
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('cashier_discount_permission', ?)", ("1" if enabled else "0",))
        db.commit()
        
        # Broadcast update via WebSocket for real-time update
        try:
            from websocket_manager import manager
            manager.broadcast({
                "type": "discount_permission_updated",
                "has_discount_permission": enabled
            })
        except Exception as e:
            print(f"Error broadcasting discount permission update: {e}")
        
        return {"message": "Discount permission updated", "enabled": enabled}
    except Exception as e:
        print(f"Error updating discount permission: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error updating discount permission: {str(e)}")
    finally:
        if db:
            db.close()

@router.post("/settings/logo")
async def upload_logo(file: UploadFile = File(...)):
    # Determine base directory
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        # backend/api/settings.py -> backend/api -> backend -> root
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # Create images/logo directory if not exists
    logo_dir = os.path.join(base_dir, "images", "logo")
    os.makedirs(logo_dir, exist_ok=True)
    
    # Save file
    # Use a consistent name to avoid clutter
    filename = "custom_logo.png"
    file_path = os.path.join(logo_dir, filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Update settings in DB
    db = get_db()
    cursor = db.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('logo_path', ?)", (file_path,))
    db.commit()
    db.close()
    
    # Return URL for frontend (we will need to serve this path)
    # Timestamp to bust cache
    import time
    return {"message": "Logo uploaded successfully", "path": file_path, "url": f"/static/images/logo/{filename}?t={int(time.time())}"}

@router.put("/settings/receipt")
def update_receipt_settings(settings: ReceiptSettingsUpdate):
    db = get_db()
    cursor = db.cursor()
    
    if settings.restaurant_name is not None:
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('restaurant_name', ?)", (settings.restaurant_name,))
    
    if settings.restaurant_address is not None:
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('restaurant_address', ?)", (settings.restaurant_address,))
        
    if settings.footer_text is not None:
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('footer_text', ?)", (settings.footer_text,))
        
    db.commit()
    db.close()
    return {"message": "Receipt settings updated"}
