import os
import sys
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display
from escpos.printer import Win32Raw
import win32print

# Add backend directory to path to find db
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from db import get_db

def get_printer_name():
    """Get printer name with auto-detection and saving"""
    db = None
    try:
        db = get_db()
        cursor = db.cursor()
        
        # 1. Try to get saved printer
        cursor.execute("SELECT value FROM settings WHERE key = 'printer_ip'")
        result = cursor.fetchone()
        
        if result and result["value"]:
            saved_printer = result["value"]
            # Check if it's BROWSER_PRINT mode
            if saved_printer == "BROWSER_PRINT":
                print(f"[INFO] Browser Print Mode enabled")
                return "BROWSER_PRINT"
            # Just return it, don't test connection (User might be offline)
            # We assume if it's saved, it's correct.
            print(f"[INFO] Using saved printer: {saved_printer}")
            return saved_printer
                
        # 2. Auto-detect physical printer
        print("[INFO] Auto-detecting printer...")
        printers = [p[2] for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)]
        
        virtual_keywords = ["PDF", "XPS", "OneNote", "Fax", "Root", "Microsoft", "Writer"]
        physical_printers = []
        
        for p in printers:
            is_virtual = any(k.lower() in p.lower() for k in virtual_keywords)
            if not is_virtual:
                physical_printers.append(p)
                
        selected_printer = None
        if physical_printers:
            selected_printer = physical_printers[0]
            print(f"[INFO] Detected physical printer: {selected_printer}")
        else:
            # Fallback to default if no physical printer found
            try:
                selected_printer = win32print.GetDefaultPrinter()
                print(f"[INFO] Using default printer: {selected_printer}")
            except:
                pass
                
        # 3. Save detected printer to DB
        if selected_printer:
            try:
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('printer_ip', ?)", (selected_printer,))
                db.commit()
                print(f"[INFO] Saved printer {selected_printer} to database.")
            except Exception as e:
                print(f"[WARN] Failed to save printer to DB: {e}")
                
        return selected_printer
        
    except Exception as e:
        print(f"[WARN] Error in printer detection: {e}")
        try:
            return win32print.GetDefaultPrinter()
        except:
            return None
    finally:
        if db:
            db.close()

class HybridPrinter:
    def __init__(self, printer_name=None):
        if not printer_name:
            self.printer_name = get_printer_name()
        else:
            self.printer_name = printer_name
        
        # Check if BROWSER_PRINT mode
        if self.printer_name == "BROWSER_PRINT":
            print("[HybridPrinter] Browser Print Mode - Skipping physical printer connection")
            self.printer = None
            return
            
        if not self.printer_name:
            raise Exception("No printer found")
            
        print(f"[HybridPrinter] Connecting to: {self.printer_name}")
        self.printer = Win32Raw(self.printer_name)
        # self.printer.initialize() # Win32Raw might not have this
        self.printer._raw(b'\x1B@')
        
        # Font configuration
        self.font_path = "arial.ttf"
        self.base_font_size = 28 
        
    def is_arabic(self, text):
        """Check if text contains Arabic characters"""
        for char in str(text):
            if '\u0600' <= char <= '\u06FF':
                return True
        return False

    def _get_font(self, size_name):
        size_map = {
            'small': self.base_font_size - 6,
            'normal': self.base_font_size,
            'large': self.base_font_size + 8,
            'xlarge': self.base_font_size + 16
        }
        size = size_map.get(size_name, self.base_font_size)
        try:
            return ImageFont.truetype(self.font_path, size)
        except:
            return ImageFont.load_default()

    def text_to_image(self, text, size='normal', align='left', width=384):
        """Convert text line to image with alignment"""
        font = self._get_font(size)
        
        # Reshape
        reshaped_text = arabic_reshaper.reshape(str(text))
        bidi_text = get_display(reshaped_text)

        # Measure
        dummy_img = Image.new('RGB', (1, 1))
        dummy_draw = ImageDraw.Draw(dummy_img)
        bbox = dummy_draw.textbbox((0, 0), bidi_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        img_width = max(width, text_width)
        img_height = text_height + 10
        
        image = Image.new('1', (img_width, img_height), 255)
        draw = ImageDraw.Draw(image)
        
        # Calculate X based on alignment
        if align == 'center':
            x = (img_width - text_width) / 2
        elif align == 'right':
            x = img_width - text_width - 5
        else: # left
            x = 5
            
        draw.text((x, 0), bidi_text, font=font, fill=0)
        return image

    def set_align(self, align):
        """Send ESC/POS alignment command"""
        if align == 'center':
            self.printer._raw(b'\x1B\x61\x01')
        elif align == 'right':
            self.printer._raw(b'\x1B\x61\x02')
        else:
            self.printer._raw(b'\x1B\x61\x00')

    def set_size(self, size):
        """Send ESC/POS font size command"""
        # GS ! n
        if size == 'xlarge':
            self.printer._raw(b'\x1D\x21\x11') # Double width & height
        elif size == 'large':
            self.printer._raw(b'\x1D\x21\x01') # Double height
        elif size == 'small':
            self.printer._raw(b'\x1D\x21\x01') # Small font
        else:
            self.printer._raw(b'\x1D\x21\x00') # Normal

    def print_line(self, text, size='normal', align='left'):
        """Smart print line: Image for Arabic, Text for English"""
        if not text:
            self.printer.text("\n")
            return

        if self.is_arabic(text):
            # Arabic -> Image
            try:
                img = self.text_to_image(text, size, align)
                self.printer.image(img)
            except Exception as e:
                print(f"[ERROR] Image print failed: {e}")
                self.printer.text(str(text) + "\n")
        else:
            # English -> Raw Text
            self.set_align(align)
            self.set_size(size)
            self.printer.text(str(text) + "\n")
            # Reset to defaults
            self.set_align('left')
            self.set_size('normal')

    def print_separator(self):
        self.printer.text("-" * 32 + "\n")

    def kick_drawer(self):
        """Open cash drawer"""
        self.printer.cashdraw(2)
        self.printer.cashdraw(5)

    def cut(self):
        self.printer.cut()
        
    def close(self):
        self.printer.close()
