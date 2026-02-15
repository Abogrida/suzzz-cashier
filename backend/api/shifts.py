from fastapi import APIRouter, HTTPException
from db import get_db
from models import (
    ShiftSettingsUpdate, ShiftSettingsResponse, 
    ShiftOpenRequest, ShiftResponse, ShiftReportResponse,
    OrderResponse, InvoiceResponse, OrderItemResponse
)
from typing import Optional, List
from datetime import datetime, date
from websocket_manager import manager
import re

router = APIRouter()

@router.get("/shifts/settings", response_model=ShiftSettingsResponse)
def get_shift_settings():
    """Get shift settings"""
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT * FROM shift_settings ORDER BY id DESC LIMIT 1")
        settings = cursor.fetchone()
        db.close()
        
        if not settings:
            # Return default settings
            return ShiftSettingsResponse(
                id=0,
                number_of_shifts=2,
                shift1_name="صباحي",
                shift1_start_time="08:00",
                shift1_end_time="16:00",
                shift2_name="مسائي",
                shift2_start_time="16:00",
                shift2_end_time="00:00"
            )
        
        return ShiftSettingsResponse(
            id=settings["id"],
            number_of_shifts=settings["number_of_shifts"],
            shift1_name=settings["shift1_name"],
            shift1_start_time=settings["shift1_start_time"],
            shift1_end_time=settings["shift1_end_time"],
            shift2_name=settings["shift2_name"],
            shift2_start_time=settings["shift2_start_time"],
            shift2_end_time=settings["shift2_end_time"],
            shift3_name=settings["shift3_name"] if "shift3_name" in settings.keys() and settings["shift3_name"] else None,
            shift3_start_time=settings["shift3_start_time"] if "shift3_start_time" in settings.keys() and settings["shift3_start_time"] else None,
            shift3_end_time=settings["shift3_end_time"] if "shift3_end_time" in settings.keys() and settings["shift3_end_time"] else None
        )
    except Exception as e:
        db.close()
        raise HTTPException(status_code=500, detail=f"Error getting shift settings: {str(e)}")

@router.put("/shifts/settings", response_model=ShiftSettingsResponse)
async def update_shift_settings(settings: ShiftSettingsUpdate):
    """Update shift settings"""
    db = get_db()
    cursor = db.cursor()
    try:
        # Get existing settings
        cursor.execute("SELECT * FROM shift_settings ORDER BY id DESC LIMIT 1")
        existing = cursor.fetchone()
        
        if existing:
            # Update existing
            cursor.execute("""
                UPDATE shift_settings SET
                    number_of_shifts = ?,
                    shift1_name = ?,
                    shift1_start_time = ?,
                    shift1_end_time = ?,
                    shift2_name = ?,
                    shift2_start_time = ?,
                    shift2_end_time = ?,
                    shift3_name = ?,
                    shift3_start_time = ?,
                    shift3_end_time = ?,
                    updated_at = datetime('now', 'localtime')
                WHERE id = ?
            """, (
                settings.number_of_shifts,
                settings.shift1_name or existing["shift1_name"],
                settings.shift1_start_time or existing["shift1_start_time"],
                settings.shift1_end_time or existing["shift1_end_time"],
                settings.shift2_name or existing["shift2_name"],
                settings.shift2_start_time or existing["shift2_start_time"],
                settings.shift2_end_time or existing["shift2_end_time"],
                settings.shift3_name if settings.number_of_shifts >= 3 else None,
                settings.shift3_start_time if settings.number_of_shifts >= 3 else None,
                settings.shift3_end_time if settings.number_of_shifts >= 3 else None,
                existing["id"]
            ))
        else:
            # Create new
            cursor.execute("""
                INSERT INTO shift_settings (
                    number_of_shifts, shift1_name, shift1_start_time, shift1_end_time,
                    shift2_name, shift2_start_time, shift2_end_time,
                    shift3_name, shift3_start_time, shift3_end_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                settings.number_of_shifts,
                settings.shift1_name or "صباحي",
                settings.shift1_start_time or "08:00",
                settings.shift1_end_time or "16:00",
                settings.shift2_name or "مسائي",
                settings.shift2_start_time or "16:00",
                settings.shift2_end_time or "00:00",
                settings.shift3_name if settings.number_of_shifts >= 3 else None,
                settings.shift3_start_time if settings.number_of_shifts >= 3 else None,
                settings.shift3_end_time if settings.number_of_shifts >= 3 else None
            ))
        
        db.commit()
        
        # Get updated settings
        cursor.execute("SELECT * FROM shift_settings ORDER BY id DESC LIMIT 1")
        updated = cursor.fetchone()
        db.close()
        
        # Broadcast shift settings updated
        try:
            await manager.broadcast({"type": "shift_settings_updated"})
        except:
            pass
        
        return ShiftSettingsResponse(
            id=updated["id"],
            number_of_shifts=updated["number_of_shifts"],
            shift1_name=updated["shift1_name"],
            shift1_start_time=updated["shift1_start_time"],
            shift1_end_time=updated["shift1_end_time"],
            shift2_name=updated["shift2_name"],
            shift2_start_time=updated["shift2_start_time"],
            shift2_end_time=updated["shift2_end_time"],
            shift3_name=updated["shift3_name"] if "shift3_name" in updated.keys() and updated["shift3_name"] else None,
            shift3_start_time=updated["shift3_start_time"] if "shift3_start_time" in updated.keys() and updated["shift3_start_time"] else None,
            shift3_end_time=updated["shift3_end_time"] if "shift3_end_time" in updated.keys() and updated["shift3_end_time"] else None
        )
    except Exception as e:
        db.close()
        raise HTTPException(status_code=500, detail=f"Error updating shift settings: {str(e)}")

@router.get("/shifts/current", response_model=Optional[dict])
def get_current_shift():
    """Get current open shift with shift settings for time checking"""
    db = get_db()
    cursor = db.cursor()
    try:
        # Get any open shift (regardless of date) - shifts should only close manually
        cursor.execute("""
            SELECT * FROM shifts 
            WHERE status = 'open' AND closed_at IS NULL
            ORDER BY opened_at DESC LIMIT 1
        """)
        shift = cursor.fetchone()
        
        if not shift:
            db.close()
            return None
        
        # Get shift settings to check if shift is overdue
        cursor.execute("SELECT * FROM shift_settings ORDER BY id DESC LIMIT 1")
        settings = cursor.fetchone()
        
        # Recalculate totals from actual data for open shifts
        cursor.execute("""
            SELECT COUNT(*) as total_invoices, COALESCE(SUM(net_amount), SUM(total_amount), 0) as total_revenue
            FROM invoices WHERE shift_id = ?
        """, (shift["id"],))
        invoices_stats = cursor.fetchone()
        
        cursor.execute("""
            SELECT COUNT(*) as total_orders
            FROM orders WHERE shift_id = ?
        """, (shift["id"],))
        orders_count = cursor.fetchone()[0]
        
        # Check if shift is overdue
        is_overdue = False
        if settings:
            # Find shift end time from settings
            shift_end_time = None
            if shift["shift_name"] == settings["shift1_name"]:
                shift_end_time = settings["shift1_end_time"]
            elif shift["shift_name"] == settings["shift2_name"]:
                shift_end_time = settings["shift2_end_time"]
            elif settings["number_of_shifts"] >= 3 and "shift3_name" in settings.keys() and shift["shift_name"] == settings["shift3_name"]:
                shift_end_time = settings["shift3_end_time"] if "shift3_end_time" in settings.keys() else None
            
            if shift_end_time:
                # Parse end time and current time
                from datetime import datetime, timedelta
                now = datetime.now()
                end_hour, end_minute = map(int, shift_end_time.split(':'))
                
                # Calculate end time for today
                end_time_today = now.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
                
                # If end time is 00:00, it means end of day (23:59:59)
                if end_hour == 0 and end_minute == 0:
                    end_time = now.replace(hour=23, minute=59, second=59, microsecond=0)
                # If end time is early morning (before 6 AM), it's likely next day
                elif end_hour < 6:
                    end_time = end_time_today + timedelta(days=1)
                # If end time is after current time today, it's today
                elif end_time_today > now:
                    end_time = end_time_today
                # Otherwise, check if it's past end time today
                else:
                    # If current time is after end time today, shift is overdue
                    if now > end_time_today:
                        is_overdue = True
                        end_time = end_time_today
                    else:
                        end_time = end_time_today
                
                # Final check: if current time is past calculated end time, shift is overdue
                if now > end_time:
                    is_overdue = True
        
        db.close()
        
        # Get cash fields safely (handle missing columns)
        cash_drawer_amount = 0.0
        cash_expected = 0.0
        cash_difference = 0.0
        
        if "cash_drawer_amount" in shift.keys():
            cash_drawer_amount = float(shift["cash_drawer_amount"]) if shift["cash_drawer_amount"] is not None else 0.0
        if "cash_expected" in shift.keys():
            cash_expected = float(shift["cash_expected"]) if shift["cash_expected"] is not None else 0.0
        if "cash_difference" in shift.keys():
            cash_difference = float(shift["cash_difference"]) if shift["cash_difference"] is not None else 0.0
        
        return {
            "id": shift["id"],
            "shift_name": shift["shift_name"],
            "shift_number": shift["shift_number"],
            "shift_date": shift["shift_date"],
            "opened_at": shift["opened_at"],
            "closed_at": shift["closed_at"],
            "opened_by": shift["opened_by"],
            "closed_by": shift["closed_by"],
            "status": shift["status"],
            "total_revenue": float(invoices_stats["total_revenue"]) if invoices_stats["total_revenue"] else 0.0,
            "total_orders": orders_count,
            "total_invoices": invoices_stats["total_invoices"] if invoices_stats["total_invoices"] else 0,
            "cash_drawer_amount": cash_drawer_amount,
            "cash_expected": cash_expected,
            "cash_difference": cash_difference,
            "notes": shift["notes"] if "notes" in shift.keys() else None,
            "is_overdue": is_overdue
        }
    except Exception as e:
        db.close()
        raise HTTPException(status_code=500, detail=f"Error getting current shift: {str(e)}")

@router.get("/shifts/available", response_model=List[dict])
def get_available_shifts():
    """Get list of available shifts from settings"""
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT * FROM shift_settings ORDER BY id DESC LIMIT 1")
        settings = cursor.fetchone()
        db.close()
        
        if not settings:
            return []
        
        available_shifts = []
        
        # Add shift 1
        if settings["shift1_name"]:
            available_shifts.append({
                "name": settings["shift1_name"],
                "start_time": settings["shift1_start_time"],
                "end_time": settings["shift1_end_time"]
            })
        
        # Add shift 2
        if settings["shift2_name"]:
            available_shifts.append({
                "name": settings["shift2_name"],
                "start_time": settings["shift2_start_time"],
                "end_time": settings["shift2_end_time"]
            })
        
        # Add shift 3 if exists
        if settings["number_of_shifts"] >= 3 and "shift3_name" in settings.keys() and settings["shift3_name"]:
            available_shifts.append({
                "name": settings["shift3_name"],
                "start_time": settings["shift3_start_time"] if "shift3_start_time" in settings.keys() else None,
                "end_time": settings["shift3_end_time"] if "shift3_end_time" in settings.keys() else None
            })
        
        return available_shifts
    except Exception as e:
        db.close()
        raise HTTPException(status_code=500, detail=f"Error getting available shifts: {str(e)}")

@router.post("/shifts/open", response_model=ShiftResponse)
async def open_shift(request: ShiftOpenRequest):
    """Open a new shift"""
    db = get_db()
    cursor = db.cursor()
    try:
        # Get shift settings
        cursor.execute("SELECT * FROM shift_settings ORDER BY id DESC LIMIT 1")
        settings = cursor.fetchone()
        
        if not settings:
            db.close()
            raise HTTPException(status_code=400, detail="Shift settings not configured")
        
        # Determine shift name
        today = date.today().isoformat()
        shift_name = None
        
        # Priority: use shift_name if provided, otherwise use shift_type (backward compatibility)
        if request.shift_name:
            shift_name = request.shift_name
        elif request.shift_type == "morning":
            shift_name = settings["shift1_name"]
        elif request.shift_type == "evening":
            shift_name = settings["shift2_name"]
        else:
            db.close()
            raise HTTPException(status_code=400, detail="Invalid shift type or name")
        
        # Validate shift name exists in settings
        valid_names = [settings["shift1_name"], settings["shift2_name"]]
        if settings["number_of_shifts"] >= 3 and "shift3_name" in settings.keys() and settings["shift3_name"]:
            valid_names.append(settings["shift3_name"])
        
        if shift_name not in valid_names:
            db.close()
            raise HTTPException(status_code=400, detail=f"Shift name '{shift_name}' not found in settings")
        
        # Check if there's already an open shift of this type today
        cursor.execute("""
            SELECT * FROM shifts 
            WHERE shift_date = ? AND shift_name = ? AND status = 'open'
        """, (today, shift_name))
        existing_open = cursor.fetchone()
        
        if existing_open:
            db.close()
            raise HTTPException(status_code=400, detail=f"Shift {shift_name} is already open today")
        
        # Count how many shifts of this type were opened today (including closed ones)
        cursor.execute("""
            SELECT COUNT(*) FROM shifts 
            WHERE shift_date = ? AND shift_name = ?
        """, (today, shift_name))
        count = cursor.fetchone()[0]
        shift_number = count + 1
        
        # Create new shift
        cursor.execute("""
            INSERT INTO shifts (shift_name, shift_number, shift_date, opened_by, status)
            VALUES (?, ?, ?, ?, 'open')
        """, (shift_name, shift_number, today, "كاشير"))
        
        shift_id = cursor.lastrowid
        db.commit()
        
        # Get created shift
        cursor.execute("SELECT * FROM shifts WHERE id = ?", (shift_id,))
        shift = cursor.fetchone()
        db.close()
        
        # Broadcast shift opened
        try:
            await manager.broadcast({"type": "shift_opened", "shift": {
                "id": shift["id"],
                "shift_name": shift["shift_name"],
                "shift_number": shift["shift_number"]
            }})
        except:
            pass
        
        return ShiftResponse(
            id=shift["id"],
            shift_name=shift["shift_name"],
            shift_number=shift["shift_number"],
            shift_date=shift["shift_date"],
            opened_at=shift["opened_at"],
            closed_at=shift["closed_at"],
            opened_by=shift["opened_by"],
            closed_by=shift["closed_by"],
            status=shift["status"],
            total_revenue=0.0,
            total_orders=0,
            total_invoices=0,
            cash_drawer_amount=0.0,
            cash_expected=0.0,
            cash_difference=0.0,
            notes=shift["notes"]
        )
    except HTTPException:
        raise
    except Exception as e:
        db.close()
        raise HTTPException(status_code=500, detail=f"Error opening shift: {str(e)}")

@router.post("/shifts/{shift_id}/close", response_model=ShiftResponse)
async def close_shift(shift_id: int, close_data: dict):
    """Close a shift"""
    db = get_db()
    cursor = db.cursor()
    try:
        # Parse cash_drawer_amount from request
        cash_drawer_amount = 0.0
        if close_data and "cash_drawer_amount" in close_data:
            cash_drawer_amount = float(close_data["cash_drawer_amount"])
        
        # Get shift
        cursor.execute("SELECT * FROM shifts WHERE id = ?", (shift_id,))
        shift = cursor.fetchone()
        
        if not shift:
            db.close()
            raise HTTPException(status_code=404, detail="Shift not found")
        
        if shift["status"] == "closed":
            db.close()
            raise HTTPException(status_code=400, detail="Shift is already closed")
        
        # Calculate totals from invoices (revenue should come from invoices, not orders)
        cursor.execute("""
            SELECT COUNT(*) as total_invoices, COALESCE(SUM(net_amount), SUM(total_amount), 0) as total_revenue
            FROM invoices WHERE shift_id = ?
        """, (shift_id,))
        invoices_stats = cursor.fetchone()
        
        # Calculate expected cash from invoices
        # For cash payments: use net_amount
        # For mixed payments: extract cash amount from payment_method string (format: mixed_cash_XXX_card_YYY)
        cursor.execute("""
            SELECT COALESCE(SUM(
                CASE 
                    WHEN payment_method = 'cash' THEN net_amount
                    WHEN payment_method LIKE 'mixed_cash_%' THEN 
                        CAST(SUBSTR(payment_method, 13, INSTR(SUBSTR(payment_method, 13), '_') - 1) AS REAL)
                    ELSE 0
                END
            ), 0) as cash_expected
            FROM invoices 
            WHERE shift_id = ? AND (payment_method = 'cash' OR payment_method LIKE 'mixed_cash_%')
        """, (shift_id,))
        cash_expected_result = cursor.fetchone()
        cash_expected = float(cash_expected_result["cash_expected"]) if cash_expected_result["cash_expected"] else 0.0
        
        # Count all orders (not just completed)
        cursor.execute("""
            SELECT COUNT(*) as total_orders
            FROM orders WHERE shift_id = ?
        """, (shift_id,))
        orders_count = cursor.fetchone()[0]
        
        # Move pending orders to next shift if exists
        today = date.today().isoformat()
        cursor.execute("""
            SELECT * FROM shifts 
            WHERE shift_date = ? AND status = 'open' AND id != ?
            ORDER BY opened_at ASC LIMIT 1
        """, (today, shift_id))
        next_shift = cursor.fetchone()
        
        if next_shift:
            # Move pending orders to next shift
            cursor.execute("""
                UPDATE orders SET shift_id = ? 
                WHERE shift_id = ? AND status = 'pending'
            """, (next_shift["id"], shift_id))
        
        # Calculate cash difference
        cash_difference = cash_drawer_amount - cash_expected
        
        # Update shift
        cursor.execute("""
            UPDATE shifts SET
                status = 'closed',
                closed_at = datetime('now', 'localtime'),
                closed_by = 'كاشير',
                total_revenue = ?,
                total_orders = ?,
                total_invoices = ?,
                cash_drawer_amount = ?,
                cash_expected = ?,
                cash_difference = ?
            WHERE id = ?
        """, (
            float(invoices_stats["total_revenue"]) if invoices_stats["total_revenue"] else 0.0,
            orders_count,
            invoices_stats["total_invoices"] if invoices_stats["total_invoices"] else 0,
            cash_drawer_amount,
            cash_expected,
            cash_difference,
            shift_id
        ))
        
        db.commit()
        
        # Get updated shift
        cursor.execute("SELECT * FROM shifts WHERE id = ?", (shift_id,))
        updated_shift = cursor.fetchone()
        db.close()
        
        # طباعة تقرير الشيفت تلقائياً عند الإغلاق
        print_preview_data = None
        try:
            from printing import print_shift_report
            print_result = print_shift_report(shift_id)
            if isinstance(print_result, dict) and "print_preview" in print_result:
                print_preview_data = print_result["print_preview"]
            
            print(f"✅ تمت طباعة تقرير الشيفت {updated_shift['shift_name']} تلقائياً")
        except Exception as e:
            print(f"⚠️ خطأ في طباعة تقرير الشيفت: {e}")
            import traceback
            traceback.print_exc()
            # الاستمرار حتى لو فشلت الطباعة - لا تمنع إغلاق الشيفت
        
        # Broadcast shift closed
        try:
            await manager.broadcast({"type": "shift_closed", "shift": {
                "id": updated_shift["id"],
                "shift_name": updated_shift["shift_name"]
            }})
        except:
            pass
        
        # Get cash fields safely (handle missing columns)
        cash_drawer_amount = 0.0
        cash_expected = 0.0
        cash_difference = 0.0
        
        if "cash_drawer_amount" in updated_shift.keys():
            cash_drawer_amount = float(updated_shift["cash_drawer_amount"]) if updated_shift["cash_drawer_amount"] is not None else 0.0
        if "cash_expected" in updated_shift.keys():
            cash_expected = float(updated_shift["cash_expected"]) if updated_shift["cash_expected"] is not None else 0.0
        if "cash_difference" in updated_shift.keys():
            cash_difference = float(updated_shift["cash_difference"]) if updated_shift["cash_difference"] is not None else 0.0
        
        return ShiftResponse(
            id=updated_shift["id"],
            shift_name=updated_shift["shift_name"],
            shift_number=updated_shift["shift_number"],
            shift_date=updated_shift["shift_date"],
            opened_at=updated_shift["opened_at"],
            closed_at=updated_shift["closed_at"],
            opened_by=updated_shift["opened_by"],
            closed_by=updated_shift["closed_by"],
            status=updated_shift["status"],
            total_revenue=float(updated_shift["total_revenue"]),
            total_orders=updated_shift["total_orders"],
            total_invoices=updated_shift["total_invoices"],
            cash_drawer_amount=cash_drawer_amount,
            cash_expected=cash_expected,
            cash_difference=cash_difference,
            notes=updated_shift["notes"] if "notes" in updated_shift.keys() else None,
            print_preview=print_preview_data
        )
    except HTTPException:
        raise
    except Exception as e:
        db.close()
        raise HTTPException(status_code=500, detail=f"Error closing shift: {str(e)}")

@router.get("/shifts", response_model=List[ShiftResponse])
def get_shifts(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = None
):
    """Get shifts with filters"""
    db = get_db()
    cursor = db.cursor()
    try:
        query = "SELECT * FROM shifts WHERE 1=1"
        params = []
        
        # Build query
        conditions = []
        
        if start_date:
            conditions.append("shift_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("shift_date <= ?")
            params.append(end_date)
            
        date_clause = " AND ".join(conditions) if conditions else "1=1"
        
        if status:
            # If status is specific, we only respect that status and the date filters
            query += f" AND ({date_clause}) AND status = ?"
            params.append(status)
        else:
            # If status is NOT specified, we return shifts in range OR any open shift
            # Note: We need to handle the params order carefully. 
            # The params currently has [start_date, end_date] (if they exist).
            # The query logic is: WHERE (date_conditions) OR status = 'open'
            
            # Since we are using "AND" in the base query "SELECT * FROM shifts WHERE 1=1",
            # we need to be careful with precedence.
            # "WHERE 1=1 AND ( (date_conditions) OR status = 'open' )"
            query += f" AND ( ({date_clause}) OR status = 'open' )"
        
        # Sort: Open shifts first (custom order), then date DESC, then time DESC
        # We can use CASE statement for custom sort
        query += " ORDER BY CASE WHEN status = 'open' THEN 1 ELSE 2 END ASC, shift_date DESC, opened_at DESC"
        cursor.execute(query, params)
        shifts = cursor.fetchall()
        
        result = []
        for shift in shifts:
            shift_id = shift["id"]
            
            # Recalculate totals from actual data (in case shift is still open or data changed)
            cursor.execute("""
                SELECT COUNT(*) as total_invoices, COALESCE(SUM(net_amount), SUM(total_amount), 0) as total_revenue
                FROM invoices WHERE shift_id = ?
            """, (shift_id,))
            invoices_stats = cursor.fetchone()
            
            cursor.execute("""
                SELECT COUNT(*) as total_orders
                FROM orders WHERE shift_id = ?
            """, (shift_id,))
            orders_count = cursor.fetchone()[0]
            
            # Get cash fields safely (handle missing columns)
            cash_drawer_amount = 0.0
            cash_expected = 0.0
            cash_difference = 0.0
            
            if "cash_drawer_amount" in shift.keys():
                cash_drawer_amount = float(shift["cash_drawer_amount"]) if shift["cash_drawer_amount"] is not None else 0.0
            if "cash_expected" in shift.keys():
                cash_expected = float(shift["cash_expected"]) if shift["cash_expected"] is not None else 0.0
            if "cash_difference" in shift.keys():
                cash_difference = float(shift["cash_difference"]) if shift["cash_difference"] is not None else 0.0
            
            # Calculate total_revenue from invoices
            total_revenue = float(invoices_stats["total_revenue"]) if invoices_stats["total_revenue"] else 0.0
            total_invoices = invoices_stats["total_invoices"] if invoices_stats["total_invoices"] else 0
            
            result.append(ShiftResponse(
                id=shift["id"],
                shift_name=shift["shift_name"],
                shift_number=shift["shift_number"],
                shift_date=shift["shift_date"],
                opened_at=shift["opened_at"],
                closed_at=shift["closed_at"],
                opened_by=shift["opened_by"],
                closed_by=shift["closed_by"],
                status=shift["status"],
                total_revenue=total_revenue,
                total_orders=orders_count,
                total_invoices=total_invoices,
                cash_drawer_amount=cash_drawer_amount,
                cash_expected=cash_expected,
                cash_difference=cash_difference,
                notes=shift["notes"] if "notes" in shift.keys() else None
            ))
        
        db.close()
        return result
    except Exception as e:
        db.close()
        raise HTTPException(status_code=500, detail=f"Error getting shifts: {str(e)}")

@router.get("/shifts/{shift_id}/report", response_model=ShiftReportResponse)
def get_shift_report(shift_id: int):
    """Get shift report with orders and invoices"""
    db = get_db()
    cursor = db.cursor()
    try:
        # Get shift
        cursor.execute("SELECT * FROM shifts WHERE id = ?", (shift_id,))
        shift = cursor.fetchone()
        
        if not shift:
            db.close()
            raise HTTPException(status_code=404, detail="Shift not found")
        
        # Recalculate totals from actual data (in case shift is still open or data changed)
        cursor.execute("""
            SELECT COUNT(*) as total_invoices, COALESCE(SUM(net_amount), SUM(total_amount), 0) as total_revenue
            FROM invoices WHERE shift_id = ?
        """, (shift_id,))
        invoices_stats = cursor.fetchone()
        
        cursor.execute("""
            SELECT COUNT(*) as total_orders
            FROM orders WHERE shift_id = ?
        """, (shift_id,))
        orders_count = cursor.fetchone()[0]
        
        # Get orders
        cursor.execute("SELECT * FROM orders WHERE shift_id = ? ORDER BY created_at DESC", (shift_id,))
        orders_data = cursor.fetchall()
        
        orders = []
        for order in orders_data:
            cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order["id"],))
            items_data = cursor.fetchall()
            
            items = []
            for item in items_data:
                items.append(OrderItemResponse(
                    id=item["id"],
                    product_id=item["product_id"],
                    product_name=item["product_name"],
                    quantity=item["quantity"],
                    price=item["price"],
                    total=item["total"],
                    size=item["size"] if "size" in item.keys() and item["size"] else None,
                    additions=item["additions"] if "additions" in item.keys() and item["additions"] else None,
                    notes=item["notes"] if "notes" in item.keys() and item["notes"] else None
                ))
            
            orders.append(OrderResponse(
                id=order["id"],
                order_number=order["order_number"],
                table_number=order["table_number"],
                customer_name=order["customer_name"] if "customer_name" in order.keys() and order["customer_name"] else None,
                customer_phone=order["customer_phone"] if "customer_phone" in order.keys() and order["customer_phone"] else None,
                notes=order["notes"] if "notes" in order.keys() and order["notes"] else None,
                status=order["status"],
                total_amount=float(order["total_amount"]),
                invoice_number=order["invoice_number"] if "invoice_number" in order.keys() and order["invoice_number"] else None,
                branch=order["branch"] if "branch" in order.keys() else "الفرع الرئيسي",
                cashier=order["cashier"] if "cashier" in order.keys() else "كاشير",
                discount_amount=float(order["discount_amount"]) if "discount_amount" in order.keys() and order["discount_amount"] else 0.0,
                tax_amount=float(order["tax_amount"]) if "tax_amount" in order.keys() and order["tax_amount"] else 0.0,
                vat_amount=float(order["vat_amount"]) if "vat_amount" in order.keys() and order["vat_amount"] else 0.0,
                created_at=order["created_at"],
                completed_at=order["completed_at"] if "completed_at" in order.keys() and order["completed_at"] else None,
                items=items
            ))
        
        # Get invoices
        cursor.execute("SELECT * FROM invoices WHERE shift_id = ? ORDER BY created_at DESC", (shift_id,))
        invoices_data = cursor.fetchall()
        
        invoices = []
        for invoice in invoices_data:
            cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (invoice["order_id"],))
            items_data = cursor.fetchall()
            
            items = []
            for item in items_data:
                items.append(OrderItemResponse(
                    id=item["id"],
                    product_id=item["product_id"],
                    product_name=item["product_name"],
                    quantity=item["quantity"],
                    price=item["price"],
                    total=item["total"],
                    size=item["size"] if "size" in item.keys() and item["size"] else None,
                    additions=item["additions"] if "additions" in item.keys() and item["additions"] else None,
                    notes=item["notes"] if "notes" in item.keys() and item["notes"] else None
                ))
            
            invoices.append(InvoiceResponse(
                id=invoice["id"],
                invoice_number=invoice["invoice_number"],
                order_id=invoice["order_id"],
                order_number=invoice["order_number"],
                table_number=invoice["table_number"],
                customer_name=invoice["customer_name"] if "customer_name" in invoice.keys() and invoice["customer_name"] else None,
                customer_phone=invoice["customer_phone"] if "customer_phone" in invoice.keys() and invoice["customer_phone"] else None,
                invoice_location=invoice["invoice_location"] if "invoice_location" in invoice.keys() else "سفری",
                quantity=invoice["quantity"] if "quantity" in invoice.keys() else 1,
                discount_amount=float(invoice["discount_amount"]) if "discount_amount" in invoice.keys() and invoice["discount_amount"] else 0.0,
                tax_amount=float(invoice["tax_amount"]) if "tax_amount" in invoice.keys() and invoice["tax_amount"] else 0.0,
                total_before_vat=float(invoice["total_before_vat"]) if "total_before_vat" in invoice.keys() else 0.0,
                vat_amount=float(invoice["vat_amount"]) if "vat_amount" in invoice.keys() and invoice["vat_amount"] else 0.0,
                net_amount=float(invoice["net_amount"]) if "net_amount" in invoice.keys() else 0.0,
                total_amount=float(invoice["total_amount"]),
                status=invoice["status"],
                payment_method=invoice["payment_method"],
                branch=invoice["branch"] if "branch" in invoice.keys() else "الفرع الرئيسي",
                cashier=invoice["cashier"] if "cashier" in invoice.keys() else "كاشير",
                created_at=invoice["created_at"],
                items=items
            ))
        
        db.close()
        
        # Use recalculated totals (more accurate than stored values)
        calculated_revenue = float(invoices_stats["total_revenue"]) if invoices_stats["total_revenue"] else 0.0
        calculated_orders = orders_count
        calculated_invoices = invoices_stats["total_invoices"] if invoices_stats["total_invoices"] else 0
        
        # Calculate total cash and card amounts from invoices
        total_cash = 0.0
        total_card = 0.0
        
        for invoice in invoices_data:
            payment_method = invoice["payment_method"] if "payment_method" in invoice.keys() else None
            net_amount = float(invoice["net_amount"]) if "net_amount" in invoice.keys() and invoice["net_amount"] else float(invoice["total_amount"])
            
            if payment_method == 'cash':
                total_cash += net_amount
            elif payment_method == 'card':
                total_card += net_amount
            elif payment_method and payment_method.startswith('mixed_cash_'):
                # Parse mixed payment: mixed_cash_XXX_card_YYY
                import re
                match = re.match(r'mixed_cash_(\d+(?:\.\d+)?)_card_(\d+(?:\.\d+)?)', payment_method)
                if match:
                    total_cash += float(match.group(1))
                    total_card += float(match.group(2))
        
        # Get cash fields safely (handle missing columns)
        cash_drawer_amount = 0.0
        cash_expected = 0.0
        cash_difference = 0.0
        
        if "cash_drawer_amount" in shift.keys():
            cash_drawer_amount = float(shift["cash_drawer_amount"]) if shift["cash_drawer_amount"] is not None else 0.0
        if "cash_expected" in shift.keys():
            cash_expected = float(shift["cash_expected"]) if shift["cash_expected"] is not None else 0.0
        if "cash_difference" in shift.keys():
            cash_difference = float(shift["cash_difference"]) if shift["cash_difference"] is not None else 0.0
        
        return ShiftReportResponse(
            shift=ShiftResponse(
                id=shift["id"],
                shift_name=shift["shift_name"],
                shift_number=shift["shift_number"],
                shift_date=shift["shift_date"],
                opened_at=shift["opened_at"],
                closed_at=shift["closed_at"],
                opened_by=shift["opened_by"],
                closed_by=shift["closed_by"],
                status=shift["status"],
                total_revenue=calculated_revenue,
                total_orders=calculated_orders,
                total_invoices=calculated_invoices,
                cash_drawer_amount=cash_drawer_amount,
                cash_expected=cash_expected,
                cash_difference=cash_difference,
                notes=shift["notes"] if "notes" in shift.keys() else None
            ),
            orders=orders,
            invoices=invoices,
            total_cash=total_cash,
            total_card=total_card
        )
    except HTTPException:
        raise
    except Exception as e:
        db.close()
        raise HTTPException(status_code=500, detail=f"Error getting shift report: {str(e)}")


