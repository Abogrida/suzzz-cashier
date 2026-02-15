from fastapi import APIRouter, HTTPException
from db import get_db
from datetime import datetime, date
from typing import Dict, Any
import socket

router = APIRouter()

def get_local_ip():
    """Get local IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

@router.get("/network/info")
def get_network_info():
    """Get network information for admin panel"""
    local_ip = get_local_ip()
    return {
        "local_ip": local_ip,
        "main_server_url": f"http://{local_ip}:3000",
        "tablet_server_url": f"http://{local_ip}:3001/tablet",
        "local_main_url": "http://localhost:3000",
        "local_tablet_url": "http://localhost:3001/tablet"
    }

@router.get("/reports/daily")
def get_daily_report(report_date: str = None):
    """Get daily sales report"""
    if not report_date:
        report_date = date.today().isoformat()
    
    db = get_db()
    cursor = db.cursor()
    
    # Total sales
    cursor.execute("""
        SELECT COALESCE(SUM(total_amount), 0) as total
        FROM orders 
        WHERE DATE(created_at) = ? AND status = 'completed'
    """, (report_date,))
    total_sales = cursor.fetchone()["total"]
    
    # Order count
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM orders 
        WHERE DATE(created_at) = ? AND status = 'completed'
    """, (report_date,))
    order_count = cursor.fetchone()["count"]
    
    # Best sellers
    cursor.execute("""
        SELECT oi.product_name, SUM(oi.quantity) as total_quantity, SUM(oi.total) as total_revenue
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        WHERE DATE(o.created_at) = ? AND o.status = 'completed'
        GROUP BY oi.product_name
        ORDER BY total_quantity DESC
        LIMIT 10
    """, (report_date,))
    best_sellers = [dict(row) for row in cursor.fetchall()]
    
    db.close()
    
    return {
        "date": report_date,
        "total_sales": total_sales,
        "order_count": order_count,
        "best_sellers": best_sellers
    }

@router.get("/reports/monthly")
def get_monthly_report(year: int = None, month: int = None):
    """Get monthly sales report"""
    if not year:
        year = date.today().year
    if not month:
        month = date.today().month
    
    db = get_db()
    cursor = db.cursor()
    
    # Total sales
    cursor.execute("""
        SELECT COALESCE(SUM(total_amount), 0) as total
        FROM orders 
        WHERE strftime('%Y', created_at) = ? AND strftime('%m', created_at) = ? AND status = 'completed'
    """, (str(year), f"{month:02d}"))
    total_sales = cursor.fetchone()["total"]
    
    # Order count
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM orders 
        WHERE strftime('%Y', created_at) = ? AND strftime('%m', created_at) = ? AND status = 'completed'
    """, (str(year), f"{month:02d}"))
    order_count = cursor.fetchone()["count"]
    
    # Daily breakdown
    cursor.execute("""
        SELECT DATE(created_at) as date, COUNT(*) as order_count, SUM(total_amount) as total
        FROM orders 
        WHERE strftime('%Y', created_at) = ? AND strftime('%m', created_at) = ? AND status = 'completed'
        GROUP BY DATE(created_at)
        ORDER BY date
    """, (str(year), f"{month:02d}"))
    daily_breakdown = [dict(row) for row in cursor.fetchall()]
    
    db.close()
    
    return {
        "year": year,
        "month": month,
        "total_sales": total_sales,
        "order_count": order_count,
        "daily_breakdown": daily_breakdown
    }

@router.get("/reports/products")
def get_products_report():
    """Get products sales report"""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("""
        SELECT 
            oi.product_name,
            SUM(oi.quantity) as total_quantity,
            SUM(oi.total) as total_revenue,
            COUNT(DISTINCT oi.order_id) as order_count
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        WHERE o.status = 'completed'
        GROUP BY oi.product_name
        ORDER BY total_revenue DESC
    """)
    products = [dict(row) for row in cursor.fetchall()]
    
    db.close()
    
    return {"products": products}

@router.get("/statistics")
def get_statistics():
    """Get comprehensive statistics"""
    db = get_db()
    cursor = db.cursor()
    
    # Today's stats
    today = date.today().isoformat()
    cursor.execute("""
        SELECT 
            COUNT(*) as order_count,
            COALESCE(SUM(total_amount), 0) as total_sales
        FROM orders 
        WHERE DATE(created_at) = ? AND status = 'completed'
    """, (today,))
    today_stats = dict(cursor.fetchone())
    
    # All time stats
    cursor.execute("""
        SELECT 
            COUNT(*) as total_orders,
            COALESCE(SUM(total_amount), 0) as total_revenue,
            COUNT(DISTINCT DATE(created_at)) as active_days
        FROM orders 
        WHERE status = 'completed'
    """)
    all_time_stats = dict(cursor.fetchone())
    
    # Pending orders
    cursor.execute("SELECT COUNT(*) as count FROM orders WHERE status = 'pending'")
    pending_orders = cursor.fetchone()["count"]
    
    # Recent orders
    cursor.execute("""
        SELECT 
            order_number,
            table_number,
            total_amount,
            created_at,
            status
        FROM orders 
        ORDER BY created_at DESC 
        LIMIT 20
    """)
    recent_orders = [dict(row) for row in cursor.fetchall()]
    
    # Top products
    cursor.execute("""
        SELECT 
            oi.product_name,
            SUM(oi.quantity) as total_quantity,
            SUM(oi.total) as total_revenue
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        WHERE o.status = 'completed'
        GROUP BY oi.product_name
        ORDER BY total_revenue DESC
        LIMIT 10
    """)
    top_products = [dict(row) for row in cursor.fetchall()]
    
    # Total products count
    cursor.execute("SELECT COUNT(*) as count FROM products")
    total_products = cursor.fetchone()["count"]
    
    # Total categories count
    cursor.execute("SELECT COUNT(*) as count FROM categories")
    total_categories = cursor.fetchone()["count"]
    
    db.close()
    
    return {
        "today": today_stats,
        "all_time": all_time_stats,
        "pending_orders": pending_orders,
        "recent_orders": recent_orders,
        "top_products": top_products,
        "total_products": total_products,
        "total_categories": total_categories
    }

