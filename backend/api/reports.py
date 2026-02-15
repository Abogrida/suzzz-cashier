from fastapi import APIRouter, HTTPException, Query
from db import get_db
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter()

class ReportSummary(BaseModel):
    total_sales: float
    total_cash: float
    total_card: float
    total_deficit: float
    total_surplus: float
    total_orders: int
    orders: List[dict]

@router.get("/reports/summary", response_model=ReportSummary)
def get_report_summary(
    start_date: str = Query(..., description="YYYY-MM-DD"),
    end_date: str = Query(..., description="YYYY-MM-DD")
):
    db = get_db()
    cursor = db.cursor()
    
    try:
        # 1. Sales Summary from Invoices
        # Ensure we look at date part of created_at
        cursor.execute("""
            SELECT 
                SUM(net_amount) as total_sales,
                SUM(CASE WHEN payment_method = 'cash' THEN net_amount ELSE 0 END) as total_cash,
                SUM(CASE WHEN payment_method = 'card' THEN net_amount ELSE 0 END) as total_card,
                COUNT(*) as total_orders
            FROM invoices 
            WHERE DATE(created_at) BETWEEN ? AND ?
        """, (start_date, end_date))
        
        sales_data = cursor.fetchone()
        
        total_sales = sales_data["total_sales"] or 0.0
        total_cash = sales_data["total_cash"] or 0.0
        total_card = sales_data["total_card"] or 0.0
        total_orders = sales_data["total_orders"] or 0
        
        # 2. Deficit/Surplus from Shifts
        # Deficit is negative cash_difference, Surplus is positive
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN cash_difference < 0 THEN cash_difference ELSE 0 END) as total_deficit,
                SUM(CASE WHEN cash_difference > 0 THEN cash_difference ELSE 0 END) as total_surplus
            FROM shifts 
            WHERE shift_date BETWEEN ? AND ? AND status = 'closed'
        """, (start_date, end_date))
        
        shift_data = cursor.fetchone()
        
        total_deficit = shift_data["total_deficit"] or 0.0
        total_surplus = shift_data["total_surplus"] or 0.0
        
        # 3. Get Orders List (Same format as orders page)
        cursor.execute("""
            SELECT * FROM orders 
            WHERE DATE(created_at) BETWEEN ? AND ?
            ORDER BY created_at DESC
        """, (start_date, end_date))
        
        orders_rows = cursor.fetchall()
        orders_list = []
        
        for order in orders_rows:
            # We need to serialize this similarly to the orders list
            orders_list.append({
                "id": order["id"],
                "order_number": order["order_number"],
                "table_number": order["table_number"],
                "customer_name": order["customer_name"],
                "customer_phone": order["customer_phone"],
                "status": order["status"],
                "total_amount": float(order["total_amount"]),
                "discount_amount": float(order["discount_amount"] or 0),
                "tax_amount": float(order["tax_amount"] or 0),
                "vat_amount": float(order["vat_amount"] or 0),
                "branch": order["branch"],
                "cashier": order["cashier"],
                "created_at": order["created_at"],
                "items": [] # We don't fetch items here to save bandwidth, unless requested? 
                            # User said "Same detail as orders page", which usually includes total quantity.
                            # Let's simple-fetch items count.
            })
            
        # Optimization: Fetch items for count? 
        # For now, let's keep it simple. If the user wants full details "exactly like orders page", 
        # the frontend `displayOrdersTable` expects items array to calc quantity.
        
        # Let's populate items minimally or fetch them properly.
        # fetching all items for a raport might be heavy. 
        # Let's do a second pass to get items if the list isn't huge, or just fetch basic count.
        
        for order_dict in orders_list:
             cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order_dict["id"],))
             items = cursor.fetchall()
             order_dict["items"] = [dict(item) for item in items]

        return {
            "total_sales": total_sales,
            "total_cash": total_cash,
            "total_card": total_card,
            "total_deficit": total_deficit,
            "total_surplus": total_surplus,
            "total_orders": total_orders,
            "orders": orders_list
        }
        
    except Exception as e:
        print(f"Error generating report: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
