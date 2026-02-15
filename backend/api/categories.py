from fastapi import APIRouter, HTTPException
import sqlite3
from db import get_db
from models import CategoryCreate, CategoryResponse
from websocket_manager import manager

router = APIRouter()

@router.get("/categories", response_model=list[CategoryResponse])
def get_categories():
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT id, name, created_at FROM categories WHERE is_enabled = 1 ORDER BY name")
        rows = cursor.fetchall()
        result = []
        
        for row in rows:
            # sqlite3.Row supports dict-like access
            cat_id = int(row["id"])
            cat_name = str(row["name"])
            
            # Handle created_at - check if key exists first
            created_at = None
            if "created_at" in row.keys():
                created_at_val = row["created_at"]
                if created_at_val is not None:
                    created_at = str(created_at_val)
            
            result.append(CategoryResponse(
                id=cat_id,
                name=cat_name,
                created_at=created_at
            ))
        
        db.close()
        return result
    except Exception as e:
        db.close()
        import traceback
        error_msg = str(e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error fetching categories: {error_msg}")

@router.post("/categories", response_model=CategoryResponse)
async def create_category(category: CategoryCreate):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("INSERT INTO categories (name, is_enabled) VALUES (?, 1)", (category.name,))
        db.commit()
        category_id = cursor.lastrowid
        cursor.execute("SELECT id, name, created_at FROM categories WHERE id = ?", (category_id,))
        new_cat = cursor.fetchone()
        created_at = None
        if new_cat and "created_at" in new_cat.keys() and new_cat["created_at"]:
            try:
                created_at = str(new_cat["created_at"])
            except:
                created_at = None
        result = CategoryResponse(id=category_id, name=category.name, created_at=created_at)
        db.close()
        
        # Broadcast update via WebSocket
        try:
            await manager.broadcast({"type": "categories_updated"})
        except Exception as ws_error:
            print(f"WebSocket broadcast error (non-critical): {ws_error}")
        
        return result
    except sqlite3.IntegrityError as e:
        db.close()
        raise HTTPException(status_code=400, detail="Category already exists")
    except Exception as e:
        db.close()
        raise HTTPException(status_code=500, detail=f"Error creating category: {str(e)}")

@router.put("/categories/{category_id}", response_model=CategoryResponse)
async def update_category(category_id: int, category: CategoryCreate):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("UPDATE categories SET name = ? WHERE id = ?", (category.name, category_id))
        if cursor.rowcount == 0:
            db.close()
            raise HTTPException(status_code=404, detail="Category not found")
        db.commit()
        cursor.execute("SELECT id, name, created_at FROM categories WHERE id = ?", (category_id,))
        updated_cat = cursor.fetchone()
        created_at = None
        if updated_cat and "created_at" in updated_cat.keys() and updated_cat["created_at"]:
            try:
                created_at = str(updated_cat["created_at"])
            except:
                created_at = None
        result = CategoryResponse(id=category_id, name=category.name, created_at=created_at)
        db.close()
        
        # Broadcast update via WebSocket
        try:
            await manager.broadcast({"type": "categories_updated"})
        except Exception as ws_error:
            print(f"WebSocket broadcast error (non-critical): {ws_error}")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        db.close()
        raise HTTPException(status_code=500, detail=f"Error updating category: {str(e)}")

# Import delete_product to use its logic
from .products import delete_product

@router.delete("/categories/{category_id}")
async def delete_category(category_id: int):
    db = get_db()
    cursor = db.cursor()
    
    # 1. Get all products in this category
    cursor.execute("SELECT id FROM products WHERE category_id = ?", (category_id,))
    products = cursor.fetchall()
    db.close() # Close here because delete_product opens its own connection
    
    print(f"Deleting category {category_id} with {len(products)} products...")
    
    # 2. Delete/Disable all products
    for prod in products:
        try:
            await delete_product(prod['id'])
        except Exception as e:
            print(f"Error deleting product {prod['id']}: {e}")
            
    # 3. Check if any products remain (Soft Deleted)
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM products WHERE category_id = ?", (category_id,))
    remaining_count = cursor.fetchone()[0]
    
    if remaining_count > 0:
        # Soft Delete Category
        print(f"Category {category_id} has {remaining_count} remaining products (history). Soft deleting category.")
        cursor.execute("UPDATE categories SET is_enabled = 0 WHERE id = ?", (category_id,))
        message = "Category deleted (soft delete due to sales history)"
    else:
        # Hard Delete Category
        print(f"Category {category_id} has no products. Hard deleting.")
        cursor.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        message = "Category deleted permanently"
        
    db.commit()
    db.close()
    
    # Broadcast update via WebSocket
    try:
        await manager.broadcast({"type": "categories_updated"})
        await manager.broadcast({"type": "products_updated"})
    except Exception as ws_error:
        print(f"WebSocket broadcast error (non-critical): {ws_error}")
    
    return {"message": message}

