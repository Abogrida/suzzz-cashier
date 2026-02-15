from fastapi import APIRouter, HTTPException
from db import get_db
from models import InvoiceResponse, InvoiceReport, OrderItemResponse
from datetime import datetime, date
from typing import Optional
import os
import sys

router = APIRouter()

# PDF generation disabled - all printing goes directly to USB printer
REPORTLAB_AVAILABLE = False

@router.get("/invoices", response_model=list[InvoiceResponse])
def get_invoices(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = None,
    invoice_number: Optional[str] = None,
    customer_name: Optional[str] = None,
    customer_phone: Optional[str] = None,
    order_number: Optional[str] = None,
    branch: Optional[str] = None,
    cashier: Optional[str] = None
):
    """Get all invoices with comprehensive filters"""
    db = get_db()
    cursor = db.cursor()
    
    query = """
        SELECT i.*, o.order_number, o.table_number, o.customer_name, o.created_at as order_created_at
        FROM invoices i
        JOIN orders o ON i.order_id = o.id
        WHERE 1=1
    """
    params = []
    
    if start_date:
        query += " AND DATE(i.created_at) >= ?"
        params.append(start_date)
    if end_date:
        query += " AND DATE(i.created_at) <= ?"
        params.append(end_date)
    if status:
        query += " AND i.status = ?"
        params.append(status)
    if invoice_number:
        query += " AND i.invoice_number LIKE ?"
        params.append(f"%{invoice_number}%")
    if customer_name:
        query += " AND (i.customer_name LIKE ? OR o.customer_name LIKE ?)"
        params.append(f"%{customer_name}%")
        params.append(f"%{customer_name}%")
    if customer_phone:
        query += " AND (i.customer_phone LIKE ? OR o.customer_phone LIKE ?)"
        params.append(f"%{customer_phone}%")
        params.append(f"%{customer_phone}%")
    if order_number:
        query += " AND (i.order_number LIKE ? OR o.order_number = ?)"
        params.append(f"%{order_number}%")
        try:
            params.append(int(order_number))
        except:
            params.append(0)
    if branch:
        query += " AND i.branch LIKE ?"
        params.append(f"%{branch}%")
    if cashier:
        query += " AND i.cashier LIKE ?"
        params.append(f"%{cashier}%")
    
    query += " ORDER BY i.created_at DESC"
    cursor.execute(query, params)
    invoices = cursor.fetchall()
    
    result = []
    for invoice_row in invoices:
        invoice = dict(invoice_row)
        # Get order items
        cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (invoice["order_id"],))
        items = cursor.fetchall()
        
        # Calculate quantities and amounts
        total_quantity = sum(item["quantity"] for item in items)
        discount_amount = invoice.get("discount_amount", 0) or 0
        tax_amount = invoice.get("tax_amount", 0) or 0
        vat_amount = invoice.get("vat_amount", 0) or 0
        total_before_vat = invoice.get("total_before_vat", 0) or (invoice["total_amount"] - vat_amount - tax_amount - discount_amount)
        net_amount = invoice.get("net_amount", 0) or invoice["total_amount"]
        
        result.append(InvoiceResponse(
            id=invoice["id"],
            invoice_number=invoice["invoice_number"],
            order_id=invoice["order_id"],
            order_number=str(invoice["order_number"]),
            table_number=invoice.get("table_number", 0) or 0,
            customer_name=invoice.get("customer_name"),
            customer_phone=invoice.get("customer_phone"),
            invoice_location=invoice.get("invoice_location", "سفری"),
            quantity=total_quantity,
            discount_amount=discount_amount,
            tax_amount=tax_amount,
            total_before_vat=total_before_vat,
            vat_amount=vat_amount,
            net_amount=net_amount,
            total_amount=invoice["total_amount"],
            status=invoice["status"],
            payment_method=invoice["payment_method"],
            branch=invoice.get("branch", "الفرع الرئيسي"),
            cashier=invoice.get("cashier", "كاشير"),
            created_at=invoice["created_at"],
            items=[OrderItemResponse(
                id=item["id"],
                product_id=item["product_id"],
                product_name=item["product_name"],
                quantity=item["quantity"],
                price=item["price"],
                total=item["total"],
                size=item["size"] if "size" in item.keys() else None,
                additions=item["additions"] if "additions" in item.keys() else None,
                notes=item["notes"] if "notes" in item.keys() else None
            ) for item in items]
        ))
    
    db.close()
    return result

@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(invoice_id: int):
    """Get a specific invoice by ID"""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("""
        SELECT i.*, o.order_number, o.table_number, o.customer_name, o.created_at as order_created_at
        FROM invoices i
        JOIN orders o ON i.order_id = o.id
        WHERE i.id = ?
    """, (invoice_id,))
    invoice_row = cursor.fetchone()
    
    if not invoice_row:
        db.close()
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Convert to dict for .get usage
    invoice = dict(invoice_row)
    
    # Get order items
    cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (invoice["order_id"],))
    items = cursor.fetchall()
    db.close()
    
    # Calculate quantities and amounts
    total_quantity = sum(item["quantity"] for item in items)
    discount_amount = invoice.get("discount_amount", 0) or 0
    tax_amount = invoice.get("tax_amount", 0) or 0
    vat_amount = invoice.get("vat_amount", 0) or 0
    total_before_vat = invoice.get("total_before_vat", 0) or (invoice["total_amount"] - vat_amount - tax_amount - discount_amount)
    net_amount = invoice.get("net_amount", 0) or invoice["total_amount"]
    
    return InvoiceResponse(
        id=invoice["id"],
        invoice_number=invoice["invoice_number"],
        order_id=invoice["order_id"],
        order_number=str(invoice["order_number"]),
        table_number=invoice.get("table_number", 0) or 0,
        customer_name=invoice.get("customer_name"),
        customer_phone=invoice.get("customer_phone"),
        invoice_location=invoice.get("invoice_location", "سفری"),
        quantity=total_quantity,
        discount_amount=discount_amount,
        tax_amount=tax_amount,
        total_before_vat=total_before_vat,
        vat_amount=vat_amount,
        net_amount=net_amount,
        total_amount=invoice["total_amount"],
        status=invoice["status"],
        payment_method=invoice["payment_method"],
        branch=invoice.get("branch", "الفرع الرئيسي"),
        cashier=invoice.get("cashier", "كاشير"),
        created_at=invoice["created_at"],
        items=[OrderItemResponse(
            id=item["id"],
            product_id=item["product_id"],
            product_name=item["product_name"],
            quantity=item["quantity"],
            price=item["price"],
            total=item["total"],
            size=item["size"] if "size" in item.keys() else None,
            additions=item["additions"] if "additions" in item.keys() else None,
            notes=item["notes"] if "notes" in item.keys() else None
        ) for item in items]
    )

@router.get("/invoices/reports/daily", response_model=InvoiceReport)
def get_daily_report(report_date: Optional[str] = None):
    """Get daily invoice report"""
    if not report_date:
        report_date = date.today().isoformat()
    
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("""
        SELECT i.*, o.order_number, o.table_number, o.customer_name, o.created_at as order_created_at
        FROM invoices i
        JOIN orders o ON i.order_id = o.id
        WHERE DATE(i.created_at) = ?
        ORDER BY i.created_at DESC
    """, (report_date,))
    invoices = cursor.fetchall()
    
    total_revenue = sum(float(inv["total_amount"]) for inv in invoices)
    
    result_invoices = []
    for invoice_row in invoices:
        invoice = dict(invoice_row)
        cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (invoice["order_id"],))
        items = cursor.fetchall()
        
        # Calculate quantities and amounts
        total_quantity = sum(item["quantity"] for item in items)
        discount_amount = invoice.get("discount_amount", 0) or 0
        tax_amount = invoice.get("tax_amount", 0) or 0
        vat_amount = invoice.get("vat_amount", 0) or 0
        total_before_vat = invoice.get("total_before_vat", 0) or (invoice["total_amount"] - vat_amount - tax_amount - discount_amount)
        net_amount = invoice.get("net_amount", 0) or invoice["total_amount"]
        
        result_invoices.append(InvoiceResponse(
            id=invoice["id"],
            invoice_number=invoice["invoice_number"],
            order_id=invoice["order_id"],
            order_number=str(invoice["order_number"]),
            table_number=invoice.get("table_number", 0) or 0,
            customer_name=invoice.get("customer_name"),
            customer_phone=invoice.get("customer_phone"),
            invoice_location=invoice.get("invoice_location", "سفری"),
            quantity=total_quantity,
            discount_amount=discount_amount,
            tax_amount=tax_amount,
            total_before_vat=total_before_vat,
            vat_amount=vat_amount,
            net_amount=net_amount,
            total_amount=invoice["total_amount"],
            status=invoice["status"],
            payment_method=invoice["payment_method"],
            branch=invoice.get("branch", "الفرع الرئيسي"),
            cashier=invoice.get("cashier", "كاشير"),
            created_at=invoice["created_at"],
            items=[OrderItemResponse(
                id=item["id"],
                product_id=item["product_id"],
                product_name=item["product_name"],
                quantity=item["quantity"],
                price=item["price"],
                total=item["total"],
                size=item["size"] if "size" in item.keys() else None,
                additions=item["additions"] if "additions" in item.keys() else None,
                notes=item["notes"] if "notes" in item.keys() else None
            ) for item in items]
        ))
    
    db.close()
    
    return InvoiceReport(
        total_invoices=len(result_invoices),
        total_revenue=total_revenue,
        invoices=result_invoices
    )

@router.get("/invoices/reports/monthly", response_model=InvoiceReport)
def get_monthly_report(year: Optional[int] = None, month: Optional[int] = None):
    """Get monthly invoice report"""
    if not year:
        year = date.today().year
    if not month:
        month = date.today().month
    
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("""
        SELECT i.*, o.order_number, o.table_number, o.customer_name, o.created_at as order_created_at
        FROM invoices i
        JOIN orders o ON i.order_id = o.id
        WHERE strftime('%Y', i.created_at) = ? AND strftime('%m', i.created_at) = ?
        ORDER BY i.created_at DESC
    """, (str(year), f"{month:02d}"))
    invoices = cursor.fetchall()
    
    total_revenue = sum(float(inv["total_amount"]) for inv in invoices)
    
    result_invoices = []
    for invoice_row in invoices:
        invoice = dict(invoice_row)
        cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (invoice["order_id"],))
        items = cursor.fetchall()
        
        # Calculate quantities and amounts
        total_quantity = sum(item["quantity"] for item in items)
        discount_amount = invoice.get("discount_amount", 0) or 0
        tax_amount = invoice.get("tax_amount", 0) or 0
        vat_amount = invoice.get("vat_amount", 0) or 0
        total_before_vat = invoice.get("total_before_vat", 0) or (invoice["total_amount"] - vat_amount - tax_amount - discount_amount)
        net_amount = invoice.get("net_amount", 0) or invoice["total_amount"]
        
        result_invoices.append(InvoiceResponse(
            id=invoice["id"],
            invoice_number=invoice["invoice_number"],
            order_id=invoice["order_id"],
            order_number=str(invoice["order_number"]),
            table_number=invoice.get("table_number", 0) or 0,
            customer_name=invoice.get("customer_name"),
            customer_phone=invoice.get("customer_phone"),
            invoice_location=invoice.get("invoice_location", "سفری"),
            quantity=total_quantity,
            discount_amount=discount_amount,
            tax_amount=tax_amount,
            total_before_vat=total_before_vat,
            vat_amount=vat_amount,
            net_amount=net_amount,
            total_amount=invoice["total_amount"],
            status=invoice["status"],
            payment_method=invoice["payment_method"],
            branch=invoice.get("branch", "الفرع الرئيسي"),
            cashier=invoice.get("cashier", "كاشير"),
            created_at=invoice["created_at"],
            items=[OrderItemResponse(
                id=item["id"],
                product_id=item["product_id"],
                product_name=item["product_name"],
                quantity=item["quantity"],
                price=item["price"],
                total=item["total"],
                size=item["size"] if "size" in item.keys() else None,
                additions=item["additions"] if "additions" in item.keys() else None,
                notes=item["notes"] if "notes" in item.keys() else None
            ) for item in items]
        ))
    
    db.close()
    
    return InvoiceReport(
        total_invoices=len(result_invoices),
        total_revenue=total_revenue,
        invoices=result_invoices
    )

# PDF download endpoint completely removed - all printing goes directly to USB printer
# No PDF files are created or downloaded anywhere in the system

@router.get("/invoices/{invoice_id}/download-pdf")
@router.post("/invoices/{invoice_id}/download-pdf")
@router.get("/invoices/{invoice_id}/pdf")
@router.post("/invoices/{invoice_id}/pdf")
async def download_invoice_pdf_disabled(invoice_id: int):
    """PDF download FORCE DISABLED - all printing goes directly to USB printer"""
    print(f"🚫🚫🚫 FORCE BLOCKED PDF DOWNLOAD ATTEMPT for invoice {invoice_id}")
    from fastapi.responses import JSONResponse
    # Return JSON instead of text to prevent browser from trying to open as PDF
    return JSONResponse(
        status_code=404,
        content={
            "error": "PDF download completely disabled",
            "message": "Printing goes directly to USB printer only",
            "blocked": True
        },
        headers={
            "X-PDF-Blocked": "true",
            "Content-Type": "application/json",
            "Content-Disposition": "inline",
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )



