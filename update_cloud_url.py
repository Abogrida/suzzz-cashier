import sqlite3
import os

DB_PATH = "cashier.db"

def update_cloud_url():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if key exists
        cursor.execute("SELECT 1 FROM settings WHERE key = 'cloud_url'")
        if cursor.fetchone():
            cursor.execute("UPDATE settings SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE key = 'cloud_url'", ("https://suzz-cloud.onrender.com",))
        else:
            cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?)", ('cloud_url', "https://suzz-cloud.onrender.com"))
        
        conn.commit()
        print("Successfully updated cloud_url to https://suzz-cloud.onrender.com")
        
        # Verify
        cursor.execute("SELECT value FROM settings WHERE key = 'cloud_url'")
        print(f"Current Value: {cursor.fetchone()[0]}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    update_cloud_url()
