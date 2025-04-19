from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QListWidget, QListWidgetItem
from PySide6.QtCore import Qt
from src.database.models import User, FriendRequest, Friendship
from src.database.config import SessionLocal
import logging
from sqlalchemy import or_, and_

class FriendDialog(QDialog):
    def __init__(self, current_user_id, parent=None):
        super().__init__(parent)
        self.current_user_id = current_user_id
        self.setWindowTitle("Add Friend")
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
                padding: 10px;
                font-size: 14px;
            }
            QPushButton {
                background-color: #5865f2;
                color: #ffffff;
                border: none;
                border-radius: 3px;
                padding: 10px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #4752c4;
            }
            QListWidget {
                background-color: #2f3136;
                color: #ffffff;
                border: none;
                padding: 5px;
            }
            QListWidget::item {
                padding: 5px;
                border-radius: 3px;
            }
            QListWidget::item:selected {
                background-color: #40444b;
            }
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search for users...")
        self.search_input.textChanged.connect(self.search_users)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)
        self.results_list = QListWidget()
        self.results_list.itemClicked.connect(self.user_selected)
        layout.addWidget(self.results_list)
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        button_layout = QHBoxLayout()
        self.add_button = QPushButton("Send Friend Request")
        self.add_button.clicked.connect(self.send_friend_request)
        self.add_button.setEnabled(False)
        button_layout.addWidget(self.add_button)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

    def search_users(self):
        query = self.search_input.text().strip()
        if not query:
            self.results_list.clear()
            self.status_label.setText("")
            return
        db = SessionLocal()
        try:
            users = db.query(User).filter(
                User.username.ilike(f"%{query}%"),
                User.id != self.current_user_id
            ).all()
            self.results_list.clear()
            if not users:
                self.status_label.setText("No users found")
                return
            self.status_label.setText(f"Found {len(users)} users")
            for user in users:
                is_friend = db.query(Friendship).filter(
                    or_(
                        and_(Friendship.user_id == self.current_user_id, Friendship.friend_id == user.id),
                        and_(Friendship.user_id == user.id, Friendship.friend_id == self.current_user_id)
                    )
                ).first()
                has_request = db.query(FriendRequest).filter(
                    FriendRequest.sender_id == self.current_user_id,
                    FriendRequest.receiver_id == user.id,
                    FriendRequest.status == "pending"
                ).first()
                status = ""
                if is_friend:
                    status = " (Already friends)"
                elif has_request:
                    status = " (Request sent)"
                item = QListWidgetItem(f"{user.username}{status}")
                item.setData(Qt.ItemDataRole.UserRole, user.id)
                self.results_list.addItem(item)
        except Exception as e:
            logging.error(f"Error searching users: {str(e)}")
            self.status_label.setText("Error searching users")
        finally:
            db.close()

    def user_selected(self, item):
        user_id = item.data(Qt.ItemDataRole.UserRole)
        if user_id:
            self.selected_user_id = user_id
            self.add_button.setEnabled(True)

    def send_friend_request(self):
        if not hasattr(self, 'selected_user_id'):
            return
        db = SessionLocal()
        try:
            existing_friendship = db.query(Friendship).filter(
                or_(
                    and_(Friendship.user_id == self.current_user_id, Friendship.friend_id == self.selected_user_id),
                    and_(Friendship.user_id == self.selected_user_id, Friendship.friend_id == self.current_user_id)
                )
            ).first()
            if existing_friendship:
                QMessageBox.warning(self, "Error", "You are already friends with this user")
                return
            existing_request = db.query(FriendRequest).filter(
                FriendRequest.sender_id == self.current_user_id,
                FriendRequest.receiver_id == self.selected_user_id,
                FriendRequest.status == "pending"
            ).first()
            if existing_request:
                QMessageBox.warning(self, "Error", "You have already sent a friend request to this user")
                return
            new_request = FriendRequest(
                sender_id=self.current_user_id,
                receiver_id=self.selected_user_id,
                status="pending"
            )
            db.add(new_request)
            db.commit()
            QMessageBox.information(self, "Success", "Friend request sent!")
            self.accept()
        except Exception as e:
            logging.error(f"Error sending friend request: {str(e)}")
            QMessageBox.critical(self, "Error", "Could not send friend request")
            db.rollback()
        finally:
            db.close()
