import sqlite3
import os
import sys
import time

# Database file path - works for both script and EXE
# For EXE: Save database next to the executable (portable mode)
if getattr(sys, 'frozen', False):
    # Running as compiled EXE - save in the same directory as the EXE
    EXE_DIR = os.path.dirname(sys.executable)
    DB_PATH = os.path.join(EXE_DIR, "cashier.db")
    
    # Ensure we have write permissions
    try:
        # Try to open/create a test file
        test_file = os.path.join(EXE_DIR, ".test_write")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
    except PermissionError:
        # Fallback to AppData if we can't write to EXE dir (e.g. Program Files)
        appdata_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'DawarElOmda')
        os.makedirs(appdata_dir, exist_ok=True)
        DB_PATH = os.path.join(appdata_dir, "cashier.db")
else:
    # Running as script
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_PATH = os.path.join(BASE_DIR, "cashier.db")
    DB_PATH = os.path.join(BASE_DIR, "cashier.db")

def get_db():
    """Get database connection with timeout to handle concurrent access"""
    # Create a new connection for each request (FastAPI handles threading)
    max_retries = 5
    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect(
                DB_PATH, 
                timeout=30.0, 
                check_same_thread=False
            )
            conn.row_factory = sqlite3.Row
            # Set busy timeout and optimize for concurrent access
            conn.execute("PRAGMA busy_timeout = 30000")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA cache_size = 10000")
            conn.execute("PRAGMA foreign_keys = ON")
            return conn
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and attempt < max_retries - 1:
                time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                continue
            else:
                raise

def init_db():
    """Initialize database with all required tables - creates empty database with all tables and columns"""
    # Ensure directory exists
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    
    # Use a temporary connection for initialization with retry logic
    max_retries = 5
    conn = None
    last_error = None
    
    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout = 30000")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA foreign_keys = ON")
            break
        except sqlite3.OperationalError as e:
            last_error = e
            if "locked" in str(e).lower() and attempt < max_retries - 1:
                time.sleep(0.5 * (attempt + 1))  # Exponential backoff
                continue
            else:
                raise last_error
    
    if conn is None:
        raise last_error
        
    cursor = conn.cursor()
    
    # Categories table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            is_enabled INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Add is_enabled to categories if not exists
    try:
        cursor.execute("ALTER TABLE categories ADD COLUMN is_enabled INTEGER DEFAULT 1")
    except:
        pass
    
    # Products table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            category_id INTEGER NOT NULL,
            image_path TEXT,
            is_enabled INTEGER DEFAULT 1,
            price_s REAL,
            price_m REAL,
            price_l REAL,
            has_sizes INTEGER DEFAULT 0,
            is_hidden_on_tablet INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    """)
    
    # Add new columns to products table if they don't exist
    try:
        cursor.execute("ALTER TABLE products ADD COLUMN is_hidden_on_tablet INTEGER DEFAULT 0")
    except:
        pass
    
    # Orders table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number INTEGER NOT NULL,
            table_number INTEGER DEFAULT 0,
            customer_name TEXT,
            customer_phone TEXT,
            notes TEXT,
            status TEXT DEFAULT 'pending',
            total_amount REAL NOT NULL,
            invoice_number TEXT,
            branch TEXT DEFAULT 'الفرع الرئيسي',
            cashier TEXT DEFAULT 'كاشير',
            discount_amount REAL DEFAULT 0,
            tax_amount REAL DEFAULT 0,
            vat_amount REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            completed_at TIMESTAMP
        )
    """)
    
    # Add new columns to orders table if they don't exist
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN customer_phone TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN branch TEXT DEFAULT 'الفرع الرئيسي'")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN cashier TEXT DEFAULT 'كاشير'")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN discount_amount REAL DEFAULT 0")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN tax_amount REAL DEFAULT 0")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN vat_amount REAL DEFAULT 0")
    except:
        pass
    
    # Order items table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            total REAL NOT NULL,
            size TEXT,
            additions TEXT,
            notes TEXT,
            is_printed BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)
    
    # Tables table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_number INTEGER NOT NULL UNIQUE,
            customer_name TEXT,
            phone TEXT,
            status TEXT DEFAULT 'open',
            order_id INTEGER,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (order_id) REFERENCES orders(id)
        )
    """)
    
    # Add missing columns to existing order_items table if they don't exist
    try:
        cursor.execute("PRAGMA table_info(order_items)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'additions' not in columns:
            cursor.execute("ALTER TABLE order_items ADD COLUMN additions TEXT")
            print("Added 'additions' column to order_items table")
        
        if 'notes' not in columns:
            cursor.execute("ALTER TABLE order_items ADD COLUMN notes TEXT")
            print("Added 'notes' column to order_items table")
            
        if 'is_printed' not in columns:
            cursor.execute("ALTER TABLE order_items ADD COLUMN is_printed BOOLEAN DEFAULT 0")
            print("Added 'is_printed' column to order_items table")
    except Exception as e:
        print(f"Error checking/adding columns to order_items: {e}")
    
    # Product additions table (global additions available for all products)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_additions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Insert default additions if they don't exist
    cursor.execute("SELECT COUNT(*) FROM product_additions")
    if cursor.fetchone()[0] == 0:
        default_additions = [
            ("سادة",),
            ("محوج",),
            ("مضبوط",),
            ("فاتح",),
            ("غامق",),
            ("وسط",),
            ("علي الريحه",),
            ("زياده",),
            ("مانو",),
        ]
        cursor.executemany("INSERT INTO product_additions (name) VALUES (?)", default_additions)
        conn.commit()
    
    # Invoices table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT NOT NULL UNIQUE,
            order_id INTEGER NOT NULL,
            order_number TEXT NOT NULL,
            table_number INTEGER DEFAULT 0,
            customer_name TEXT,
            customer_phone TEXT,
            invoice_location TEXT DEFAULT 'سفری',
            total_amount REAL NOT NULL,
            quantity INTEGER DEFAULT 1,
            discount_amount REAL DEFAULT 0,
            tax_amount REAL DEFAULT 0,
            total_before_vat REAL NOT NULL,
            vat_amount REAL DEFAULT 0,
            net_amount REAL NOT NULL,
            status TEXT DEFAULT 'paid',
            payment_method TEXT DEFAULT 'cash',
            branch TEXT DEFAULT 'الفرع الرئيسي',
            cashier TEXT DEFAULT 'كاشير',
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (order_id) REFERENCES orders(id)
        )
    """)
    
    # Add new columns to invoices table if they don't exist
    try:
        cursor.execute("ALTER TABLE invoices ADD COLUMN customer_phone TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE invoices ADD COLUMN invoice_location TEXT DEFAULT 'سفری'")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE invoices ADD COLUMN quantity INTEGER DEFAULT 1")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE invoices ADD COLUMN discount_amount REAL DEFAULT 0")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE invoices ADD COLUMN tax_amount REAL DEFAULT 0")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE invoices ADD COLUMN total_before_vat REAL NOT NULL DEFAULT 0")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE invoices ADD COLUMN vat_amount REAL DEFAULT 0")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE invoices ADD COLUMN net_amount REAL NOT NULL DEFAULT 0")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE invoices ADD COLUMN branch TEXT DEFAULT 'الفرع الرئيسي'")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE invoices ADD COLUMN cashier TEXT DEFAULT 'كاشير'")
    except:
        pass
    
    # Settings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Shift settings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shift_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number_of_shifts INTEGER DEFAULT 2,
            shift1_name TEXT DEFAULT 'صباحي',
            shift1_start_time TEXT DEFAULT '08:00',
            shift1_end_time TEXT DEFAULT '16:00',
            shift2_name TEXT DEFAULT 'مسائي',
            shift2_start_time TEXT DEFAULT '16:00',
            shift2_end_time TEXT DEFAULT '00:00',
            shift3_name TEXT,
            shift3_start_time TEXT,
            shift3_end_time TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Shifts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shift_name TEXT NOT NULL,
            shift_number INTEGER DEFAULT 1,
            shift_date DATE NOT NULL,
            opened_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            closed_at TIMESTAMP,
            opened_by TEXT,
            closed_by TEXT,
            status TEXT DEFAULT 'open',
            total_revenue REAL DEFAULT 0,
            total_orders INTEGER DEFAULT 0,
            total_invoices INTEGER DEFAULT 0,
            notes TEXT,
            UNIQUE(shift_name, shift_date, shift_number)
        )
    """)
    
    # Add shift_id to orders table
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN shift_id INTEGER")
    except:
        pass
    
    # Add shift_id to invoices table
    try:
        cursor.execute("ALTER TABLE invoices ADD COLUMN shift_id INTEGER")
    except:
        pass
    
    # Add cash drawer fields to shifts table
    try:
        cursor.execute("ALTER TABLE shifts ADD COLUMN cash_drawer_amount REAL DEFAULT 0")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE shifts ADD COLUMN cash_expected REAL DEFAULT 0")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE shifts ADD COLUMN cash_difference REAL DEFAULT 0")
    except:
        pass
    
    # Insert default shift settings if they don't exist
    cursor.execute("SELECT COUNT(*) FROM shift_settings")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO shift_settings (number_of_shifts, shift1_name, shift1_start_time, shift1_end_time, 
                                      shift2_name, shift2_start_time, shift2_end_time)
            VALUES (2, 'صباحي', '08:00', '16:00', 'مسائي', '16:00', '00:00')
        """)
    
    # Don't insert default categories - let user add them manually
    # cursor.execute("SELECT COUNT(*) FROM categories")
    # if cursor.fetchone()[0] == 0:
    #     default_categories = [
    #         ("drinks",),
    #         ("breakfast",),
    #         ("lunch",),
    #         ("desserts",)
    #     ]
    #     cursor.executemany("INSERT INTO categories (name) VALUES (?)", default_categories)
    
    # Insert default settings if they don't exist
    cursor.execute("SELECT COUNT(*) FROM settings")
    if cursor.fetchone()[0] == 0:
        default_settings = [
            ("admin_password", "12345"),
            ("cashier_password", "1234"),
            ("owner_password", "2212"),
            ("printer_ip", ""),
            ("restaurant_name", "دوار العمده"),
            ("restaurant_address", "قبل بنزينه توتال ابو الاخضر - طريقه الزقازيق القاهره الصحراوي"),
            ("footer_text", "Powered by Abogrida.com"),
            ("logo_path", ""),
            ("playstation_price_per_hour", "50"),
            ("playstation_price_multi", "70"),
            ("playstation_enabled", "0")
        ]
        cursor.executemany("INSERT INTO settings (key, value) VALUES (?, ?)", default_settings)
    
    # Check if tables table exists and has required columns
    try:
        cursor.execute("PRAGMA table_info(tables)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if len(columns) == 0:
            # Table doesn't exist, create it
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tables (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_number INTEGER NOT NULL UNIQUE,
                    customer_name TEXT,
                    phone TEXT,
                    status TEXT DEFAULT 'open',
                    order_id INTEGER,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    FOREIGN KEY (order_id) REFERENCES orders(id)
                )
            """)
            print("Created tables table")
        else:
            # Table exists, check for missing columns
            required_columns = ['id', 'table_number', 'customer_name', 'phone', 'status', 'order_id', 'created_at', 'updated_at']
            for col in required_columns:
                if col not in columns:
                    if col == 'order_id':
                        cursor.execute("ALTER TABLE tables ADD COLUMN order_id INTEGER")
                    elif col == 'updated_at':
                        cursor.execute("ALTER TABLE tables ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                    print(f"Added missing column {col} to tables table")
        if 'playstation_start_time' not in columns:
            cursor.execute("ALTER TABLE tables ADD COLUMN playstation_start_time TIMESTAMP")
            print("Added 'playstation_start_time' column to tables table")

    
        if 'playstation_type' not in columns:
            cursor.execute("ALTER TABLE tables ADD COLUMN playstation_type TEXT")
            print("Added 'playstation_type' column to tables table")

    except Exception as e:
        print(f"Error checking/creating tables table: {e}")
        import traceback
        traceback.print_exc()

    # --- CLOUD SYNC COLUMNS ---
    # Add is_synced to orders
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN is_synced INTEGER DEFAULT 0")
        print("Added 'is_synced' to orders")
    except:
        pass # Probably exists

    # Add is_synced to invoices
    try:
        cursor.execute("ALTER TABLE invoices ADD COLUMN is_synced INTEGER DEFAULT 0")
        print("Added 'is_synced' to invoices")
    except:
        pass

    # Add is_synced to shifts
    try:
        cursor.execute("ALTER TABLE shifts ADD COLUMN is_synced INTEGER DEFAULT 0")
        print("Added 'is_synced' to shifts")
    except:
        pass
        
    # Add is_synced to tables (optional, but good for real-time status online)
    try:
        cursor.execute("ALTER TABLE tables ADD COLUMN is_synced INTEGER DEFAULT 0")
        print("Added 'is_synced' to tables")
    except:
        pass

    conn.commit()
    conn.close()
