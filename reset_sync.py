import sqlite3

DB_PATH = "cashier.db"

def reset_sync_status():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        tables = ["categories", "products", "settings", "orders", "invoices", "shifts"]
        
        for table in tables:
            try:
                cursor.execute(f"UPDATE {table} SET is_synced = 0")
                print(f"Reset {cursor.rowcount} records in {table}")
            except Exception as e:
                print(f"Error resetting {table}: {e}")
        
        conn.commit()
        conn.close()
        print("Sync status reset successfully.")
    except Exception as e:
        print(f"Database error: {e}")

if __name__ == "__main__":
    reset_sync_status()
