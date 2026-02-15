import os
import sys
from PIL import Image, ImageDraw, ImageFont, ImageOps
import arabic_reshaper
from bidi.algorithm import get_display

class ExactRenderer:
    def __init__(self, width_mm=80, dpi=203):
        self.width_px = 576 # Standard for 80mm
        self.font_path = self._get_resource_path("arial.ttf")
        self.bold_font_path = self._get_resource_path("arialbd.ttf")
        
        # Fonts
        try:
            self.font_s = ImageFont.truetype(self.font_path, 20)
            self.font_m = ImageFont.truetype(self.font_path, 24)
            self.font_l = ImageFont.truetype(self.bold_font_path, 30)
            self.font_xl = ImageFont.truetype(self.bold_font_path, 40)
            self.font_xxl = ImageFont.truetype(self.bold_font_path, 50)
        except:
            self.font_s = ImageFont.load_default()
            self.font_m = ImageFont.load_default()
            self.font_l = ImageFont.load_default()
            self.font_xl = ImageFont.load_default()
            self.font_xl = ImageFont.load_default()
            self.font_xxl = ImageFont.load_default()
            
        self.settings = self.load_settings()

    def load_settings(self):
        try:
            from db import get_db
            db = get_db()
            cursor = db.cursor()
            cursor.execute("SELECT key, value FROM settings")
            settings = {row["key"]: row["value"] for row in cursor.fetchall()}
            db.close()
            return settings
        except Exception as e:
            print(f"Error loading settings: {e}")
            return {}

    def get_setting(self, key, default):
        return self.settings.get(key, default)
    def _get_resource_path(self, relative_path):
        """Get absolute path to resource, works for dev and for PyInstaller"""
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
            
        return os.path.join(base_path, relative_path)

    def _reshape(self, text):
        if not text: return ""
        return get_display(arabic_reshaper.reshape(str(text)))

    def _draw_centered(self, draw, text, font, y, width=None):
        if width is None: width = self.width_px
        text = self._reshape(text)
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        x = (width - w) / 2
        draw.text((x, y), text, font=font, fill=0)
        return bbox[3] - bbox[1] + 5

    def _draw_right(self, draw, text, font, y, right_margin=10):
        text = self._reshape(text)
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        x = self.width_px - right_margin - w
        draw.text((x, y), text, font=font, fill=0)
        return bbox[3] - bbox[1] + 5
        
    def _draw_left(self, draw, text, font, y, left_margin=10):
        text = self._reshape(text)
        draw.text((left_margin, y), text, font=font, fill=0)
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[3] - bbox[1] + 5

    def render_kitchen_receipt(self, order, items):
        # Image 1 Style: Grid/Box Layout
        # Create canvas
        img = Image.new('1', (self.width_px, 2000), 255)
        draw = ImageDraw.Draw(img)
        y = 20
        
        # 1. Header (Order Type)
        # "سفري" or Table
        order_type = "سفري" if order['table_number'] == 0 else f"طاولة {order['table_number']}"
        y += self._draw_centered(draw, order_type, self.font_xl, y)
        y += 20
        
        # 2. Order Info Row
        # 10 (Left)           5609 (Right)
        #                     Cashier (Right)
        
        # Right Side
        y_start = y
        self._draw_right(draw, str(order['order_number']), self.font_xl, y)
        y += 40
        self._draw_right(draw, "كاشير", self.font_m, y)
        y += 30
        self._draw_right(draw, order['created_at'].split()[0], self.font_l, y) # Date
        y += 35
        self._draw_right(draw, datetime.now().strftime("%I:%M %p"), self.font_l, y) # Time
        
        # Left Side (Table/Order Num again?)
        # Image shows "10" on left. Let's put Table Num there.
        # REMOVED per user request
        # self._draw_left(draw, str(order['table_number']), self.font_xxl, y_start + 20)
        
        y += 50 # Increased padding to separate time from grid
        
        # 3. Items Grid
        # Header Box
        # |  Quantity  |       Item       |
        
        # Draw Box
        box_top = y
        draw.rectangle((10, y, self.width_px - 10, y + 40), outline=0, width=2)
        
        # Vertical Line (approx 25% for Qty)
        split_x = 150
        draw.line((split_x, y, split_x, y + 40), fill=0, width=2)
        
        # Headers
        # Centered in their boxes
        qty_header = self._reshape("كمية")
        item_header = self._reshape("الصنف")
        
        # Helper for box centering
        def draw_in_box(text, font, box_x1, box_y1, box_x2, box_y2):
            text = self._reshape(text)
            bbox = draw.textbbox((0, 0), text, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            x = box_x1 + (box_x2 - box_x1 - w) / 2
            y = box_y1 + (box_y2 - box_y1 - h) / 2
            draw.text((x, y), text, font=font, fill=0)
            
        draw_in_box("كمية", self.font_l, 10, y, split_x, y+40)
        draw_in_box("الصنف", self.font_l, split_x, y, self.width_px-10, y+40)
        
        y += 40
        
        # Items
        print(f"[DEBUG] Rendering Kitchen Receipt Grid Items: {items}")
        for item in items:
            try:
                # Handle both dict and sqlite3.Row
                qty_val = item['quantity']
                name_val = item['product_name']
                print(f"[DEBUG] Kitchen Grid Item: {name_val}, Qty: {qty_val}, Type: {type(item)}")
            except Exception as e:
                print(f"[DEBUG] Error accessing kitchen item: {e}")

            # Row Height depends on text wrapping, but for now fixed or dynamic
            row_h = 60
            
            # Draw Box
            draw.rectangle((10, y, self.width_px - 10, y + row_h), outline=0, width=2)
            draw.line((split_x, y, split_x, y + row_h), fill=0, width=2)
            
            # Qty
            safe_qty = item['quantity']
            if safe_qty is None or safe_qty == 0 or str(safe_qty) == "0":
                safe_qty = 1 # Fallback to 1 if 0 is received
            
            draw_in_box(str(safe_qty), self.font_xl, 10, y, split_x, y+row_h)
            
            # Name
            name = item['product_name']
            if item['size']: name += f" - {item['size']}"
            draw_in_box(name, self.font_l, split_x, y, self.width_px-10, y+row_h)
            
            y += row_h
            
            # Additions/Notes
            additions = item['additions'] if 'additions' in item.keys() else None
            notes = item['notes'] if 'notes' in item.keys() else None
            
            if additions or notes:
                note = ""
                if additions: note += f"+ {additions} "
                if notes: note += f"({notes})"
                
                # Small box below
                draw.rectangle((10, y, self.width_px - 10, y + 30), outline=0, width=2)
                draw_in_box(note, self.font_m, 10, y, self.width_px-10, y+30)
                y += 30
                
        y += 20
        y += 20
        footer_text = self.get_setting("footer_text", "Powered by Abogrida.com")
        y += self._draw_centered(draw, footer_text, self.font_s, y)
        y += 20
        
        # Crop
        return img.crop((0, 0, self.width_px, y))

    def render_customer_invoice(self, order, invoice, items):
        # Image 2 Style: Customer Invoice
        # Note: If invoice is None, this is a "Check" (Provisional Receipt)
        
        is_provisional = invoice is None
        
        # Calculate totals if provisional
        if is_provisional:
            total_amount = float(order['total_amount'])
            discount_amount = float(order['discount_amount'] or 0)
            tax_amount = float(order['tax_amount'] or 0)
            vat_amount = float(order['vat_amount'] or 0)
            # Net amount is usually calculated as: Total - Discount + Tax + VAT
            # But order['total_amount'] in some systems is already net or gross.
            # Let's assume order['total_amount'] is the final amount to pay if no breakdown provided.
            # Actually, looking at `orders` table usually:
            # total_amount matches the sum of items prices.
            # So Net = Total - Discount + Tax + VAT
            net_amount = total_amount - discount_amount + tax_amount + vat_amount
            
            invoice_data = {
                'invoice_number': '---', # No invoice number yet
                'cashier': order['cashier'] or 'Server',
                'invoice_location': 'شيك مبدئي', # Label as Provisional
                'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'total_amount': total_amount,
                'discount_amount': discount_amount,
                'net_amount': net_amount,
                'payment_method': '---'
            }
        else:
            invoice_data = dict(invoice)
            
        img = Image.new('1', (self.width_px, 2000), 255)
        draw = ImageDraw.Draw(img)
        y = 0
        
        # 0. Logo
        logo_setting = self.get_setting("logo_path", "")
        default_logo_path = self._get_resource_path("image.png")
        
        final_logo_path = None
        if logo_setting and os.path.exists(logo_setting):
            final_logo_path = logo_setting
        elif os.path.exists(default_logo_path):
            final_logo_path = default_logo_path
            
        if final_logo_path:
            try:
                logo = Image.open(final_logo_path).convert("1")
                
                # Auto-crop whitespace
                try:
                    # Invert to find non-white pixels
                    bbox = ImageOps.invert(logo.convert('L')).getbbox()
                    if bbox:
                        logo = logo.crop(bbox)
                except Exception:
                    pass

                # Resize to fit width (keep aspect) - Make it smaller (e.g. 300px)
                target_width = 450
                w_percent = (target_width / float(logo.size[0]))
                h_size = int((float(logo.size[1]) * float(w_percent)))
                logo = logo.resize((target_width, h_size), Image.Resampling.LANCZOS)
                
                # Center
                x_pos = (self.width_px - target_width) // 2
                img.paste(logo, (x_pos, y))
                y += h_size
            except:
                name = self.get_setting("restaurant_name", "دوار العمده")
                y += self._draw_centered(draw, name, self.font_xxl, y)
        else:
            name = self.get_setting("restaurant_name", "دوار العمده")
            y += self._draw_centered(draw, name, self.font_xxl, y)
            
        y += 0
        
        # 1. Header Labels
        if is_provisional:
            y += self._draw_centered(draw, "شيك طلب", self.font_xl, y)
            y += 10
        
        # 2. Order Number (Centered)
        y += self._draw_centered(draw, str(order['order_number']), self.font_xl, y)
        y += 10
        name = self.get_setting("restaurant_name", "دوار العمده")
        y += self._draw_centered(draw, name, self.font_l, y)
        y += 10
        
        address = self.get_setting("restaurant_address", "قبل بنزينه توتال ابو الاخضر - طريقه الزقازيق القاهره الصحراوي")
        # Split address if too long? For now just draw it
        y += self._draw_centered(draw, address, self.font_m, y)
        y += 10
        
        # Separator (Dotted)
        draw.line((10, y, self.width_px - 10, y), fill=0, width=2) # Dotted hard to draw with simple line, solid is fine
        y += 10
        
        # 3. Info Block
        # Right aligned labels, Left aligned values? No, Image shows:
        # رقم الفاتورة: 5609 (Right)
        # كاشير كاشير (Right)
        # - سفري (Right)
        # Date/Time (Left)
        
        y_start = y
        # Right Side
        invoice_num_display = invoice_data['invoice_number']
        self._draw_right(draw, f"رقم الفاتورة: {invoice_num_display}", self.font_m, y)
        y += 30
        self._draw_right(draw, f"كاشير: {invoice_data['cashier']}", self.font_m, y)
        y += 30
        location_display = invoice_data.get('invoice_location', 'سفري')
        if location_display == 'سفري' and order['table_number'] > 0:
             location_display = f"طاولة {order['table_number']}"
             
        self._draw_right(draw, f"- {location_display}", self.font_l, y)
        
        # Left Side (Date)
        y = y_start
        created_at_str = str(invoice_data['created_at'])
        self._draw_left(draw, created_at_str.split()[0], self.font_m, y)
        y += 30
        # Parse original time from created_at string "YYYY-MM-DD HH:MM:SS"
        try:
             dt = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
             time_str = dt.strftime("%I:%M %p")
        except:
             time_str = created_at_str.split()[1] if len(created_at_str.split()) > 1 else ""
        self._draw_left(draw, time_str, self.font_m, y)
        
        y += 60
        
        # 4. Items Header
        # Line
        draw.line((10, y, self.width_px - 10, y), fill=0, width=2)
        y += 5
        # نهائي (Left) ... (Right)
        # Image headers: 30.00 (Price) 1 (Qty) ... Name
        
        y += 30
        draw.line((10, y, self.width_px - 10, y), fill=0, width=2)
        y += 10
        
        # Items
        print(f"[DEBUG] Rendering Customer Invoice Items: {items}")
        for item in items:
            try:
                # Handle both dict and sqlite3.Row
                # Use accessing by key instead of .keys() for sqlite3.Row compatibility in some versions/implementations if keys() is not available directly on row object in loop context
                # But sqlite3.Row supports keys() in Python 3.
                qty_val = item['quantity']
                name_val = item['product_name']
                print(f"[DEBUG] Invoice Item: {name_val}, Qty Raw: {qty_val}, Type: {type(item)}")
            except Exception as e:
                print(f"[DEBUG] Error accessing item fields: {e}")

            # Name (Right)
            name = item['product_name']
            if item['size']: name += f" - {item['size']}"
            
            # Price (Left)
            price = f"{item['price']:.2f}"
            
            # Qty (Left of Price)
            qty = str(item['quantity'])
            
            # Draw Name
            self._draw_right(draw, name, self.font_l, y)
            
            # Draw Price (at x=100)
            draw.text((20, y), price, font=self.font_l, fill=0)
            
            # Draw Qty (at x=180)
            draw.text((150, y), qty, font=self.font_l, fill=0)
            
            y += 40
            
            if item['additions']:
                self._draw_right(draw, f"+ {item['additions']}", self.font_m, y)
                y += 30
                
        y += 10
        draw.line((10, y, self.width_px - 10, y), fill=0, width=1)
        y += 10
        
        # 5. Totals
        # المجموع (Right)  30.00 (Left)
        self._draw_right(draw, "المجموع", self.font_m, y)
        draw.text((50, y), f"{invoice_data['total_amount']:.2f}", font=self.font_m, fill=0)
        y += 30
        
        if invoice_data['discount_amount'] > 0:
            self._draw_right(draw, "خصم", self.font_m, y)
            draw.text((50, y), f"{invoice_data['discount_amount']:.2f}", font=self.font_m, fill=0)
            y += 30
            
        y += 10
        
        # Grey Box for Net Total
        # Draw rectangle with grey fill? 1-bit image, so stippled or just outline
        # Image shows grey background. We can simulate with pattern or just black box with white text.
        # Let's do Outline Box with Large Text
        
        box_h = 60
        draw.rectangle((10, y, self.width_px - 10, y + box_h), outline=0, width=2)
        
        # Text inside
        # المبلغ المطلوب (Right)   30.00 (Left/Center)
        
        text_y = y + 10
        label_total = "المبلغ المطلوب" if not is_provisional else "إجمالي الشيك"
        self._draw_right(draw, label_total, self.font_l, text_y, right_margin=20)
        draw.text((50, text_y), f"{invoice_data['net_amount']:.2f}", font=self.font_xl, fill=0)
        
        y += box_h + 20
        
        # Payment Info
        # نوع الدفع (Center)
        # Display actual payment method
        if not is_provisional:
            y += self._draw_centered(draw, "نوع الدفع", self.font_m, y)
            y += 25
            
            # Map payment_method to Arabic display text
            payment_method = invoice_data.get('payment_method', 'cash')
            if payment_method == 'cash':
                payment_text = "نقدي"
            elif payment_method == 'card':
                payment_text = "بطاقة"
            elif payment_method.startswith('mixed'):
                payment_text = "نقدي وبطاقة"
            else:
                payment_text = "نقدي"  # Default fallback
            
            y += self._draw_centered(draw, payment_text, self.font_l, y)
            y += 10
            y += self._draw_centered(draw, f"{invoice_data['net_amount']:.2f}", self.font_l, y)
            y += 30
        
        # Footer
        draw.line((10, y, self.width_px - 10, y), fill=0, width=2)
        y += 10
        y += self._draw_centered(draw, "YOUR COFFEE, ON THE GO", self.font_l, y)
        y += 30
        footer_text = self.get_setting("footer_text", "Powered by Abogrida.com")
        y += self._draw_centered(draw, footer_text, self.font_s, y)
        y += 20
        
        return img.crop((0, 0, self.width_px, y))

    def render_drawer_slip(self):
        img = Image.new('1', (self.width_px, 200), 255)
        draw = ImageDraw.Draw(img)
        y = 50
        y += self._draw_centered(draw, "تم فتح الدرج", self.font_xl, y)
        y += 30
        y += self._draw_centered(draw, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), self.font_s, y)
        return img.crop((0, 0, self.width_px, y + 50))

    def render_shift_report(self, data):
        # Image 3 Style: Shift Report (Complex Layout)
        img = Image.new('1', (self.width_px, 3000), 255)
        draw = ImageDraw.Draw(img)
        y = 0
        
        # 0. Logo (Added per user request)
        # 0. Logo (Added per user request)
        logo_setting = self.get_setting("logo_path", "")
        default_logo_path = self._get_resource_path("image.png")
        
        final_logo_path = None
        if logo_setting and os.path.exists(logo_setting):
            final_logo_path = logo_setting
        elif os.path.exists(default_logo_path):
            final_logo_path = default_logo_path

        if final_logo_path:
            try:
                logo = Image.open(final_logo_path).convert("1")
                
                # Auto-crop whitespace
                try:
                    bbox = ImageOps.invert(logo.convert('L')).getbbox()
                    if bbox:
                        logo = logo.crop(bbox)
                except Exception:
                    pass

                # Resize to fit width (keep aspect) - Make it smaller (e.g. 300px)
                target_width = 450
                w_percent = (target_width / float(logo.size[0]))
                h_size = int((float(logo.size[1]) * float(w_percent)))
                logo = logo.resize((target_width, h_size), Image.Resampling.LANCZOS)
                
                # Center
                x_pos = (self.width_px - target_width) // 2
                img.paste(logo, (x_pos, y))
                y += h_size
            except:
                pass
        
        # 1. Header
        y += self._draw_centered(draw, "ملخص الوردية", self.font_xl, y)
        y += 10
        y += self._draw_centered(draw, f"الوردية: {data['shift_name']}", self.font_m, y)
        y += 20
        
        # Shift Info Block
        # Right: Shift Num, Start Date/Time, Branch
        # Left: End Date/Time, Cashier
        
        # Row 1: Shift Num (Right)
        self._draw_right(draw, f"رقم الوردية: {data['shift_number']}", self.font_m, y)
        y += 30
        
        # Row 2: Dates
        # Right: From
        self._draw_right(draw, f"من: {data['start_date']}", self.font_m, y)
        # Left: To
        self._draw_left(draw, f"إلى: {data['end_date']}", self.font_m, y)
        y += 25
        # Times
        self._draw_right(draw, data['start_time'], self.font_m, y)
        self._draw_left(draw, data['end_time'], self.font_m, y)
        y += 30
        
        # Row 3: Branch / Cashier
        self._draw_right(draw, f"الفرع: {data['branch']}", self.font_m, y)
        self._draw_left(draw, f"الكاشير: {data['cashier']}", self.font_m, y)
        y += 30
        
        draw.line((10, y, self.width_px - 10, y), fill=0, width=2)
        y += 10
        
        # 2. Sales Section (المبيعات)
        y += self._draw_centered(draw, "المبيعات", self.font_l, y)
        y += 20
        
        # Total / Count
        self._draw_right(draw, f"الاجمالي: {data['sales']['total']:.2f}", self.font_l, y)
        self._draw_left(draw, f"العدد: {data['sales']['count']}", self.font_l, y)
        y += 30
        
        # Cash / Card
        self._draw_right(draw, f"نقدي: {data['sales']['cash']:.2f}", self.font_m, y)
        self._draw_left(draw, f"بطاقة: {data['sales']['card']:.2f}", self.font_m, y)
        y += 25
        
        # Credit / Tax
        self._draw_right(draw, f"آجل: 0.00", self.font_m, y) # Placeholder
        self._draw_left(draw, f"ضريبة التبغ: {data['sales']['tax']:.2f}", self.font_m, y)
        y += 25
        
        # Delivery / VAT
        self._draw_right(draw, f"رسوم التوصيل: {data['sales']['delivery']:.2f}", self.font_m, y)
        self._draw_left(draw, f"ق.م: {data['sales']['vat']:.2f}", self.font_m, y)
        y += 25
        
        # Discount
        self._draw_centered(draw, f"الخصم: {data['sales']['discount']:.2f}", self.font_m, y)
        y += 30
        
        # Box for "Application" (تطبيق) - Placeholder from image
        draw.rectangle((10, y, self.width_px - 10, y + 30), outline=0, width=1)
        self._draw_right(draw, "تطبيق", self.font_m, y, right_margin=20)
        self._draw_left(draw, "0.00", self.font_m, y, left_margin=20)
        y += 40
        
        # 3. Expenses/Payouts (صرف)
        y += self._draw_centered(draw, "صرف", self.font_l, y)
        y += 20
        # Count / Debit / Credit
        # Count / Debit / Credit
        self._draw_right(draw, f"العدد: {data['expenses']['count']}", self.font_m, y)
        draw.text((200, y), self._reshape(f"المدين: {data['expenses']['debit']:.2f}"), font=self.font_m, fill=0)
        self._draw_left(draw, f"الدائن: {data['expenses']['credit']:.2f}", self.font_m, y)
        y += 30
        draw.line((10, y, self.width_px - 10, y), fill=0, width=1)
        y += 10
        
        # 4. Income (قبض) - Placeholder
        y += self._draw_centered(draw, "قبض", self.font_l, y)
        y += 20
        self._draw_right(draw, "العدد: 0", self.font_m, y)
        draw.text((200, y), self._reshape("المدين: 0"), font=self.font_m, fill=0)
        self._draw_left(draw, "الدائن: 0.00", self.font_m, y)
        y += 30
        draw.line((10, y, self.width_px - 10, y), fill=0, width=1)
        y += 10
        
        # 5. Reconciliation (العهدة)
        y += self._draw_centered(draw, "العهدة", self.font_l, y)
        y += 20
        
        def draw_row(label, value, font=self.font_m):
            self._draw_right(draw, label, font, y)
            self._draw_left(draw, f"{value:.2f}", font, y)
            return 30
            
        y += draw_row("إجمالي الصرف", data['reconciliation']['total_expenses'])
        y += draw_row("إجمالي القبض", data['reconciliation']['total_income'])
        y += draw_row("مبيعات نقدي", data['reconciliation']['cash_sales'], self.font_l)
        y += draw_row("صافي المبلغ", data['reconciliation']['net_amount'], self.font_l)
        y += draw_row("نقدية الكاشير", data['reconciliation']['cashier_cash'], self.font_l)
        y += draw_row("فرق النقدية", data['reconciliation']['cash_diff'])
        y += draw_row("مبيعات بطاقة", data['reconciliation']['card_sales'])
        y += draw_row("جهاز المدفوعات", data['reconciliation']['device_total'])
        y += draw_row("فرق جهاز المدفوعات", data['reconciliation']['device_diff'])
        y += draw_row("اكرامية نقدي", data['reconciliation']['cash_tips'])
        y += draw_row("اكرامية بطاقة", data['reconciliation']['card_tips'])
        
        y += 10
        draw.line((10, y, self.width_px - 10, y), fill=0, width=1)
        y += 10
        
        # 6. Categories (الفئات)
        y += self._draw_centered(draw, "الفئات", self.font_l, y)
        y += 20
        
        # Table Header
        draw.rectangle((10, y, self.width_px - 10, y + 30), outline=0, width=1)
        # Columns: Category (Right), Qty (Center), Total (Left)
        # Split lines
        draw.line((200, y, 200, y + 30), fill=0, width=1) # Left split
        draw.line((400, y, 400, y + 30), fill=0, width=1) # Right split
        
        # Headers
        # Right box: Category
        self._draw_right(draw, "الفئة", self.font_m, y, right_margin=20)
        # Center box: Qty
        draw.text((280, y), self._reshape("الكمية"), font=self.font_m, fill=0)
        # Left box: Total
        self._draw_left(draw, "الاجمالي", self.font_m, y, left_margin=20)
        y += 30
        
        # Rows
        for cat in data['categories']:
            draw.rectangle((10, y, self.width_px - 10, y + 30), outline=0, width=1)
            draw.line((200, y, 200, y + 30), fill=0, width=1)
            draw.line((400, y, 400, y + 30), fill=0, width=1)
            
            self._draw_right(draw, cat['name'], self.font_m, y, right_margin=20)
            draw.text((290, y), str(cat['qty']), font=self.font_m, fill=0)
            self._draw_left(draw, f"{cat['total']:.2f}", self.font_m, y, left_margin=20)
            y += 30
            
        # Total Row
        draw.rectangle((10, y, self.width_px - 10, y + 30), outline=0, width=1)
        draw.line((200, y, 200, y + 30), fill=0, width=1)
        self._draw_right(draw, "الاجمالي", self.font_m, y, right_margin=20)
        self._draw_left(draw, f"{data['sales']['total']:.2f}", self.font_m, y, left_margin=20)
        y += 40
        
        # 7. Returns (مرتجع) - Placeholder
        y += self._draw_centered(draw, "مرتجع", self.font_m, y)
        y += 20
        self._draw_right(draw, "عدد الفواتير: 0", self.font_m, y)
        self._draw_left(draw, "عدد الاصناف: 0", self.font_m, y)
        y += 30
        self._draw_centered(draw, "من فاتورة: 0.00", self.font_m, y)
        y += 30
        
        draw.line((10, y, self.width_px - 10, y), fill=0, width=2)
        y += 10
        
        # Footer
        # Footer
        footer_text = self.get_setting("footer_text", "Powered by Abogrida.com")
        y += self._draw_centered(draw, footer_text, self.font_s, y)
        y += 20
        
        return img.crop((0, 0, self.width_px, y))

from datetime import datetime
