import requests
import sqlite3
import json

CLOUD_URL = "https://suzz-cloud.onrender.com"
DB_PATH = "cashier.db"

def manual_sync_products():
    print("--- Manual Sync Products Debug ---")
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # This enables column access by name
        cursor = conn.cursor()
        
        # Get ALL products (force sync)
        cursor.execute("SELECT * FROM products LIMIT 5")
        rows = cursor.fetchall()
        
        if not rows:
            print("No products found in DB.")
            return

        data = [dict(row) for row in rows]
        
        # Exclude images
        for item in data:
            if 'image' in item:
                # print("Removing image data...")
                item.pop('image')
            if 'image_path' in item:
                item.pop('image_path')
                
        print(f"Attempting to force sync {len(data)} products...")
        # print(f"Data sample: {data[0]}")
        
        headers = {
            "Content-Type": "application/json",
            "X-Sync-Secret": "change_me_to_secure_secret" 
        }
        
        print(f"Sending to {CLOUD_URL}/api/sync/products")
        response = requests.post(f"{CLOUD_URL}/api/sync/products", json=data, headers=headers, timeout=10)
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    manual_sync_products()
