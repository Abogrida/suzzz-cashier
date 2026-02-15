from fastapi import APIRouter, HTTPException, UploadFile, File
from db import get_db
from models import ProductCreate, ProductUpdate, ProductResponse
from typing import Optional
import os
import sys
import shutil
from websocket_manager import manager

router = APIRouter()

# Get absolute path for upload directory - works for both script and EXE
if getattr(sys, 'frozen', False):
    # Running as EXE - save images in EXE directory
    EXE_DIR = os.path.dirname(sys.executable)
    UPLOAD_DIR = os.path.join(EXE_DIR, "images", "products")
else:
    # Running as script
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    UPLOAD_DIR = os.path.join(BASE_DIR, "frontend", "static", "images", "products")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.get("/products", response_model=list[ProductResponse])
def get_products(category_id: Optional[int] = None, enabled: Optional[bool] = None, exclude_hidden_tablet: Optional[bool] = None):
    db = get_db()
    cursor = db.cursor()
    query = """
        SELECT p.id, p.name, p.price, p.category_id, p.image_path, p.is_enabled as enabled, 
               COALESCE(p.price_s, 0) as price_s, 
               COALESCE(p.price_m, 0) as price_m, 
               COALESCE(p.price_l, 0) as price_l, 
               COALESCE(p.has_sizes, 0) as has_sizes, 
               COALESCE(p.is_hidden_on_tablet, 0) as hidden_on_tablet,
               c.name as category_name 
        FROM products p 
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE 1=1
    """
    params = []
    if category_id:
        query += " AND p.category_id = ?"
        params.append(category_id)
    if enabled is not None:
        query += " AND p.is_enabled = ?"
        params.append(1 if enabled else 0)
    if exclude_hidden_tablet:
        query += " AND (p.is_hidden_on_tablet IS NULL OR p.is_hidden_on_tablet = 0)"
    query += " ORDER BY p.name"
    cursor.execute(query, params)
    products = cursor.fetchall()
    db.close()
    result = []
    for p in products:
        # Get size prices - use direct access for sqlite3.Row
        try:
            price_s_val = p["price_s"]
        except (KeyError, TypeError):
            price_s_val = None
            
        try:
            price_m_val = p["price_m"]
        except (KeyError, TypeError):
            price_m_val = None
            
        try:
            price_l_val = p["price_l"]
        except (KeyError, TypeError):
            price_l_val = None
            
        try:
            has_sizes_val = p["has_sizes"]
        except (KeyError, TypeError):
            has_sizes_val = 0
        
        # Convert to float and check if > 0
        try:
            price_s = float(price_s_val) if price_s_val is not None and price_s_val != 0 and float(price_s_val) > 0 else None
        except (ValueError, TypeError):
            price_s = None
            
        try:
            price_m = float(price_m_val) if price_m_val is not None and price_m_val != 0 and float(price_m_val) > 0 else None
        except (ValueError, TypeError):
            price_m = None
            
        try:
            price_l = float(price_l_val) if price_l_val is not None and price_l_val != 0 and float(price_l_val) > 0 else None
        except (ValueError, TypeError):
            price_l = None
        
        # Get has_sizes - handle different types (bool, int, str)
        if isinstance(has_sizes_val, bool):
            has_sizes = has_sizes_val
        elif isinstance(has_sizes_val, int):
            has_sizes = bool(has_sizes_val)
        elif isinstance(has_sizes_val, str):
            has_sizes = has_sizes_val.lower() in ['true', '1', 'yes']
        else:
            has_sizes = bool(has_sizes_val) if has_sizes_val else False
        
        # If has any size prices, set has_sizes to True
        if not has_sizes and (price_s or price_m or price_l):
            has_sizes = True
        
        # print(f"Processing product {p['id']} ({p['name']}): has_sizes={has_sizes} (raw={has_sizes_val}), price_s={price_s} (raw={price_s_val}), price_m={price_m} (raw={price_m_val}), price_l={price_l} (raw={price_l_val})")
        
        result.append(ProductResponse(
            id=p["id"],
            name=p["name"],
            price=p["price"],
            category_id=p["category_id"],
            category_name=p["category_name"],
            image_path=p["image_path"],
            enabled=bool(p["enabled"]),
            price_s=price_s,
            price_m=price_m,
            price_l=price_l,

            has_sizes=has_sizes,
            hidden_on_tablet=bool(p["hidden_on_tablet"])
        ))
    return result

@router.get("/products/{product_id}", response_model=ProductResponse)
def get_product(product_id: int):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT p.id, p.name, p.price, p.category_id, p.image_path, p.is_enabled as enabled, 
               COALESCE(p.price_s, 0) as price_s, 
               COALESCE(p.price_m, 0) as price_m, 
               COALESCE(p.price_l, 0) as price_l, 
               COALESCE(p.has_sizes, 0) as has_sizes, 
               COALESCE(p.is_hidden_on_tablet, 0) as hidden_on_tablet,
               c.name as category_name 
        FROM products p 
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.id = ?
    """, (product_id,))
    product = cursor.fetchone()
    db.close()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Get size prices - handle None and 0 values
    # Use direct access for sqlite3.Row
    try:
        price_s_val = product["price_s"] if "price_s" in product.keys() else (product.get("price_s") if hasattr(product, 'get') else None)
        price_m_val = product["price_m"] if "price_m" in product.keys() else (product.get("price_m") if hasattr(product, 'get') else None)
        price_l_val = product["price_l"] if "price_l" in product.keys() else (product.get("price_l") if hasattr(product, 'get') else None)
        has_sizes_val = product["has_sizes"] if "has_sizes" in product.keys() else (product.get("has_sizes", 0) if hasattr(product, 'get') else 0)
    except (KeyError, TypeError):
        price_s_val = product.get("price_s") if hasattr(product, 'get') else None
        price_m_val = product.get("price_m") if hasattr(product, 'get') else None
        price_l_val = product.get("price_l") if hasattr(product, 'get') else None
        has_sizes_val = product.get("has_sizes", 0) if hasattr(product, 'get') else 0
    
    # Convert to float and check if > 0
    try:
        price_s = float(price_s_val) if price_s_val is not None and float(price_s_val) > 0 else None
    except (ValueError, TypeError):
        price_s = None
        
    try:
        price_m = float(price_m_val) if price_m_val is not None and float(price_m_val) > 0 else None
    except (ValueError, TypeError):
        price_m = None
        
    try:
        price_l = float(price_l_val) if price_l_val is not None and float(price_l_val) > 0 else None
    except (ValueError, TypeError):
        price_l = None
    
    # Get has_sizes - handle different types (bool, int, str)
    if isinstance(has_sizes_val, bool):
        has_sizes = has_sizes_val
    elif isinstance(has_sizes_val, int):
        has_sizes = bool(has_sizes_val)
    elif isinstance(has_sizes_val, str):
        has_sizes = has_sizes_val.lower() in ['true', '1', 'yes']
    else:
        has_sizes = bool(has_sizes_val) if has_sizes_val else False
    
    # If has any size prices, set has_sizes to True
    if not has_sizes and (price_s or price_m or price_l):
        has_sizes = True
    
    print(f"Returning product {product['id']}: has_sizes={has_sizes}, price_s={price_s}, price_m={price_m}, price_l={price_l}")
    
    return ProductResponse(
        id=product["id"],
        name=product["name"],
        price=product["price"],
        category_id=product["category_id"],
        category_name=product["category_name"],
        image_path=product["image_path"],
        enabled=bool(product["enabled"]),
        price_s=price_s,
        price_m=price_m,
        price_l=price_l,
        has_sizes=has_sizes,
        hidden_on_tablet=bool(product["hidden_on_tablet"])
    )

@router.post("/products", response_model=ProductResponse)
async def create_product(product: ProductCreate):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO products (name, price, category_id, image_path, is_enabled, price_s, price_m, price_l, has_sizes, is_hidden_on_tablet)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (product.name, product.price, product.category_id, product.image_path, 1 if product.enabled else 0,
          product.price_s, product.price_m, product.price_l, 1 if product.has_sizes else 0, 1 if product.hidden_on_tablet else 0))
    db.commit()
    product_id = cursor.lastrowid
    cursor.execute("""
        SELECT p.id, p.name, p.price, p.category_id, p.image_path, p.is_enabled as enabled, 
               COALESCE(p.price_s, 0) as price_s, 
               COALESCE(p.price_m, 0) as price_m, 
               COALESCE(p.price_l, 0) as price_l, 
               COALESCE(p.has_sizes, 0) as has_sizes, 
               COALESCE(p.is_hidden_on_tablet, 0) as hidden_on_tablet,
               c.name as category_name 
        FROM products p 
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.id = ?
    """, (product_id,))
    result = cursor.fetchone()
    db.close()
    
    # Get size prices - handle None and 0 values
    # Get size prices - use direct access for sqlite3.Row
    try:
        price_s_val = result["price_s"]
    except (KeyError, TypeError):
        price_s_val = None
        
    try:
        price_m_val = result["price_m"]
    except (KeyError, TypeError):
        price_m_val = None
        
    try:
        price_l_val = result["price_l"]
    except (KeyError, TypeError):
        price_l_val = None
        
    try:
        has_sizes_val = result["has_sizes"]
    except (KeyError, TypeError):
        has_sizes_val = 0
    
    # Convert to float and check if > 0
    try:
        price_s = float(price_s_val) if price_s_val is not None and price_s_val != 0 and float(price_s_val) > 0 else None
    except (ValueError, TypeError):
        price_s = None
        
    try:
        price_m = float(price_m_val) if price_m_val is not None and price_m_val != 0 and float(price_m_val) > 0 else None
    except (ValueError, TypeError):
        price_m = None
        
    try:
        price_l = float(price_l_val) if price_l_val is not None and price_l_val != 0 and float(price_l_val) > 0 else None
    except (ValueError, TypeError):
        price_l = None
    
    # Get has_sizes - handle different types (bool, int, str)
    if isinstance(has_sizes_val, bool):
        has_sizes = has_sizes_val
    elif isinstance(has_sizes_val, int):
        has_sizes = bool(has_sizes_val)
    elif isinstance(has_sizes_val, str):
        has_sizes = has_sizes_val.lower() in ['true', '1', 'yes']
    else:
        has_sizes = bool(has_sizes_val)
    
    # If has any size prices, set has_sizes to True
    if not has_sizes and (price_s or price_m or price_l):
        has_sizes = True
    
    print(f"Returning product {product_id}: has_sizes={has_sizes}, price_s={price_s}, price_m={price_m}, price_l={price_l}")
    
    response = ProductResponse(
        id=result["id"],
        name=result["name"],
        price=result["price"],
        category_id=result["category_id"],
        category_name=result["category_name"],
        image_path=result["image_path"],
        enabled=bool(result["enabled"]),
        price_s=price_s,
        price_m=price_m,
        price_l=price_l,
        has_sizes=has_sizes,
        hidden_on_tablet=bool(result["hidden_on_tablet"])
    )
    
    # Broadcast update via WebSocket
    try:
        await manager.broadcast({"type": "products_updated"})
    except Exception as ws_error:
        print(f"WebSocket broadcast error (non-critical): {ws_error}")
    
    return response

@router.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(product_id: int, product: ProductUpdate):
    db = get_db()
    cursor = db.cursor()
    
    # Get current product
    cursor.execute("SELECT id, name, price, category_id, image_path, is_enabled, price_s, price_m, price_l, has_sizes, is_hidden_on_tablet FROM products WHERE id = ?", (product_id,))
    current = cursor.fetchone()
    if not current:
        db.close()
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Update fields
    name = product.name if product.name is not None else current["name"]
    price = product.price if product.price is not None else current["price"]
    category_id = product.category_id if product.category_id is not None else current["category_id"]
    image_path = product.image_path if product.image_path is not None else current["image_path"]
    enabled = product.enabled if product.enabled is not None else bool(current["is_enabled"])
    hidden_on_tablet = product.hidden_on_tablet if product.hidden_on_tablet is not None else bool(current["is_hidden_on_tablet"] if current["is_hidden_on_tablet"] is not None else 0)
    
    # Handle sizes - if has_sizes is provided, use it; otherwise keep current value
    # IMPORTANT: Always use the provided has_sizes value if it exists
    # Get current size values using direct access for sqlite3.Row
    try:
        current_price_s = current["price_s"]
    except (KeyError, TypeError):
        current_price_s = None
        
    try:
        current_price_m = current["price_m"]
    except (KeyError, TypeError):
        current_price_m = None
        
    try:
        current_price_l = current["price_l"]
    except (KeyError, TypeError):
        current_price_l = None
        
    try:
        current_has_sizes = current["has_sizes"]
    except (KeyError, TypeError):
        current_has_sizes = 0
    
    if product.has_sizes is not None:
        has_sizes = bool(product.has_sizes)
        # If enabling sizes, use provided values
        if has_sizes:
            price_s = product.price_s if product.price_s is not None else current_price_s
            price_m = product.price_m if product.price_m is not None else current_price_m
            price_l = product.price_l if product.price_l is not None else current_price_l
        else:
            # If disabling sizes, clear all size prices
            price_s = None
            price_m = None
            price_l = None
    else:
        # If has_sizes not provided, keep current values
        has_sizes = bool(current_has_sizes) if current_has_sizes else False
        price_s = product.price_s if product.price_s is not None else current_price_s
        price_m = product.price_m if product.price_m is not None else current_price_m
        price_l = product.price_l if product.price_l is not None else current_price_l
    
    # Debug logging
    print(f"Updating product {product_id}: has_sizes={has_sizes}, price_s={price_s}, price_m={price_m}, price_l={price_l}")
    
    try:
        cursor.execute("""
            UPDATE products 
            SET name = ?, price = ?, category_id = ?, image_path = ?, is_enabled = ?, 
                price_s = ?, price_m = ?, price_l = ?, has_sizes = ?, is_hidden_on_tablet = ?
            WHERE id = ?
        """, (name, price, category_id, image_path, 1 if enabled else 0, price_s, price_m, price_l, 1 if has_sizes else 0, 1 if hidden_on_tablet else 0, product_id))
        db.commit()
    except Exception as e:
        db.close()
        print(f"Error updating product: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating product: {str(e)}")
    
    cursor.execute("""
        SELECT p.id, p.name, p.price, p.category_id, p.image_path, p.is_enabled as enabled, 
               COALESCE(p.price_s, 0) as price_s, 
               COALESCE(p.price_m, 0) as price_m, 
               COALESCE(p.price_l, 0) as price_l, 
               COALESCE(p.has_sizes, 0) as has_sizes, 
               COALESCE(p.is_hidden_on_tablet, 0) as hidden_on_tablet,
               c.name as category_name 
        FROM products p 
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.id = ?
    """, (product_id,))
    result = cursor.fetchone()
    db.close()
    
    # Get size prices - handle None and 0 values
    # Get size prices - use direct access for sqlite3.Row
    try:
        price_s_val = result["price_s"]
    except (KeyError, TypeError):
        price_s_val = None
        
    try:
        price_m_val = result["price_m"]
    except (KeyError, TypeError):
        price_m_val = None
        
    try:
        price_l_val = result["price_l"]
    except (KeyError, TypeError):
        price_l_val = None
        
    try:
        has_sizes_val = result["has_sizes"]
    except (KeyError, TypeError):
        has_sizes_val = 0
    
    # Convert to float and check if > 0
    try:
        price_s = float(price_s_val) if price_s_val is not None and price_s_val != 0 and float(price_s_val) > 0 else None
    except (ValueError, TypeError):
        price_s = None
        
    try:
        price_m = float(price_m_val) if price_m_val is not None and price_m_val != 0 and float(price_m_val) > 0 else None
    except (ValueError, TypeError):
        price_m = None
        
    try:
        price_l = float(price_l_val) if price_l_val is not None and price_l_val != 0 and float(price_l_val) > 0 else None
    except (ValueError, TypeError):
        price_l = None
    
    # Get has_sizes - handle different types (bool, int, str)
    if isinstance(has_sizes_val, bool):
        has_sizes = has_sizes_val
    elif isinstance(has_sizes_val, int):
        has_sizes = bool(has_sizes_val)
    elif isinstance(has_sizes_val, str):
        has_sizes = has_sizes_val.lower() in ['true', '1', 'yes']
    else:
        has_sizes = bool(has_sizes_val)
    
    # If has any size prices, set has_sizes to True
    if not has_sizes and (price_s or price_m or price_l):
        has_sizes = True
    
    print(f"Returning product {product_id}: has_sizes={has_sizes}, price_s={price_s}, price_m={price_m}, price_l={price_l}")
    
    response = ProductResponse(
        id=result["id"],
        name=result["name"],
        price=result["price"],
        category_id=result["category_id"],
        category_name=result["category_name"],
        image_path=result["image_path"],
        enabled=bool(result["enabled"]),
        price_s=price_s,
        price_m=price_m,
        price_l=price_l,
        has_sizes=has_sizes,
        hidden_on_tablet=bool(result["hidden_on_tablet"])
    )
    
    # Broadcast update via WebSocket
    try:
        await manager.broadcast({"type": "products_updated"})
    except Exception as ws_error:
        print(f"WebSocket broadcast error (non-critical): {ws_error}")
    
    return response

@router.delete("/products/{product_id}")
async def delete_product(product_id: int):
    db = get_db()
    cursor = db.cursor()
    
    # Check if product exists
    cursor.execute("SELECT image_path FROM products WHERE id = ?", (product_id,))
    result = cursor.fetchone()
    
    if not result:
        db.close()
        raise HTTPException(status_code=404, detail="Product not found")
        
    image_path = result["image_path"]
    
    try:
        # Unlink from order_items (set product_id to NULL)
        # This preserves the historical data (product_name, price, etc.) in order_items
        cursor.execute("UPDATE order_items SET product_id = NULL WHERE product_id = ?", (product_id,))
        
        # Delete from products
        cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
        
        db.commit()
    except Exception as e:
        db.rollback()
        db.close()
        print(f"Error deleting product: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting product: {str(e)}")
        
    db.close()
    
    # Delete image file if exists
    if image_path:
        try:
            # Convert web path to file path
            # image_path is like "/static/images/products/filename.jpg"
            if image_path.startswith("/static/images/products/"):
                filename = image_path.split("/")[-1]
                file_path = os.path.join(UPLOAD_DIR, filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"Deleted image file: {file_path}")
        except Exception as e:
            print(f"Error deleting image file: {e}")
    
    # Broadcast update via WebSocket
    try:
        await manager.broadcast({"type": "products_updated"})
    except Exception as ws_error:
        print(f"WebSocket broadcast error (non-critical): {ws_error}")
    
    return {"message": "Product deleted permanently"}

@router.post("/products/{product_id}/upload-image")
async def upload_image(product_id: int, file: UploadFile = File(...)):
    try:
        # Allowed image extensions
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif', '.svg', '.ico', '.jfif', '.pjpeg', '.pjp'}
        
        # Get file extension
        file_ext = os.path.splitext(file.filename)[1].lower() if file.filename else ''
        
        # Validate file type - check both content_type and file extension
        is_valid_image = False
        
        # Check content_type first
        if file.content_type and file.content_type.startswith('image/'):
            is_valid_image = True
        # If content_type is missing or invalid, check file extension
        elif file_ext in allowed_extensions:
            is_valid_image = True
        
        if not is_valid_image:
            raise HTTPException(
                status_code=400, 
                detail=f"File must be an image. Allowed types: {', '.join(allowed_extensions)}"
            )
        
        # Use .jpg as default extension if none provided
        if not file_ext:
            file_ext = '.jpg'
        
        # Save uploaded file
        filename = f"product_{product_id}{file_ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        
        # Ensure directory exists
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        
        # Save file
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Update product image path in database
        image_path = f"/static/images/products/{filename}"
        db = get_db()
        cursor = db.cursor()
        cursor.execute("UPDATE products SET image_path = ? WHERE id = ?", (image_path, product_id))
        db.commit()
        db.close()
        
        print(f"Image saved: {filepath}, Path: {image_path}")
        return {"image_path": image_path, "message": "Image uploaded successfully"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error uploading image: {str(e)}")

