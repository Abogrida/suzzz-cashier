
import sys
import os
import hashlib
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QHBoxLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon

class ActivationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("تفعيل النظام")
        self.setFixedSize(400, 250)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        
        # Styling
        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
            }
            QLabel {
                color: #1e293b;
            }
            QLineEdit {
                padding: 10px;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton {
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Title
        title = QLabel("تفعيل نسخة البرنامج")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        # Input
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("أدخل كود التفعيل...")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.returnPressed.connect(self.check_activation)
        layout.addWidget(self.password_input)

        # Buttons
        btn_layout = QHBoxLayout()
        
        self.activate_btn = QPushButton("تفعيل")
        self.activate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.activate_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:pressed {
                background-color: #1e40af;
            }
        """)
        self.activate_btn.clicked.connect(self.check_activation)
        btn_layout.addWidget(self.activate_btn)

        self.cancel_btn = QPushButton("إغلاق")
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #64748b;
                border: 1px solid #cbd5e1;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
            }
        """)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)
        
        self.activation_file = self.get_activation_path()
        self.machine_id = self.get_machine_id()

    def get_activation_path(self):
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
        return os.path.join(base_dir, "activation.key")

    def get_machine_id(self):
        try:
            # Method 1: Windows UUID (Strongest)
            import subprocess
            cmd = 'wmic csproduct get uuid'
            uuid = subprocess.check_output(cmd, shell=True).decode().split('\n')[1].strip()
            if uuid:
                return uuid
        except:
            pass
            
        try:
            # Method 2: Mac Address (Fallback)
            import uuid
            return str(uuid.getnode())
        except:
            # Method 3: Fallback generic (Not unique per machine but allows run)
            return "UNKNOWN_MACHINE_ID"

    def is_activated(self):
        if not os.path.exists(self.activation_file):
            return False
            
        try:
            with open(self.activation_file, 'r') as f:
                saved_hash = f.read().strip()
            
            # Verify hash matches THIS machine
            current_hash = hashlib.sha256((self.machine_id + "MADO_SALT_2024").encode()).hexdigest()
            return saved_hash == current_hash
        except:
            return False

    def check_activation(self):
        password = self.password_input.text()
        if password == "MADO2212":
            try:
                # Save activation bound to THIS machine
                with open(self.activation_file, 'w') as f:
                    device_hash = hashlib.sha256((self.machine_id + "MADO_SALT_2024").encode()).hexdigest()
                    f.write(device_hash)
                
                QMessageBox.information(self, "نجاح", "تم تفعيل البرنامج بنجاح لهذا الجهاز")
                self.accept()
            except Exception as e:
                QMessageBox.critical(self, "خطأ", f"فشل حفظ التفعيل: {str(e)}")
        else:
            QMessageBox.warning(self, "خطأ", "كود التفعيل غير صحيح")
            self.password_input.clear()
            self.password_input.setFocus()
