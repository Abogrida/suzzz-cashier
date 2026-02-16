"""
Command Handlers for Local System
Executes commands received from Cloud Admin via WebSocket
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db import get_db

async def handle_add_category(payload: dict) -> dict:
    """Add a new category"""
    name = payload.get('name')
    if not name:
        raise Exception("Category name is required")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "INSERT INTO categories (name) VALUES (?)",
            (name,)
        )
        conn.commit()
        category_id = cursor.lastrowid
        
        return {
            "id": category_id,
            "name": name,
            "message": "Category added successfully"
        }
    finally:
        conn.close()


async def handle_edit_category(payload: dict) -> dict:
    """Edit an existing category"""
    category_id = payload.get('id')
    name = payload.get('name')
    
    if not category_id or not name:
        raise Exception("Category ID and name are required")
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "UPDATE categories SET name = ? WHERE id = ?",
            (name, category_id)
        )
        conn.commit()
        
        if cursor.rowcount == 0:
            raise Exception(f"Category {category_id} not found")
        
        return {
            "id": category_id,
            "name": name,
            "message": "Category updated successfully"
        }
    finally:
        conn.close()


async def handle_delete_category(payload: dict) -> dict:
    """Delete a category"""
    category_id = payload.get('id')
    
    if not category_id:
        raise Exception("Category ID is required")
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        conn.commit()
        
        if cursor.rowcount == 0:
            raise Exception(f"Category {category_id} not found")
        
        return {
            "id": category_id,
            "message": "Category deleted successfully"
        }
    finally:
        conn.close()


async def handle_add_product(payload: dict) -> dict:
    """Add a new product"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Extract fields
        name = payload.get('name')
        category_id = payload.get('category_id')
        price = payload.get('price', 0)
        has_sizes = payload.get('has_sizes', False)
        price_s = payload.get('price_s')
        price_m = payload.get('price_m')
        price_l = payload.get('price_l')
        enabled = payload.get('enabled', True)
        hidden_on_tablet = payload.get('hidden_on_tablet', False)
        
        if not name:
            raise Exception("Product name is required")
        
        cursor.execute("""
            INSERT INTO products 
            (name, category_id, price, has_sizes, price_s, price_m, price_l, enabled, hidden_on_tablet)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, category_id, price, has_sizes, price_s, price_m, price_l, enabled, hidden_on_tablet))
        
        conn.commit()
        product_id = cursor.lastrowid
        
        return {
            "id": product_id,
            "name": name,
            "message": "Product added successfully"
        }
    finally:
        conn.close()


async def handle_edit_product(payload: dict) -> dict:
    """Edit an existing product"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        product_id = payload.get('id')
        if not product_id:
            raise Exception("Product ID is required")
        
        # Build update query dynamically based on provided fields
        updates = []
        params = []
        
        for field in ['name', 'category_id', 'price', 'has_sizes', 'price_s', 'price_m', 'price_l', 'enabled', 'hidden_on_tablet']:
            if field in payload:
                updates.append(f"{field} = ?")
                params.append(payload[field])
        
        if not updates:
            raise Exception("No fields to update")
        
        params.append(product_id)
        query = f"UPDATE products SET {', '.join(updates)} WHERE id = ?"
        
        cursor.execute(query, params)
        conn.commit()
        
        if cursor.rowcount == 0:
            raise Exception(f"Product {product_id} not found")
        
        return {
            "id": product_id,
            "message": "Product updated successfully"
        }
    finally:
        conn.close()


async def handle_delete_product(payload: dict) -> dict:
    """Delete a product"""
    product_id = payload.get('id')
    
    if not product_id:
        raise Exception("Product ID is required")
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        
        if cursor.rowcount == 0:
            raise Exception(f"Product {product_id} not found")
        
        return {
            "id": product_id,
            "message": "Product deleted successfully"
        }
    finally:
        conn.close()


async def handle_toggle_product(payload: dict) -> dict:
    """Toggle product enabled status"""
    product_id = payload.get('id')
    enabled = payload.get('enabled')
    
    if not product_id or enabled is None:
        raise Exception("Product ID and enabled status are required")
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "UPDATE products SET enabled = ? WHERE id = ?",
            (enabled, product_id)
        )
        conn.commit()
        
        if cursor.rowcount == 0:
            raise Exception(f"Product {product_id} not found")
        
        return {
            "id": product_id,
            "enabled": enabled,
            "message": "Product status updated successfully"
        }
    finally:
        conn.close()


# Command handler registry
COMMAND_HANDLERS = {
    "add_category": handle_add_category,
    "edit_category": handle_edit_category,
    "delete_category": handle_delete_category,
    "add_product": handle_add_product,
    "edit_product": handle_edit_product,
    "delete_product": handle_delete_product,
    "toggle_product": handle_toggle_product,
}
