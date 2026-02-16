import requests
import sqlite3
import json

CLOUD_URL = "https://suzz-cloud.onrender.com"
DB_PATH = "cashier.db"

# Try different possible secrets
POSSIBLE_SECRETS = [
    "change_me_to_secure_secret",
    "my_secure_password_123",
    "",  # Empty
    "suzz-cloud-secret",
    "SYNC_SECRET",
]

def test_secrets():
    print("--- Testing Different Secrets ---")
    
    # Get a product to sync
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products LIMIT 1")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print("No products to test with")
        return
    
    data = [dict(row) for row in rows]
    # Remove images
    for item in data:
        item.pop('image', None)
        item.pop('image_path', None)
    
    print(f"Testing with {len(data)} product(s)...\\n")
    
    for secret in POSSIBLE_SECRETS:
        print(f"Testing Secret: '{secret[:20]}{'...' if len(secret) > 20 else ''}'")
        
        headers = {
            "Content-Type": "application/json",
            "X-Sync-Secret": secret
        }
        
        try:
            response = requests.post(
                f"{CLOUD_URL}/api/sync/products", 
                json=data, 
                headers=headers, 
                timeout=10
            )
            
            print(f"  Status: {response.status_code}")
            if response.status_code == 200:
                print(f"  ✅ SUCCESS! Correct secret is: '{secret}'")
                print(f"  Response: {response.text[:200]}")
                return secret
            else:
                print(f"  Response: {response.text[:100]}")
        except Exception as e:
            print(f"  Error: {e}")
        
        print()
    
    print("❌ None of the secrets worked!")
    return None

if __name__ == "__main__":
    test_secrets()
