from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QMessageBox, QTabWidget,
                             QFrame, QDialog, QSpinBox, QInputDialog)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from src.database.models import User
from src.database.config import SessionLocal
import logging
import socket
import random

class AuthDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hybrid ParadigmChat Chat Application - Login")
        self.setFixedSize(400, 550) 
        self.setStyleSheet("""
            QDialog {
                background-color: #36393f;
            }
            QWidget {
                background-color: #36393f;
            }
            QLabel {
                color: #ffffff;
                font-size: 14px; /* Reduced font size for labels */
            }
            QLineEdit {
                background-color: #40444b;
                color: #ffffff;
                border: 1px solid #202225;
                border-radius: 3px;
                padding: 10px; /* Reduced padding */
                font-size: 14px; /* Reduced font size */
                min-height: 35px; /* Reduced min height */
            }
            QPushButton {
                background-color: #5865f2;
                color: #ffffff;
                border: none;
                border-radius: 3px;
                padding: 10px; /* Reduced padding */
                font-size: 14px; /* Reduced font size */
                font-weight: bold;
                min-height: 35px; /* Reduced min height */
            }
            QPushButton:hover {
                background-color: #4752c4;
            }
            QTabWidget::pane {
                border: none;
                background-color: #36393f;
            }
            QTabBar::tab {
                background-color: #2f3136;
                color: #b9bbbe;
                padding: 10px 20px; /* Reduced padding */
                border: none;
                font-size: 14px; /* Reduced font size */
            }
            QTabBar::tab:selected {
                color: #ffffff;
                border-bottom: 2px solid #5865f2;
            }
            /* Style for QSpinBox added previously */
            QSpinBox {
                background-color: #40444b;
                color: #ffffff;
                border: 1px solid #202225;
                border-radius: 3px;
                padding: 8px; /* Adjusted padding */
                font-size: 14px; /* Reduced font size */
                min-height: 30px; /* Adjusted min height */
            }
        """)
        
        self.port = None
        self.user_id = None
        self.visitor_username = None
        main_layout = QVBoxLayout(self) 
        main_layout.setContentsMargins(25, 25, 25, 25) 
        main_layout.setSpacing(15) 
        
        # Port Selection
        port_layout = QHBoxLayout()
        port_label = QLabel("Client Port:")
        port_label.setFont(QFont("Arial", 12))
        self.port_input = QSpinBox()
        self.port_input.setRange(5001, 9999)
        
        # Find an available port and set it as the default
        default_port = self.find_available_port()
        self.port_input.setValue(default_port)
        
        port_layout.addWidget(port_label)
        port_layout.addWidget(self.port_input)
        port_layout.addStretch()
        
        # Add a Find Available Port
        find_port_btn = QPushButton("Find Port")
        find_port_btn.setFixedWidth(80)
        find_port_btn.setStyleSheet("""
            QPushButton {
                background-color: #4f545c;
                font-size: 12px;
                font-weight: normal;
            }
            QPushButton:hover {
                background-color: #5d6269;
            }
        """)
        find_port_btn.clicked.connect(self.find_and_set_available_port)
        port_layout.addWidget(find_port_btn)
        
        main_layout.addLayout(port_layout)
        
        main_layout.addSpacing(10) 

        title = QLabel("Welcome to Hybrid ParadigmChat Chat")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Arial", 18, QFont.Bold))
        main_layout.addWidget(title)
        
        # Create tab widget
        tab_widget = QTabWidget()
        
        # Login
        login_tab = QWidget()
        login_layout = QVBoxLayout()
        login_layout.setSpacing(15)
        login_title = QLabel("Login to your account")
        login_title.setAlignment(Qt.AlignCenter)
        login_title.setFont(QFont("Arial", 14)) 
        login_layout.addWidget(login_title)
        login_layout.addSpacing(15)
        
        self.login_username = QLineEdit()
        self.login_username.setPlaceholderText("Username")
        login_layout.addWidget(self.login_username)
        
        self.login_password = QLineEdit()
        self.login_password.setPlaceholderText("Password")
        self.login_password.setEchoMode(QLineEdit.Password)
        login_layout.addWidget(self.login_password)
        
        login_layout.addSpacing(15) 
        
        login_btn = QPushButton("Login")
        login_btn.clicked.connect(self.login)
        login_layout.addWidget(login_btn)
        
        login_tab.setLayout(login_layout)
        
        # Register
        register_tab = QWidget()
        register_layout = QVBoxLayout()
        register_layout.setSpacing(15) 
        register_title = QLabel("Create a new account")
        register_title.setAlignment(Qt.AlignCenter)
        register_title.setFont(QFont("Arial", 14)) 
        register_layout.addWidget(register_title)
        register_layout.addSpacing(15) 
        
        self.register_username = QLineEdit()
        self.register_username.setPlaceholderText("Username")
        register_layout.addWidget(self.register_username)
        
        self.register_password = QLineEdit()
        self.register_password.setPlaceholderText("Password")
        self.register_password.setEchoMode(QLineEdit.Password)
        register_layout.addWidget(self.register_password)
        
        register_layout.addSpacing(15) 
        
        register_btn = QPushButton("Register")
        register_btn.clicked.connect(self.register)
        register_layout.addWidget(register_btn)
        
        register_tab.setLayout(register_layout)
        
        tab_widget.addTab(login_tab, "Login")
        tab_widget.addTab(register_tab, "Register")
        main_layout.addWidget(tab_widget)
        
        main_layout.addSpacing(10)

        # Visitor mode button
        visitor_btn = QPushButton("Continue as Visitor")
        visitor_btn.clicked.connect(self.visitor_mode)
        visitor_btn.setStyleSheet("""
            QPushButton {
                background-color: #2f3136;
                color: #b9bbbe;
                /* Inherits padding/font from main style */
            }
            QPushButton:hover {
                background-color: #40444b;
            }
        """)
        main_layout.addWidget(visitor_btn)
    
    def find_available_port(self):
        active_ports = set()

        try:
            db = SessionLocal()
            users = db.query(User).all()
            for user in users:
                pass
            db.close()
        except Exception as e:
            logging.error(f"Error querying database for active peers: {str(e)}")

        attempts = 0
        while attempts < 100:
            port = random.randint(5001, 9999)

            if port in active_ports:
                continue

            if self.check_port(port, show_message=False):
                return port
                
            attempts += 1

        return 5001
        
    def find_and_set_available_port(self):
        port = self.find_available_port()
        self.port_input.setValue(port)
        QMessageBox.information(self, "Port Selection", f"Found available port: {port}")
        
    def check_port(self, port: int, show_message: bool = True) -> bool:
        try:
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            test_socket.bind(('0.0.0.0', port))
            test_socket.close()
            return True
        except socket.error as e:
            if e.errno == 98 or e.errno == 10048: 
                logging.error(f"Port {port} is already in use on this machine")
                if show_message:
                    QMessageBox.warning(self, "Error", 
                        f"Port {port} is already in use on this machine.\n"
                        "Please select a different port or click 'Find Port' to automatically find an available port.")
                return False
            else:
                logging.error(f"Error checking port {port}: {str(e)}")
                return False
        except Exception as e:
            logging.error(f"Unexpected error checking port {port}: {str(e)}")
            return False

    def login(self):
        # Kiểm tra port
        port = self.port_input.value()
        if not self.check_port(port):
            return

        # Kiểm tra thông tin login
        username = self.login_username.text()
        password = self.login_password.text()
        
        if not username or not password:
            QMessageBox.warning(self, "Error", "Please enter both username and password")
            return
            
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == username).first()
            if user and user.password == password:
                self.user_id = user.id
                self.port = port
                self.visitor_username = None
                QMessageBox.information(self, "Login Successful", f"Welcome back, {user.username}!")
                self.accept()
            else:
                QMessageBox.warning(self, "Error", "Invalid username or password")
        except Exception as e:
            logging.error(f"Login error: {str(e)}")
            QMessageBox.critical(self, "Error", "An error occurred during login")
        finally:
            db.close()
            
    def register(self):
        # Kiểm tra port
        port = self.port_input.value()
        if not self.check_port(port):
            return

        # Kiểm tra thông tin đăng ký
        username = self.register_username.text()
        password = self.register_password.text()
        
        if not username or not password:
            QMessageBox.warning(self, "Error", "Please enter both username and password")
            return
            
        if len(username) < 3:
            QMessageBox.warning(self, "Error", "Username must be at least 3 characters long")
            return
            
        if len(password) < 6:
            QMessageBox.warning(self, "Error", "Password must be at least 6 characters long")
            return
            
        db = SessionLocal()
        try:
            existing_user = db.query(User).filter(User.username == username).first()
            if existing_user:
                QMessageBox.warning(self, "Error", "Username already exists")
                return
                
            new_user = User(
                username=username,
                password=password,
                status="offline",
                role="user"
            )
            db.add(new_user)
            db.commit()
            
            self.user_id = new_user.id
            self.port = port
            self.visitor_username = None
            QMessageBox.information(self, "Registration Successful", f"Account created for {username}! You are now logged in.")
            self.accept()
            
        except Exception as e:
            logging.error(f"Registration error: {str(e)}")
            QMessageBox.critical(self, "Error", "An error occurred during registration")
            db.rollback()
        finally:
            db.close()
            
    def visitor_mode(self):
        port = self.port_input.value()
        if not self.check_port(port):
            return

        username, ok = QInputDialog.getText(self, "Visitor Mode", "Enter your visitor username:")
        if ok and username:
            if len(username.strip()) >= 3:
                self.user_id = None
                self.visitor_username = username.strip()
                self.port = port
                self.accept()
            else:
                QMessageBox.warning(self, "Error", "Visitor username must be at least 3 characters long.")
        elif ok and not username:
            QMessageBox.warning(self, "Error", "Visitor username cannot be empty.") 