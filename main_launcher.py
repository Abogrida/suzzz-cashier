import sys
import os
import threading
import time
import subprocess
import ctypes

# Patch stdout/stderr for Noconsole execution (Fixes uvicorn logging crash)
# Also force UTF-8 encoding to prevent 'charmap' errors with Arabic text
import io
if sys.stdout is None:
    class DummyWriter:
        def write(self, data): pass
        def flush(self): pass
        def isatty(self): return False
        def close(self): pass
        def fileno(self): return -1
    sys.stdout = DummyWriter()
    sys.stderr = DummyWriter()
else:
    # Force UTF-8 encoding for existing stdout/stderr
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        # Fallback for older python versions or specific environments
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
        except: pass

# Auto-configure Windows Firewall
def add_firewall_rules():
    """add firewall rules for ports 3000 and 3001"""
    try:
        # Check if running as admin
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        if is_admin:
            # Add rules silently
            subprocess.run('netsh advfirewall firewall add rule name="DawarElOmda Main" dir=in action=allow protocol=TCP localport=3000', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run('netsh advfirewall firewall add rule name="DawarElOmda Tablet" dir=in action=allow protocol=TCP localport=3001', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except:
        pass

import webbrowser
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox, QLabel, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QDialog
from PyQt6.QtCore import QUrl, QTimer, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QFont

# Fix for High DPI displays
if hasattr(sys, 'frozen'):
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

# Setup Path based on execution context
if getattr(sys, 'frozen', False):
    # EXE Mode
    BASE_DIR = os.path.dirname(sys.executable)
    # In EXE, resource path (MEI) is sys._MEIPASS for bundled files
    RESOURCE_DIR = sys._MEIPASS
    # Add backend to path specifically
    sys.path.insert(0, os.path.join(RESOURCE_DIR, "backend"))
    sys.path.insert(0, RESOURCE_DIR)
else:
    # Dev Mode
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    RESOURCE_DIR = BASE_DIR
    sys.path.insert(0, os.path.join(BASE_DIR, "backend"))
    sys.path.insert(0, os.path.join(BASE_DIR, "backend"))

PORT = 3000

class ServerThread(QThread):
    server_started = pyqtSignal(bool)
    server_error = pyqtSignal(str) # New signal for errors
    
    def run(self):
        try:
            # Capture stdout/stderr to debug startup
            # Import backend here to avoid blocking UI and resolve circular imports
            import uvicorn
            import traceback
            
            # Ensure backend directory is in path (Already done at top level, but confirming)
            backend_path = os.path.join(RESOURCE_DIR, "backend")
            if backend_path not in sys.path:
                sys.path.insert(0, backend_path)
            
            # Import app from app_core (using flat import to match backend usage)
            from app_core import app
            # Import server to register routes (side effects)
            import server as main_server
            
            # Start server
            uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
        except Exception as e:
            err_msg = "".join(traceback.format_exception(None, e, e.__traceback__))
            print(f"Server Error: {err_msg}")
            self.server_error.emit(err_msg)
            self.server_started.emit(False)

class TabletServerThread(QThread):
    def run(self):
        try:
            import uvicorn
            import sys
            import os
            from fastapi import FastAPI
            from fastapi.staticfiles import StaticFiles
            from fastapi.responses import HTMLResponse
            
            # Ensure backend path
            if getattr(sys, 'frozen', False):
                RESOURCE_DIR = sys._MEIPASS
            else:
                RESOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
                
            backend_path = os.path.join(RESOURCE_DIR, "backend")
            if backend_path not in sys.path:
                sys.path.insert(0, backend_path)
            
            # Helper to get frontend path
            def get_frontend_path(filename):
                if getattr(sys, 'frozen', False):
                    base_path = sys._MEIPASS
                    file_path = os.path.join(base_path, "frontend", filename)
                    if os.path.exists(file_path): return file_path
                    exe_dir = os.path.dirname(sys.executable)
                    alt_path = os.path.join(exe_dir, "frontend", filename)
                    if os.path.exists(alt_path): return alt_path
                    return file_path
                else:
                    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", filename)

            # Create specific Tablet App
            tablet_app = FastAPI(title="دوار العمده - Tablet")
            
            # Mount Static Files (Same as main app)
            from server import get_static_dir
            static_dir = get_static_dir()
            if os.path.exists(static_dir):
                tablet_app.mount("/static", StaticFiles(directory=static_dir), name="static")

            # Route: / -> Tablet Page
            @tablet_app.get("/", response_class=HTMLResponse)
            @tablet_app.get("/tablet", response_class=HTMLResponse)
            async def tablet_root():
                try:
                    file_path = get_frontend_path("tablet/index.html")
                    if not os.path.exists(file_path):
                        return HTMLResponse(content="<h1>Tablet page not found</h1>", status_code=404)
                    with open(file_path, "r", encoding="utf-8") as f:
                        return HTMLResponse(content=f.read())
                except Exception as e:
                    return HTMLResponse(content=f"<h1>Error: {e}</h1>", status_code=500)

            # Start specialized tablet server on port 3001
            uvicorn.run(tablet_app, host="0.0.0.0", port=3001, log_level="error")
        except Exception as e:
            print(f"Tablet Server Error: {e}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("لوحة تحكم النظام (دوار العمده)")
        self.resize(400, 200)
        
        # Set Icon
        icon_path = os.path.join(RESOURCE_DIR, "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        # Central Widget & Layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(15)
        
        # Status Label
        self.status_label = QLabel("جاري تشغيل النظام...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.layout.addWidget(self.status_label)
        
        # Info Label
        self.info_label = QLabel("سيتم فتح المتصفح تلقائياً عند جاهزية النظام")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("color: #666;")
        self.layout.addWidget(self.info_label)

        # Buttons
        button_layout = QHBoxLayout()
        
        self.open_browser_btn = QPushButton("فتح المتصفح")
        self.open_browser_btn.clicked.connect(self.open_browser)
        self.open_browser_btn.setEnabled(False)
        button_layout.addWidget(self.open_browser_btn)
        
        self.exit_btn = QPushButton("إغلاق النظام")
        self.exit_btn.clicked.connect(self.close)
        self.exit_btn.setStyleSheet("background-color: #fee2e2; color: #991b1b;")
        button_layout.addWidget(self.exit_btn)
        
        self.layout.addLayout(button_layout)
        
        # Start Server
        self.server_thread = ServerThread()
        self.server_thread.server_error.connect(self.show_error) # Connect error signal
        self.server_thread.start()
        
        # Start Tablet Server
        self.tablet_server_thread = TabletServerThread()
        self.tablet_server_thread.start()
        
        # Check server readiness
        self.retry_count = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_connection)
        self.timer.start(500) # Check every 500ms
    
    def show_error(self, error_msg):
        self.timer.stop()
        self.status_label.setText("فشل التشغيل")
        self.status_label.setStyleSheet("color: red")
        QMessageBox.critical(self, "خطأ في بدء الخادم", f"فشل تشغيل النظام:\n{error_msg}")
        
    def check_connection(self):
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', PORT))
        sock.close()
        
        if result == 0:
            # Server is ready
            self.timer.stop()
            self.server_ready()
        else:
            self.retry_count += 1
            if self.retry_count > 60: # 30 seconds timeout
                self.status_label.setText("فشل الاتصال بالخادم")
                self.info_label.setText("الرجاء إعادة تشغيل البرنامج")
                self.timer.stop()
                
    def server_ready(self):
        self.status_label.setText("النظام يعمل بنجاح")
        self.status_label.setStyleSheet("color: green")
        self.info_label.setText(f"Http://localhost:{PORT}")
        self.open_browser_btn.setEnabled(True)
        self.open_browser()
        
    def open_browser(self):
        webbrowser.open(f"http://localhost:{PORT}")
        
    def closeEvent(self, event):
        reply = QMessageBox.question(self, 'تأكيد الخروج',
            "هل أنت متأكد من إغلاق البرنامج؟\nسيتم إيقاف الخادم.", QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            event.accept()
            # Force kill to cleanup
            os._exit(0)
        else:
            event.ignore()

if __name__ == "__main__":
    # Ensure port 3000 is clean
    import subprocess
    try:
        # subprocess.run(f"taskkill /F /IM python.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        pass
    except: pass

    app_qt = QApplication(sys.argv)
    
    # Set Layout Direction to RTL for Arabic
    app_qt.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    
    # Security Check
    from activation_dialog import ActivationDialog
    security_check = ActivationDialog()
    if not security_check.is_activated():
        if security_check.exec() != QDialog.DialogCode.Accepted:
            sys.exit(0)

    # Try to add firewall rules
    add_firewall_rules()

    window = MainWindow()
    window.show()
    
    sys.exit(app_qt.exec())
