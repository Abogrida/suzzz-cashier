from fastapi import APIRouter, HTTPException
from db import get_db
from typing import List
import sqlite3

router = APIRouter()

@router.get("/additions")
def get_additions():
    """Get all available product additions"""
    db = get_db()
    try:
        cursor = db.cursor()
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='product_additions'")
        if not cursor.fetchone():
            # Table doesn't exist, create it
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS product_additions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Insert default additions
            default_additions = [
                ("سادة",),
                ("محوج",),
                ("مضبوط",),
                ("فاتح",),
                ("غامق",),
                ("وسط",),
                ("علي الريحه",),
                ("زياده",),
                ("مانو",),
            ]
            cursor.executemany("INSERT INTO product_additions (name) VALUES (?)", default_additions)
            db.commit()
        
        cursor.execute("SELECT id, name FROM product_additions ORDER BY name")
        additions = [{"id": row["id"], "name": row["name"]} for row in cursor.fetchall()]
        return additions
    except Exception as e:
        print(f"Error getting additions: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        if db:
            db.close()

@router.post("/additions")
def create_addition(name: str):
    """Create a new addition"""
    db = get_db()
    try:
        cursor = db.cursor()
        cursor.execute("INSERT INTO product_additions (name) VALUES (?)", (name,))
        db.commit()
        return {"id": cursor.lastrowid, "name": name}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Addition already exists")
    except Exception as e:
        print(f"Error creating addition: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating addition: {str(e)}")
    finally:
        if db:
            db.close()

