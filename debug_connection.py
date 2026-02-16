import requests
import sqlite3
import time

CLOUD_URL = "https://suzz-cloud.onrender.com"
DB_PATH = "cashier.db"

def check_heartbeat():
    print(f"--- Checking Connection to {CLOUD_URL} ---")
    try:
        start = time.time()
        response = requests.post(f"{CLOUD_URL}/api/sync/heartbeat", timeout=10)
        end = time.time()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        print(f"Time: {end - start:.2f}s")
        if response.status_code == 200:
            print("[OK] Connection Successful")
        else:
            print("[FAIL] Connection Failed")
    except Exception as e:
        print(f"[ERROR] Connection Error: {e}")

def check_db_status():
    print(f"\n--- Checking Local Database ({DB_PATH}) ---")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check cloud_url
        cursor.execute("SELECT value FROM settings WHERE key = 'cloud_url'")
        row = cursor.fetchone()
        print(f"Setting 'cloud_url': {row[0] if row else 'NOT FOUND'}")
        
        # Check cloud_connection_status
        cursor.execute("SELECT value, updated_at FROM settings WHERE key = 'cloud_connection_status'")
        row = cursor.fetchone()
        if row:
            print(f"Setting 'cloud_connection_status': {row[0]}")
            print(f"Last Updated: {row[1]}")
        else:
            print("Setting 'cloud_connection_status': NOT FOUND")
            
        conn.close()
    except Exception as e:
        print(f"[ERROR] Database Error: {e}")

if __name__ == "__main__":
    check_heartbeat()
    check_db_status()
