import requests

print("=== Cloud Backend Verification ===")
print()

# Products
r = requests.get('https://suzz-cloud.onrender.com/api/products')
products = r.json()
print(f"Products: {len(products)}")
if products:
    print(f"  - First product ID: {products[0].get('id')}")
    print(f"  - First product name: {products[0].get('name')}")
    print(f"  - First product price: {products[0].get('price')}")

print()

# Categories
r = requests.get('https://suzz-cloud.onrender.com/api/categories')
categories = r.json()
print(f"Categories: {len(categories)}")
if categories:
    print(f"  - First category ID: {categories[0].get('id')}")
    print(f"  - First category name: {categories[0].get('name')}")

print()

# Shifts
r = requests.get('https://suzz-cloud.onrender.com/api/shifts')
shifts = r.json()
print(f"Shifts: {len(shifts)}")
if shifts:
    print(f"  - First shift: {shifts[0].get('shift_name')}")
    print(f"  - Revenue: {shifts[0].get('total_revenue')}")

print()

# Statistics
r = requests.get('https://suzz-cloud.onrender.com/api/admin/statistics')
stats = r.json()
print(f"Statistics:")
print(f"  - Total Products: {stats['total_products']}")
print(f"  - Total Categories: {stats['total_categories']}")
print(f"  - Total Orders: {stats['all_time']['total_orders']}")
print(f"  - Today Sales: {stats['today']['total_sales']}")

print()
print("SUCCESS - Cloud backend is working!")
