import requests
import sqlite3
import os

# Test with current secret
SYNC_SECRET = os.environ.get("SYNC_SECRET", "my_secure_password_123")
CLOUD_URL = "https://suzz-cloud.onrender.com"

print(f"Testing sync with secret: {SYNC_SECRET[:10]}...")

# Get a product
conn = sqlite3.connect('cashier.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
cursor.execute("SELECT * FROM products LIMIT 1")
row = cursor.fetchone()
conn.close()

if not row:
    print("No products to test")
    exit(1)

data = [dict(row)]
# Remove images
for item in data:
    item.pop('image', None)
    item.pop('image_path', None)

print(f"Sending product: {data[0].get('name', 'N/A')}")

headers = {
    "Content-Type": "application/json",
    "X-Sync-Secret": SYNC_SECRET
}

try:
    response = requests.post(
        f"{CLOUD_URL}/api/sync/products",
        json=data,
        headers=headers,
        timeout=10
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text[:200]}")
    
    if response.status_code == 200:
        print("\nSUCCESS - Sync is working!")
        resp_data = response.json()
        print(f"Synced: {resp_data.get('synced_count', 0)} products")
    else:
        print(f"\nFAILED - Error: {response.text}")
        
except Exception as e:
    print(f"ERROR: {e}")
