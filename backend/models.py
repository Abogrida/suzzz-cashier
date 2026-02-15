from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class CategoryCreate(BaseModel):
    name: str

class CategoryResponse(BaseModel):
    id: int
    name: str
    created_at: Optional[str] = None

class ProductCreate(BaseModel):
    name: str
    price: float
    category_id: int
    image_path: Optional[str] = None
    enabled: bool = True
    price_s: Optional[float] = None
    price_m: Optional[float] = None
    price_l: Optional[float] = None
    has_sizes: bool = False
    hidden_on_tablet: bool = False

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    category_id: Optional[int] = None
    image_path: Optional[str] = None
    enabled: Optional[bool] = None
    price_s: Optional[float] = None
    price_m: Optional[float] = None
    price_l: Optional[float] = None
    has_sizes: Optional[bool] = None
    hidden_on_tablet: Optional[bool] = None

class ProductResponse(BaseModel):
    id: int
    name: str
    price: float
    category_id: int
    category_name: Optional[str] = None
    image_path: Optional[str] = None
    enabled: bool
    price_s: Optional[float] = None
    price_m: Optional[float] = None
    price_l: Optional[float] = None
    has_sizes: bool = False
    hidden_on_tablet: bool = False

class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int
    size: Optional[str] = None  # S, M, L, or None
    additions: Optional[str] = None  # Comma-separated additions
    notes: Optional[str] = None  # Notes for this item

class OrderCreate(BaseModel):
    table_number: int = 0
    customer_name: Optional[str] = None
    notes: Optional[str] = None
    items: List[OrderItemCreate]
    idempotency_key: Optional[str] = None

class OrderItemResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: int
    price: float
    total: float
    size: Optional[str] = None
    additions: Optional[str] = None  # Comma-separated additions
    notes: Optional[str] = None  # Notes for this item

class OrderResponse(BaseModel):
    id: int
    order_number: int
    table_number: int
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    notes: Optional[str] = None
    status: str
    total_amount: float
    invoice_number: Optional[str] = None
    branch: Optional[str] = 'الفرع الرئيسي'
    cashier: Optional[str] = 'كاشير'
    discount_amount: Optional[float] = 0
    tax_amount: Optional[float] = 0
    vat_amount: Optional[float] = 0
    created_at: str
    completed_at: Optional[str] = None
    items: List[OrderItemResponse] = []
    print_preview: Optional[str] = None  # Base64 image for browser printing

class SettingsUpdate(BaseModel):
    admin_password: Optional[str] = None
    cashier_password: Optional[str] = None
    owner_password: Optional[str] = None
    printer_ip: Optional[str] = None
    cashier_discount_permission: Optional[bool] = None
    restaurant_name: Optional[str] = None
    restaurant_address: Optional[str] = None
    footer_text: Optional[str] = None
    logo_path: Optional[str] = None
    playstation_price_per_hour: Optional[float] = None
    playstation_price_per_hour: Optional[float] = None
    playstation_price_multi: Optional[float] = None
    playstation_enabled: Optional[str] = None

class LoginRequest(BaseModel):
    password: str

class InvoiceResponse(BaseModel):
    id: int
    invoice_number: str
    order_id: int
    order_number: str
    table_number: int
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    invoice_location: Optional[str] = 'سفری'
    quantity: Optional[int] = 1
    discount_amount: Optional[float] = 0
    tax_amount: Optional[float] = 0
    total_before_vat: Optional[float] = 0
    vat_amount: Optional[float] = 0
    net_amount: Optional[float] = 0
    total_amount: float
    status: str
    payment_method: str
    branch: Optional[str] = 'الفرع الرئيسي'
    cashier: Optional[str] = 'كاشير'
    created_at: str
    items: List[OrderItemResponse] = []

class InvoiceReport(BaseModel):
    total_invoices: int
    total_revenue: float
    invoices: List[InvoiceResponse]

class TableCreate(BaseModel):
    table_number: int
    customer_name: Optional[str] = None
    phone: Optional[str] = None

class TableUpdate(BaseModel):
    customer_name: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    order_id: Optional[int] = None

class TableResponse(BaseModel):
    id: int
    table_number: int
    customer_name: Optional[str] = None
    phone: Optional[str] = None
    status: str
    order_id: Optional[int] = None
    created_at: str
    updated_at: str
    playstation_start_time: Optional[str] = None
    playstation_type: Optional[str] = None
    order: Optional[OrderResponse] = None

class ShiftSettingsUpdate(BaseModel):
    number_of_shifts: int = 2
    shift1_name: Optional[str] = None
    shift1_start_time: Optional[str] = None
    shift1_end_time: Optional[str] = None
    shift2_name: Optional[str] = None
    shift2_start_time: Optional[str] = None
    shift2_end_time: Optional[str] = None
    shift3_name: Optional[str] = None
    shift3_start_time: Optional[str] = None
    shift3_end_time: Optional[str] = None

class ShiftSettingsResponse(BaseModel):
    id: int
    number_of_shifts: int
    shift1_name: str
    shift1_start_time: str
    shift1_end_time: str
    shift2_name: str
    shift2_start_time: str
    shift2_end_time: str
    shift3_name: Optional[str] = None
    shift3_start_time: Optional[str] = None
    shift3_end_time: Optional[str] = None

class ShiftOpenRequest(BaseModel):
    shift_type: Optional[str] = None  # 'morning' or 'evening' (deprecated)
    shift_name: Optional[str] = None  # Direct shift name from settings

class ShiftCloseRequest(BaseModel):
    cash_drawer_amount: float

class ShiftResponse(BaseModel):
    id: int
    shift_name: str
    shift_number: int
    shift_date: str
    opened_at: str
    closed_at: Optional[str] = None
    opened_by: Optional[str] = None
    closed_by: Optional[str] = None
    status: str
    total_revenue: float
    total_orders: int
    total_invoices: int
    cash_drawer_amount: Optional[float] = 0.0
    cash_expected: Optional[float] = 0.0
    cash_difference: Optional[float] = 0.0
    notes: Optional[str] = None
    print_preview: Optional[str] = None

class ShiftReportResponse(BaseModel):
    shift: ShiftResponse
    orders: List[OrderResponse]
    invoices: List[InvoiceResponse]
    total_cash: Optional[float] = 0.0
    total_card: Optional[float] = 0.0

