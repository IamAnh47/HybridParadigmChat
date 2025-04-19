from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QMessageBox, QTabWidget,
                             QWidget, QCheckBox, QComboBox, QSpinBox, QListWidget,
                             QListWidgetItem, QGroupBox)
from PySide6.QtCore import Qt
from src.database.models import User, Friendship, Channel, ChannelMembership
from src.database.config import SessionLocal
from src.client.settings_handler import SettingsHandler
import logging

class SettingsDialog(QDialog):
    def __init__(self, user_id, parent=None):
        super().__init__(parent)
        self.user_id = user_id
        self.setWindowTitle("User Settings")
        self.setFixedSize(500, 400)
        self.settings = SettingsHandler()
        
        # Set dark style
        self.setStyleSheet("""
            QDialog {
                background-color: #36393f;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
                font-size: 13px;
            }
            QLineEdit, QComboBox, QSpinBox {
                background-color: #40444b;
                color: #ffffff;
                border: 1px solid #202225;
                border-radius: 3px;
                padding: 8px;
                selection-background-color: #5865f2;
            }
            QPushButton {
                background-color: #5865f2;
                color: #ffffff;
                border: none;
                padding: 8px;
                border-radius: 3px;
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
                color: #ffffff;
                padding: 8px;
                margin-right: 2px;
                border-top-left-radius: 3px;
                border-top-right-radius: 3px;
            }
            QTabBar::tab:selected {
                background-color: #36393f;
                border-bottom: 2px solid #5865f2;
            }
            QCheckBox {
                color: #ffffff;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #202225;
                border-radius: 3px;
                background-color: #40444b;
            }
            QCheckBox::indicator:checked {
                background-color: #5865f2;
            }
        """)
        
        self.init_ui()
        self.load_settings()
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # Create tab widget
        tabs = QTabWidget()
        
        # Profile tab
        profile_tab = QWidget()
        profile_layout = QVBoxLayout(profile_tab)
        
        # Username
        username_label = QLabel("Username")
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Enter your username")
        profile_layout.addWidget(username_label)
        profile_layout.addWidget(self.username_edit)
        
        # Password
        password_label = QLabel("Password")
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("Enter your password")
        self.password_edit.setEchoMode(QLineEdit.Password)
        profile_layout.addWidget(password_label)
        profile_layout.addWidget(self.password_edit)
        
        # Confirm Password
        confirm_password_label = QLabel("Confirm Password")
        self.confirm_password_edit = QLineEdit()
        self.confirm_password_edit.setPlaceholderText("Confirm your password")
        self.confirm_password_edit.setEchoMode(QLineEdit.Password)
        profile_layout.addWidget(confirm_password_label)
        profile_layout.addWidget(self.confirm_password_edit)
        
        tabs.addTab(profile_tab, "Profile")
        
        main_layout.addWidget(tabs)
        
        # Buttons
        button_layout = QHBoxLayout()
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_settings)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        main_layout.addLayout(button_layout)
        
    def load_settings(self):
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == self.user_id).first()
            if user:
                self.username_edit.setText(user.username)
        finally:
            db.close()

    def save_settings(self):
        username = self.username_edit.text()
        password = self.password_edit.text()
        confirm_password = self.confirm_password_edit.text()
        
        if not username:
            QMessageBox.warning(self, "Error", "Username is required")
            return
            
        if password and password != confirm_password:
            QMessageBox.warning(self, "Error", "Passwords do not match")
            return
            
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == self.user_id).first()
            if user:
                # Check if username already exists
                existing_user = db.query(User).filter(User.username == username).first()
                if existing_user and existing_user.id != self.user_id:
                    QMessageBox.warning(self, "Error", "Username already exists")
                    return
                    
                # Update user info
                user.username = username
                if password:
                    user.password = password
                
                db.commit()
                QMessageBox.information(self, "Success", "Settings saved successfully")
                self.accept()

        except Exception as e:
            db.rollback()
            QMessageBox.critical(self, "Error", f"Failed to save settings: {str(e)}")
        finally:
            db.close()
            
    def hash_password(self, password):
        import hashlib
        return hashlib.sha256(password.encode()).hexdigest() 