from fastapi import APIRouter, HTTPException
from printing import print_kitchen_receipt, print_customer_invoice, print_shift_report
from typing import Optional, List, Dict
from pydantic import BaseModel

router = APIRouter()

class PrintKitchenRequest(BaseModel):
    new_items: Optional[List[Dict]] = None

@router.post("/print/kitchen/{order_id}")
def print_kitchen(order_id: int, request: Optional[PrintKitchenRequest] = None):
    """طباعة ريسيت المطبخ (بدون أسعار)"""
    try:
        new_items = request.new_items if request and request.new_items else None
        success = print_kitchen_receipt(order_id, new_items_only=new_items)
        
        # Check if browser print mode returned preview
        if isinstance(success, dict) and "print_preview" in success:
             return {"message": "تمت طباعة ريسيت المطبخ (معاينة)", "success": True, "print_preview": success["print_preview"]}
             
        if not success:
            print(f"⚠️ فشلت طباعة ريسيت المطبخ للطلب {order_id}")
        return {"message": "تمت طباعة ريسيت المطبخ", "success": success}
    except Exception as e:
        print(f"❌ خطأ في endpoint الطباعة: {e}")
        import traceback
        traceback.print_exc()
        # Return success message even if printing fails - don't block the operation
        return {"message": "تمت محاولة الطباعة", "success": False, "error": str(e)}

@router.post("/print/check/{order_id}")
def print_check_endpoint(order_id: int):
    """طباعة شيك طلب (مبدئي) بدون حفظ فاتورة"""
    from printing import print_order_check
    try:
        success = print_order_check(order_id)
        
        # Check if browser print mode returned preview
        if isinstance(success, dict) and "print_preview" in success:
             return {"message": "تمت طباعة الشيك (معاينة)", "success": True, "print_preview": success["print_preview"]}
        
        if not success:
            print(f"⚠️ فشلت طباعة الشيك للطلب {order_id}")
        return {"message": "تمت طباعة الشيك", "success": success}
    except Exception as e:
        print(f"❌ خطأ في endpoint طباعة الشيك: {e}")
        return {"message": "خطأ في الطباعة", "success": False, "error": str(e)}

@router.post("/print/invoice/{order_id}")
def print_invoice_endpoint(order_id: int):
    """طباعة فاتورة العميل (بأسعار)"""
    try:
        from printing import print_customer_invoice
        result = print_customer_invoice(order_id)
        
        # Check if browser print mode returned preview
        if isinstance(result, dict) and "print_preview" in result:
             return {"message": "تمت طباعة الفاتورة (معاينة)", "success": True, "print_preview": result["print_preview"]}
        
        success = result
        if not success:
            print(f"⚠️ فشلت طباعة الفاتورة للطلب {order_id}")
            # Don't raise error - just log it
        return {"message": "تمت طباعة الفاتورة", "success": success}
    except Exception as e:
        print(f"❌ خطأ في endpoint الطباعة: {e}")
        import traceback
        traceback.print_exc()
        # Return success message even if printing fails - don't block the operation
        return {"message": "تمت محاولة الطباعة", "success": False, "error": str(e)}

@router.post("/print/shift/{shift_id}")
def print_shift_endpoint(shift_id: int):
    """طباعة تقرير الشيفت"""
    success = print_shift_report(shift_id)
    
    # Check if browser print mode returned preview
    if isinstance(success, dict) and "print_preview" in success:
         return {"message": "تمت طباعة تقرير الشيفت (معاينة)", "success": True, "print_preview": success["print_preview"]}
    
    if not success:
        print(f"⚠️ فشلت طباعة تقرير الشيفت {shift_id}")
    return {"message": "تمت طباعة تقرير الشيفت"}




