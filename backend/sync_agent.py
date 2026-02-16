import threading
import time
import requests
import sqlite3
import os
import sys
import json
from datetime import datetime

# Add parent directory to path to import db
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from db import get_db

# Configuration
CLOUD_API_URL = "https://suzz-cloud.onrender.com" # Updated after deployment
SYNC_INTERVAL = 10 # Seconds
BATCH_SIZE = 50

class SyncAgent:
    def __init__(self):
        self.running = False
        self.thread = None
        
    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        print("[SyncAgent] Started background sync service")
        
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
        print("[SyncAgent] Stopped background sync service")

    def _run_loop(self):
        while self.running:
            try:
                if self._check_internet():
                    self._sync_data()
                else:
                    # print("[SyncAgent] No internet connection")
                    pass
            except Exception as e:
                print(f"[SyncAgent] Error in sync loop: {e}")
            
            time.sleep(SYNC_INTERVAL)

    def _check_internet(self):
        try:
            # Quick check to Google DNS or Cloudflare
            requests.get("https://1.1.1.1", timeout=3)
            return True
        except:
            return False

    def _sync_data(self):
        # Check connection and update status
        is_connected = self._check_cloud_connection()
        self._update_connection_status(is_connected)
        
        if not is_connected:
            return

        # Sync Categories first (dependency for products)
        self._sync_table("categories", "/api/sync/categories")

        # Sync Products
        self._sync_table("products", "/api/sync/products")

        # Sync Settings
        self._sync_table("settings", "/api/sync/settings")

        # Sync Orders
        self._sync_table("orders", "/api/sync/orders")
        
        # Sync Invoices
        self._sync_table("invoices", "/api/sync/invoices")
        
        # Sync Shifts
        self._sync_table("shifts", "/api/sync/shifts")

    def _check_cloud_connection(self):
        try:
            # We assume the cloud URL is configured in settings or hardcoded
            # This logic is duplicated in _sync_table, should ideally be refactored to a property or helper
            db = get_db()
            cursor = db.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = 'cloud_url'")
            setting = cursor.fetchone()
            cloud_url = setting['value'] if setting else CLOUD_API_URL
            db.close()
            
            if not cloud_url or "YOUR_RENDER_APP_URL" in cloud_url:
                return False
                
            response = requests.post(f"{cloud_url}/api/sync/heartbeat", timeout=5)
            return response.status_code == 200
        except:
            return False

    def _update_connection_status(self, is_connected):
        try:
            db = get_db()
            cursor = db.cursor()
            status_value = "connected" if is_connected else "disconnected"
            
            # Check if key exists
            cursor.execute("SELECT 1 FROM settings WHERE key = 'cloud_connection_status'")
            if cursor.fetchone():
                cursor.execute("UPDATE settings SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE key = 'cloud_connection_status'", (status_value,))
            else:
                cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?)", ('cloud_connection_status', status_value))
            
            db.commit()
            db.close()
        except Exception as e:
            print(f"[SyncAgent] Error updating connection status: {e}")

    def _sync_table(self, table_name, api_endpoint):
        db = None
        try:
            db = get_db()
            cursor = db.cursor()
            
            # Get unsynced records
            cursor.execute(f"SELECT * FROM {table_name} WHERE is_synced = 0 LIMIT ?", (BATCH_SIZE,))
            rows = cursor.fetchall()
            
            if not rows:
                return

            print(f"[SyncAgent] Found {len(rows)} unsynced records in {table_name}")
            
            # Convert rows to dict
            data = [dict(row) for row in rows]
            
            # Remove image data to save bandwidth
            for item in data:
                if 'image' in item:
                    item.pop('image')
                if 'image_path' in item:
                    item.pop('image_path')
            
            # Send to Cloud
            # Note: We need a way to authenticate. For now, we'll use a simple approach 
            # or rely on the endpoint being open/protected by a shared secret key in headers
            headers = {
                "Content-Type": "application/json",
                "X-Sync-Secret": "change_me_to_secure_secret" 
            }
            
            # We assume the cloud URL is configured in settings or hardcoded for now
            # Let's try to get it from settings DB if possible, or use global
            cursor.execute("SELECT value FROM settings WHERE key = 'cloud_url'")
            setting = cursor.fetchone()
            cloud_url = setting['value'] if setting else CLOUD_API_URL
            
            if not cloud_url or "YOUR_RENDER_APP_URL" in cloud_url:
                print("[SyncAgent] Cloud URL not configured")
                return

            response = requests.post(f"{cloud_url}{api_endpoint}", json=data, headers=headers, timeout=10)
            
            if response.status_code == 200:
                # Mark as synced
                ids = [row['id'] for row in rows]
                placeholders = ','.join(['?'] * len(ids))
                cursor.execute(f"UPDATE {table_name} SET is_synced = 1 WHERE id IN ({placeholders})", ids)
                db.commit()
                print(f"[SyncAgent] Successfully synced {len(rows)} records from {table_name}")
            else:
                print(f"[SyncAgent] Failed to sync {table_name}: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"[SyncAgent] Error syncing {table_name}: {e}")
        finally:
            if db:
                db.close()

# Singleton instance
sync_agent = SyncAgent()
