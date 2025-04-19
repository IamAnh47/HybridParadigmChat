from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QMessageBox, QSpinBox,
                             QTabWidget, QWidget)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from src.database.models import User
from src.database.config import SessionLocal
import hashlib
import socket
import logging

class StartupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Discord-like Chat - Startup")
        self.setFixedSize(400, 500)
        self.setStyleSheet("""
            QDialog {
                background-color: #36393f;
            }
            QLabel {
                color: #ffffff;
                font-size: 14px;
            }
            QLineEdit {
                background-color: #40444b;
                color: #ffffff;
                border: 1px solid #202225;
                border-radius: 3px;
                padding: 8px;
                font-size: 14px;
            }
            QSpinBox {
                background-color: #40444b;
                color: #ffffff;
                border: 1px solid #202225;
                border-radius: 3px;
                padding: 8px;
                font-size: 14px;
            }
            QPushButton {
                background-color: #5865f2;
                color: #ffffff;
                border: none;
                border-radius: 3px;
                padding: 10px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4752c4;
            }
            QTabWidget::pane {
                border: none;
            }
            QTabBar::tab {
                background-color: #2f3136;
                color: #b9bbbe;
                padding: 10px 20px;
                border: none;
            }
            QTabBar::tab:selected {
                color: #ffffff;
                border-bottom: 2px solid #5865f2;
            }
        """)
        
        self.user = None
        self.port = None
        
        self.init_ui()
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # Port selection
        port_layout = QHBoxLayout()
        port_label = QLabel("Select Port:")
        self.port_input = QSpinBox()
        self.port_input.setRange(5001, 9999)
        self.port_input.setValue(5001)
        port_layout.addWidget(port_label)
        port_layout.addWidget(self.port_input)
        main_layout.addLayout(port_layout)
        
        # Title
        title = QLabel("Welcome to Discord-like Chat")
        title.setFont(QFont("Arial", 20, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)
        
        # Create tab widget
        tabs = QTabWidget()
        
        # Login tab
        login_tab = QWidget()
        login_layout = QVBoxLayout(login_tab)
        login_layout.setSpacing(15)
        
        # Username
        username_label = QLabel("Username")
        self.login_username = QLineEdit()
        self.login_username.setPlaceholderText("Enter your username")
        login_layout.addWidget(username_label)
        login_layout.addWidget(self.login_username)
        
        # Password
        password_label = QLabel("Password")
        self.login_password = QLineEdit()
        self.login_password.setPlaceholderText("Enter your password")
        self.login_password.setEchoMode(QLineEdit.Password)
        login_layout.addWidget(password_label)
        login_layout.addWidget(self.login_password)
        
        # Login button
        login_button = QPushButton("Login")
        login_button.clicked.connect(self.login)
        login_layout.addWidget(login_button)
        
        # Register tab
        register_tab = QWidget()
        register_layout = QVBoxLayout(register_tab)
        register_layout.setSpacing(15)
        
        # Username
        username_label = QLabel("Username")
        self.register_username = QLineEdit()
        self.register_username.setPlaceholderText("Enter your username")
        register_layout.addWidget(username_label)
        register_layout.addWidget(self.register_username)
        
        # Password
        password_label = QLabel("Password")
        self.register_password = QLineEdit()
        self.register_password.setPlaceholderText("Enter your password")
        self.register_password.setEchoMode(QLineEdit.Password)
        register_layout.addWidget(password_label)
        register_layout.addWidget(self.register_password)
        
        # Confirm Password
        confirm_password_label = QLabel("Confirm Password")
        self.register_confirm_password = QLineEdit()
        self.register_confirm_password.setPlaceholderText("Confirm your password")
        self.register_confirm_password.setEchoMode(QLineEdit.Password)
        register_layout.addWidget(confirm_password_label)
        register_layout.addWidget(self.register_confirm_password)
        
        # Register button
        register_button = QPushButton("Register")
        register_button.clicked.connect(self.register)
        register_layout.addWidget(register_button)
        
        # Add tabs
        tabs.addTab(login_tab, "Login")
        tabs.addTab(register_tab, "Register")
        
        main_layout.addWidget(tabs)
        
        # Visitor mode button
        visitor_button = QPushButton("Continue as Visitor")
        visitor_button.setStyleSheet("""
            QPushButton {
                background-color: #2f3136;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #40444b;
            }
        """)
        visitor_button.clicked.connect(self.visitor_mode)
        main_layout.addWidget(visitor_button)
        
    def check_port_available(self, port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(('localhost', port))
            sock.close()
            return True
        except socket.error:
            return False
            
    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()
        
    def login(self):
        port = self.port_input.value()
        if not self.check_port_available(port):
            QMessageBox.warning(self, "Error", f"Port {port} is already in use. Please select another port.")
            return
            
        username = self.login_username.text()
        password = self.login_password.text()
        
        if not username or not password:
            QMessageBox.warning(self, "Error", "Please fill in all fields")
            return
            
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == username).first()
            if user and user.password == self.hash_password(password):
                self.port = port
                self.user = user
                self.accept()
            else:
                QMessageBox.warning(self, "Error", "Invalid username or password")
        finally:
            db.close()
            
    def register(self):
        port = self.port_input.value()
        if not self.check_port_available(port):
            QMessageBox.warning(self, "Error", f"Port {port} is already in use. Please select another port.")
            return
            
        username = self.register_username.text()
        password = self.register_password.text()
        confirm_password = self.register_confirm_password.text()
        
        if not all([username, password, confirm_password]):
            QMessageBox.warning(self, "Error", "All fields are required")
            return
            
        if password != confirm_password:
            QMessageBox.warning(self, "Error", "Passwords do not match")
            return
            
        db = SessionLocal()
        try:
            # Check if username already exists
            existing_user = db.query(User).filter(User.username == username).first()
            if existing_user:
                QMessageBox.warning(self, "Error", "Username already exists")
                return
                
            # Create new user
            new_user = User(
                username=username,
                password=password,
                status="offline",
                role="user"
            )
            db.add(new_user)
            db.commit()
            
            self.port = port
            self.user = new_user
            self.accept()
            
        except Exception as e:
            db.rollback()
            QMessageBox.critical(self, "Error", f"Registration failed: {str(e)}")
        finally:
            db.close()
            
    def visitor_mode(self):
        port = self.port_input.value()
        if not self.check_port_available(port):
            QMessageBox.warning(self, "Error", f"Port {port} is already in use. Please select another port.")
            return
            
        self.port = port
        self.user = None
        self.accept() 