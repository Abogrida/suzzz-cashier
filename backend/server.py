"""
Main FastAPI Application for Dawar El Omda
"""
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import WebSocket
import os
import sys
import socket
import threading
import time

# Force UTF-8 encoding for stdout and stderr (for Windows console support of Arabic)
if sys.platform.startswith('win'):
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        # In PyInstaller --noconfirm --noconsole, stdout might be None or DummyWriter
        pass

# Import routers
# Import routers (Moved below app creation to avoid circular imports)
# from api import admin, categories, products, orders, tables, settings, invoices, shifts, additions, printing, backup, reports, reports

# Import database functions
from db import init_db, get_db

# Import WebSocket manager
from websocket_manager import manager

from app_core import app, BASE_DIR, get_static_dir

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Start Sync Agent
@app.on_event("startup")
async def startup_event():
    try:
        from sync_agent import sync_agent
        sync_agent.start()
        print("[INFO] SyncAgent started successfully")
    except Exception as e:
        print(f"[ERROR] Failed to start SyncAgent: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    try:
        from sync_agent import sync_agent
        sync_agent.stop()
        print("[INFO] SyncAgent stopped successfully")
    except Exception as e:
        print(f"[ERROR] Failed to stop SyncAgent: {e}")

# Block any PDF download attempts - FORCE BLOCK - NO PDF FILES ALLOWED
@app.middleware("http")
async def block_pdf_downloads(request, call_next):
    """Block any PDF download attempts - FORCE BLOCK - NO PDF FILES ALLOWED"""
    url_str = str(request.url).lower()
    path_str = request.url.path.lower()
    query_str = str(request.url.query).lower()
    
    # Block any PDF-related requests - COMPREHENSIVE BLOCK
    if ("pdf" in url_str or "pdf" in path_str or "pdf" in query_str or
        "/download" in path_str or "/download-pdf" in path_str or
        path_str.endswith(".pdf") or
        "application/pdf" in str(request.headers.get("accept", "")).lower() or
        "application/pdf" in str(request.headers.get("content-type", "")).lower() or
        "attachment" in str(request.headers.get("content-disposition", "")).lower() and "pdf" in str(request.headers.get("content-disposition", "")).lower()):
        from fastapi.responses import Response
        print(f"[BLOCKED] FORCE BLOCKED PDF REQUEST: {request.method} {request.url.path} from {request.client.host if request.client else 'unknown'}")
        print(f"   Headers: Accept={request.headers.get('accept')}, Content-Type={request.headers.get('content-type')}")
        return Response(
            status_code=404,
            content="PDF download completely disabled. Printing goes directly to USB printer only.",
            media_type="text/plain",
            headers={
                "X-PDF-Blocked": "true",
                "Content-Disposition": "inline; filename=blocked.txt",
                "Cache-Control": "no-store, no-cache, must-revalidate"
            }
        )
    
    response = await call_next(request)
    
    # Also block PDF in response headers - DOUBLE CHECK - FORCE OVERRIDE
    content_type = response.headers.get("content-type", "").lower()
    content_disposition = response.headers.get("content-disposition", "").lower()
    
    # FORCE BLOCK any PDF content
    if ("application/pdf" in content_type or 
        (".pdf" in content_disposition and "attachment" in content_disposition) or
        ".pdf" in str(response.headers.get("content-disposition", "")).lower()):
        print(f"[BLOCKED] FORCE BLOCKED PDF RESPONSE: {request.url.path}")
        print(f"   Response Content-Type: {content_type}")
        print(f"   Response Content-Disposition: {content_disposition}")
        # Return JSON instead to prevent browser from trying to save as PDF
        from fastapi.responses import JSONResponse
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
    
    # FORCE OVERRIDE: Remove any PDF-related headers from ALL responses
    if "content-disposition" in response.headers:
        disposition = response.headers["content-disposition"].lower()
        if ".pdf" in disposition or "attachment" in disposition:
            # Remove the header to prevent download
            del response.headers["content-disposition"]
            print(f"[INFO] REMOVED PDF Content-Disposition header from: {request.url.path}")
    
    # FORCE: Set Content-Type to JSON if it's PDF
    if "application/pdf" in content_type:
        response.headers["content-type"] = "application/json"
        print(f"[INFO] OVERRIDDEN PDF Content-Type to JSON for: {request.url.path}")
    
    return response

# Include routers
# Imports moved here to resolve circular dependency with app
from api import admin, categories, products, orders, tables, settings, invoices, shifts, additions, printing, backup, playstation, reports

app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(categories.router, prefix="/api", tags=["categories"])
app.include_router(products.router, prefix="/api", tags=["products"])
app.include_router(orders.router, prefix="/api", tags=["orders"])
app.include_router(tables.router, prefix="/api", tags=["tables"])
app.include_router(settings.router, prefix="/api", tags=["settings"])
app.include_router(invoices.router, prefix="/api", tags=["invoices"])
app.include_router(shifts.router, prefix="/api", tags=["shifts"])
app.include_router(additions.router, prefix="/api", tags=["additions"])
app.include_router(printing.router, prefix="/api", tags=["printing"])
app.include_router(playstation.router, prefix="/api", tags=["playstation"])
app.include_router(backup.router, prefix="/api/backup", tags=["backup"])
app.include_router(reports.router, prefix="/api", tags=["reports"])

# Serve static files (Function imported from core)

# Serve uploaded images from EXE directory when running as EXE
# IMPORTANT: This must be defined BEFORE app.mount("/static") to take precedence
if getattr(sys, 'frozen', False):
    from fastapi.responses import FileResponse
    # Serve uploaded images from EXE directory when running as EXE
    exe_dir = os.path.dirname(sys.executable)
    images_dir = os.path.join(exe_dir, "images")
    
    @app.get("/static/images/products/{filename}")
    async def serve_product_image(filename: str):
        """Serve product images from EXE directory when running as EXE"""
        # 1. Try to serve from EXE/images/products (User uploaded)
        image_path = os.path.join(images_dir, "products", filename)
        if os.path.exists(image_path):
            # Add cache control to prevent flickering
            return FileResponse(image_path, headers={"Cache-Control": "public, max-age=3600"})
            
        # 2. Try to serve from internal static files (Default/Bundled)
        static_dir = get_static_dir()
        static_image_path = os.path.join(static_dir, "images", "products", filename)
        if os.path.exists(static_image_path):
            return FileResponse(static_image_path, headers={"Cache-Control": "public, max-age=3600"})
            
        # 3. If not found, return 404
        # We don't raise HTTPException immediately to let other routes try if needed, 
        # but since this is a specific file route, we should probably 404 here.
        raise HTTPException(status_code=404, detail="Image not found")

    @app.get("/static/images/logo/{filename}")
    async def serve_logo_image(filename: str):
        """Serve logo images from EXE directory when running as EXE"""
        # 1. Try to serve from EXE/images/logo (User uploaded)
        image_path = os.path.join(images_dir, "logo", filename)
        if os.path.exists(image_path):
            return FileResponse(image_path, headers={"Cache-Control": "no-cache"})
            
        # 2. Try to serve from internal static files
        static_dir = get_static_dir()
        static_image_path = os.path.join(static_dir, "images", "logo", filename)
        if os.path.exists(static_image_path):
            return FileResponse(static_image_path, headers={"Cache-Control": "public, max-age=3600"})
            
        raise HTTPException(status_code=404, detail="Image not found")

static_dir = get_static_dir()
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")



# Helper function to get frontend file path
def get_frontend_path(filename):
    if getattr(sys, 'frozen', False):
        # When running as EXE, files are in _MEIPASS
        base_path = sys._MEIPASS
        file_path = os.path.join(base_path, "frontend", filename)
        if os.path.exists(file_path):
            return file_path
        # Fallback: try EXE directory
        exe_dir = os.path.dirname(sys.executable)
        alt_path = os.path.join(exe_dir, "frontend", filename)
        if os.path.exists(alt_path):
            return alt_path
        return file_path  # Return original path even if not found
    else:
        base_path = BASE_DIR
        return os.path.join(base_path, "frontend", filename)

# Health check endpoint
@app.get("/api/health")
def health_check():
    """Health check endpoint for loading page"""
    return {"status": "ok", "message": "Server is running"}

# WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo back or handle messages
            await websocket.send_text(f"Echo: {data}")
    except Exception as e:
        manager.disconnect(websocket)

# Serve HTML pages
@app.get("/", response_class=HTMLResponse)
async def root():
    """Redirect to login page"""
    try:
        file_path = get_frontend_path("login/index.html")
        if not os.path.exists(file_path):
            return HTMLResponse(content="<h1>Login page not found</h1>", status_code=404)
        with open(file_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error loading page: {e}</h1>", status_code=500)

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    """Login page"""
    try:
        file_path = get_frontend_path("login/index.html")
        if not os.path.exists(file_path):
            return HTMLResponse(content="<h1>Login page not found</h1>", status_code=404)
        with open(file_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error loading page: {e}</h1>", status_code=500)

@app.get("/admin", response_class=HTMLResponse)
@app.get("/admin/", response_class=HTMLResponse)
@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_page():
    """Admin page"""
    try:
        file_path = get_frontend_path("admin/index.html")
        if not os.path.exists(file_path):
            # Try alternative path
            alt_path = os.path.join(BASE_DIR, "frontend", "admin", "index.html")
            if os.path.exists(alt_path):
                file_path = alt_path
            else:
                return HTMLResponse(content=f"<h1>Admin page not found at: {file_path}</h1>", status_code=404)
        with open(file_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except Exception as e:
        import traceback
        error_msg = f"<h1>Error loading admin page: {e}</h1><pre>{traceback.format_exc()}</pre>"
        return HTMLResponse(content=error_msg, status_code=500)

@app.get("/cashier", response_class=HTMLResponse)
async def cashier_page():
    """Cashier page"""
    try:
        file_path = get_frontend_path("cashier/index.html")
        if not os.path.exists(file_path):
            return HTMLResponse(content="<h1>Cashier page not found</h1>", status_code=404)
        with open(file_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error loading page: {e}</h1>", status_code=500)

@app.get("/tablet", response_class=HTMLResponse)
async def tablet_page():
    """Tablet page"""
    try:
        file_path = get_frontend_path("tablet/index.html")
        if not os.path.exists(file_path):
            return HTMLResponse(content="<h1>Tablet page not found</h1>", status_code=404)
        with open(file_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error loading page: {e}</h1>", status_code=500)

@app.get("/loading", response_class=HTMLResponse)
async def loading_page():
    """Loading page for the desktop app"""
    try:
        file_path = get_frontend_path("loading.html")
        if not os.path.exists(file_path):
            return HTMLResponse(content="<h1>Loading file not found</h1>", status_code=404)
        with open(file_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error loading page: {e}</h1>", status_code=500)

# Get local IP address function
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

# Shutdown handlers (placeholder functions for compatibility)
def close_all_open_shifts():
    """Close all open shifts - placeholder"""
    pass

def setup_shutdown_handlers():
    """Setup shutdown handlers - placeholder"""
    pass

# Initialize database synchronously on startup to ensure it's ready
# This ensures the database is created with all tables and columns before the server starts
try:
    init_db()
    
    # Initialize menu data on first run (if database is empty)
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) FROM categories")
        category_count = cursor.fetchone()[0]
        db.close()
        
        if category_count == 0:
            # Database is empty, initialize menu
            print("[INFO] Initializing menu data on first run...")
            try:
                from init_menu_data import init_menu_data
                init_menu_data()
                print("[SUCCESS] Menu initialized successfully!")
            except Exception as menu_error:
                print(f"[WARNING] Could not initialize menu: {menu_error}")
    except Exception as menu_init_error:
        print(f"[WARNING] Could not check/initialize menu: {menu_init_error}")
        
except Exception as e:
    # Log error to file since console is hidden
    try:
        base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.getcwd()
        error_file = os.path.join(base_dir, "server_error.log")
        with open(error_file, "a", encoding="utf-8") as f:
            f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Database init error: {e}\n")
            import traceback
            f.write(traceback.format_exc())
    except:
        pass

@app.post("/api/cash-drawer/open")
async def open_drawer_api():
    try:
        from printing import open_cash_drawer
        # Print slip when manually opening drawer
        success = open_cash_drawer(print_slip=True)
        if success:
            return {"status": "success", "message": "تم فتح الدرج بنجاح"}
        else:
            return JSONResponse(status_code=500, content={"detail": "فشل في فتح الدرج"})
    except Exception as e:
        print(f"Error opening drawer: {e}")
        return JSONResponse(status_code=500, content={"detail": str(e)})

@app.get("/api/printers/list")
async def list_printers():
    """List all available printers on the system"""
    try:
        import win32print
        # Get all printers (local and network)
        printers = []
        printer_list = win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        )
        
        for printer_info in printer_list:
            printer_name = printer_info[2]  # Printer name is at index 2
            printers.append({
                "name": printer_name,
                "is_default": printer_name == win32print.GetDefaultPrinter()
            })
        
        return {"printers": printers}
    except Exception as e:
        print(f"Error listing printers: {e}")
        return JSONResponse(
            status_code=500, 
            content={"detail": f"خطأ في جلب قائمة الطابعات: {str(e)}"}
        )

if __name__ == "__main__":
    import uvicorn
    local_ip = get_local_ip()
    print(f"\n{'='*50}")
    print(f"دوار العمده - نظام إدارة المطعم")
    print(f"Local Network: http://{local_ip}:3000")
    print(f"Local Access: http://localhost:3000")
    print(f"{'='*50}\n")
    uvicorn.run(app, host="0.0.0.0", port=3000, log_level="info")
