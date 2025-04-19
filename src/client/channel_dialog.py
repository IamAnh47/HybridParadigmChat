from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                           QLineEdit, QPushButton, QListWidget, QMessageBox,
                           QInputDialog, QListWidgetItem, QCheckBox, QMenu,
                           QTabWidget, QWidget)
from PySide6.QtCore import Qt
from src.database.models import Channel, ChannelMembership, User
from src.database.config import SessionLocal
import logging

class ChannelDialog(QDialog):
    def __init__(self, current_user_id: int, parent=None):
        super().__init__(parent)
        self.current_user_id = current_user_id
        self.setWindowTitle("Search and Join Channel")
        self.setMinimumWidth(400)
        self.setStyleSheet("""
            QDialog {
                background-color: #36393f;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
            QLineEdit {
                background-color: #40444b;
                border: none;
                padding: 8px;
                color: #ffffff;
                border-radius: 3px;
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
            QListWidget {
                background-color: #2f3136;
                border: none;
                padding: 5px;
                color: #ffffff;
            }
            QListWidget::item {
                padding: 5px;
                border-radius: 3px;
            }
            QListWidget::item:selected {
                background-color: #40444b;
            }
            QCheckBox {
                color: #ffffff;
            }
        """)
        
        self.init_ui()
        self.load_channels()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Search
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search channels...")
        self.search_input.textChanged.connect(self.search_channels)
        search_layout.addWidget(self.search_input)
        
        # Create channel
        self.create_btn = QPushButton("Create")
        self.create_btn.clicked.connect(self.create_channel)
        search_layout.addWidget(self.create_btn)
        
        layout.addLayout(search_layout)
        
        # Channel list
        self.channel_list = QListWidget()
        self.channel_list.itemDoubleClicked.connect(self.join_channel)
        self.channel_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.channel_list.customContextMenuRequested.connect(self.show_context_menu)
        self.channel_list.setStyleSheet("""
            QListWidget {
                background-color: #2f3136;
                border: none;
                padding: 5px;
                color: #ffffff;
            }
            QListWidget::item {
                padding: 5px;
                border-radius: 3px;
            }
            QListWidget::item:selected {
                background-color: #40444b;
            }
            QListWidget::item:hover {
                background-color: #40444b;
            }
        """)
        layout.addWidget(self.channel_list)
        
        # Join
        self.join_btn = QPushButton("Join")
        self.join_btn.clicked.connect(self.join_selected_channel)
        layout.addWidget(self.join_btn)
        
        self.setLayout(layout)
        
    def load_channels(self):
        """Tải list channel có thể tham gia"""
        self.channel_list.clear()
        db = SessionLocal()
        try:
            if self.current_user_id:
                channels = db.query(Channel).filter(
                    ~Channel.members.any(ChannelMembership.user_id == self.current_user_id)
                ).all()
                
                for channel in channels:
                    # Widget channel
                    channel_widget = QWidget()
                    channel_layout = QHBoxLayout()
                    channel_layout.setContentsMargins(5, 5, 5, 5)
                    
                    # Icon và name channel
                    icon = "🔒" if channel.is_private else "#"
                    name_label = QLabel(f"{icon} {channel.name}")
                    name_label.setStyleSheet("color: #ffffff;")
                    channel_layout.addWidget(name_label)
                    
                    # Quyền dành cho user tạo channel
                    if channel.owner_id == self.current_user_id:
                        edit_btn = QPushButton("⚙️")
                        edit_btn.setFixedSize(30, 30)
                        edit_btn.setStyleSheet("""
                            QPushButton {
                                background-color: #5865f2;
                                border: none;
                                border-radius: 15px;
                                color: #ffffff;
                                font-size: 16px;
                            }
                            QPushButton:hover {
                                background-color: #4752c4;
                            }
                        """)
                        edit_btn.clicked.connect(lambda checked, cid=channel.id: self.edit_channel(cid))
                        channel_layout.addWidget(edit_btn)
                    
                    channel_widget.setLayout(channel_layout)
                    
                    item = QListWidgetItem()
                    item.setSizeHint(channel_widget.sizeHint())
                    item.setData(Qt.ItemDataRole.UserRole, channel.id)
                    self.channel_list.addItem(item)
                    self.channel_list.setItemWidget(item, channel_widget)
            else:
                channels = db.query(Channel).filter(
                    Channel.allow_visitors == True
                ).all()
                
                for channel in channels:
                    channel_widget = QWidget()
                    channel_layout = QHBoxLayout()
                    channel_layout.setContentsMargins(5, 5, 5, 5)
                    
                    icon = "🔒" if channel.is_private else "#"
                    name_label = QLabel(f"{icon} {channel.name}")
                    name_label.setStyleSheet("color: #ffffff;")
                    channel_layout.addWidget(name_label)
                    
                    channel_widget.setLayout(channel_layout)
                    
                    item = QListWidgetItem()
                    item.setSizeHint(channel_widget.sizeHint())
                    item.setData(Qt.ItemDataRole.UserRole, channel.id)
                    self.channel_list.addItem(item)
                    self.channel_list.setItemWidget(item, channel_widget)
                    
        except Exception as e:
            logging.error(f"Error loading channels: {str(e)}")
            QMessageBox.critical(self, "Error", "Could not load channels")
        finally:
            db.close()
            
    def search_channels(self):
        search_text = self.search_input.text().lower()
        for i in range(self.channel_list.count()):
            item = self.channel_list.item(i)
            item.setHidden(search_text not in item.text().lower())
            
    def create_channel(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Create Channel")
        dialog.setStyleSheet(self.styleSheet())
        
        layout = QVBoxLayout()
        
        # Channel name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Channel Name:"))
        name_input = QLineEdit()
        name_layout.addWidget(name_input)
        layout.addLayout(name_layout)
        
        # Channel settings
        private_checkbox = QCheckBox("Private Channel")
        allow_visitors_checkbox = QCheckBox("Allow Visitors")
        allow_visitor_messages_checkbox = QCheckBox("Allow Visitor Messages")
        allow_visitor_messages_checkbox.setEnabled(False)  # Disabled by default
        
        # Connect signals
        allow_visitors_checkbox.stateChanged.connect(
            lambda state: allow_visitor_messages_checkbox.setEnabled(state == Qt.CheckState.Checked)
        )
        
        layout.addWidget(private_checkbox)
        layout.addWidget(allow_visitors_checkbox)
        layout.addWidget(allow_visitor_messages_checkbox)
        
        # Button create
        button_layout = QHBoxLayout()
        create_btn = QPushButton("Create")
        cancel_btn = QPushButton("Cancel")
        
        create_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        
        button_layout.addWidget(create_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name = name_input.text().strip()
            if not name:
                QMessageBox.warning(self, "Error", "Please enter a channel name")
                return
                
            db = SessionLocal()
            try:
                # Check
                existing = db.query(Channel).filter(Channel.name == name).first()
                if existing:
                    QMessageBox.warning(self, "Error", "Channel name already exists")
                    return
                    
                # Tạo channel mới
                new_channel = Channel(
                    name=name,
                    owner_id=self.current_user_id,
                    is_private=private_checkbox.isChecked(),
                    allow_visitors=allow_visitors_checkbox.isChecked(),
                    allow_visitor_messages=allow_visitor_messages_checkbox.isChecked()
                )
                db.add(new_channel)
                db.commit()
                
                # Add user -> channel
                membership = ChannelMembership(
                    channel_id=new_channel.id,
                    user_id=self.current_user_id
                )
                db.add(membership)
                db.commit()
                
                QMessageBox.information(self, "Success", f"Channel '{name}' created!")
                self.accept()
                
            except Exception as e:
                logging.error(f"Error creating channel: {str(e)}")
                QMessageBox.critical(self, "Error", "Could not create channel")
                db.rollback()
            finally:
                db.close()
                
    def join_selected_channel(self):
        selected = self.channel_list.currentItem()
        if selected:
            self.join_channel(selected)
            
    def join_channel(self, item):
        channel_id = item.data(Qt.ItemDataRole.UserRole)
        db = SessionLocal()
        try:
            channel = db.query(Channel).get(channel_id)
            if not channel:
                QMessageBox.warning(self, "Error", "Channel not found")
                return

            existing = db.query(ChannelMembership).filter(
                ChannelMembership.channel_id == channel_id,
                ChannelMembership.user_id == self.current_user_id
            ).first()
            
            if existing:
                QMessageBox.warning(self, "Error", "You are already a member of this channel")
                return

            membership = ChannelMembership(
                channel_id=channel_id,
                user_id=self.current_user_id
            )
            db.add(membership)
            db.commit()
            
            QMessageBox.information(self, "Success", "Joined channel successfully!")
            self.accept()
            
        except Exception as e:
            logging.error(f"Error joining channel: {str(e)}")
            QMessageBox.critical(self, "Error", "Could not join channel")
            db.rollback()
        finally:
            db.close()
            
    def edit_channel(self, channel_id: int):
        db = SessionLocal()
        try:
            channel = db.query(Channel).get(channel_id)
            if not channel:
                QMessageBox.warning(self, "Error", "Channel not found")
                return
                
            if channel.owner_id != self.current_user_id:
                QMessageBox.warning(self, "Error", "Only channel owner can edit channel settings")
                return

            dialog = QDialog(self)
            dialog.setWindowTitle("Edit Channel Settings")
            dialog.setMinimumWidth(400)
            dialog.setStyleSheet("""
                QDialog {
                    background-color: #36393f;
                    color: #ffffff;
                }
                QLabel {
                    color: #ffffff;
                }
                QLineEdit {
                    background-color: #40444b;
                    border: none;
                    padding: 8px;
                    color: #ffffff;
                    border-radius: 3px;
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
                QListWidget {
                    background-color: #2f3136;
                    border: none;
                    padding: 5px;
                    color: #ffffff;
                }
                QListWidget::item {
                    padding: 5px;
                    border-radius: 3px;
                }
                QListWidget::item:selected {
                    background-color: #40444b;
                }
                QCheckBox {
                    color: #ffffff;
                }
                QTabWidget::pane {
                    border: none;
                    background-color: #2f3136;
                }
                QTabBar::tab {
                    background-color: #2f3136;
                    color: #ffffff;
                    padding: 8px;
                    border: none;
                }
                QTabBar::tab:selected {
                    background-color: #40444b;
                }
                QWidget#settings_tab {
                    background-color: #2f3136;
                }
                QWidget#members_tab {
                    background-color: #2f3136;
                }
            """)
            
            layout = QVBoxLayout()
            
            # Tab widget
            tab_widget = QTabWidget()
            
            # Settings tab
            settings_tab = QWidget()
            settings_tab.setObjectName("settings_tab")
            settings_layout = QVBoxLayout()
            
            # Channel name
            name_layout = QHBoxLayout()
            name_layout.addWidget(QLabel("Channel Name:"))
            name_input = QLineEdit(channel.name)
            name_layout.addWidget(name_input)
            settings_layout.addLayout(name_layout)
            
            # Channel settings
            private_checkbox = QCheckBox("Private Channel")
            private_checkbox.setChecked(channel.is_private)
            
            allow_visitors_checkbox = QCheckBox("Allow Visitors")
            allow_visitors_checkbox.setChecked(channel.allow_visitors)
            
            allow_visitor_messages_checkbox = QCheckBox("Allow Visitor Messages")
            allow_visitor_messages_checkbox.setChecked(channel.allow_visitor_messages)
            allow_visitor_messages_checkbox.setEnabled(channel.allow_visitors)
            
            # Connect signals
            allow_visitors_checkbox.stateChanged.connect(
                lambda state: allow_visitor_messages_checkbox.setEnabled(state == Qt.CheckState.Checked)
            )
            
            settings_layout.addWidget(private_checkbox)
            settings_layout.addWidget(allow_visitors_checkbox)
            settings_layout.addWidget(allow_visitor_messages_checkbox)
            settings_tab.setLayout(settings_layout)
            
            # Members tab
            members_tab = QWidget()
            members_tab.setObjectName("members_tab")
            members_layout = QVBoxLayout()
            
            # Members list
            members_list = QListWidget()
            members = db.query(User).join(ChannelMembership).filter(
                ChannelMembership.channel_id == channel_id
            ).all()
            
            for member in members:
                role = "Owner" if member.id == channel.owner_id else "Member"
                item = QListWidgetItem(f"{member.username} ({role})")
                item.setData(Qt.ItemDataRole.UserRole, member.id)
                members_list.addItem(item)
                
            members_layout.addWidget(members_list)
            
            # Remove member button
            remove_btn = QPushButton("Remove Member")
            remove_btn.clicked.connect(lambda: self.remove_member(channel_id, members_list))
            members_layout.addWidget(remove_btn)
            
            members_tab.setLayout(members_layout)
            
            # Add tabs
            tab_widget.addTab(settings_tab, "Settings")
            tab_widget.addTab(members_tab, "Members")
            layout.addWidget(tab_widget)
            
            # Buttons
            button_layout = QHBoxLayout()
            save_btn = QPushButton("Save")
            cancel_btn = QPushButton("Cancel")
            
            save_btn.clicked.connect(dialog.accept)
            cancel_btn.clicked.connect(dialog.reject)
            
            button_layout.addWidget(save_btn)
            button_layout.addWidget(cancel_btn)
            layout.addLayout(button_layout)
            
            dialog.setLayout(layout)
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                channel.name = name_input.text().strip()
                channel.is_private = private_checkbox.isChecked()
                channel.allow_visitors = allow_visitors_checkbox.isChecked()
                channel.allow_visitor_messages = allow_visitor_messages_checkbox.isChecked()
                
                db.commit()
                QMessageBox.information(self, "Success", "Channel settings updated!")
                self.load_channels()
                
        except Exception as e:
            logging.error(f"Error editing channel: {str(e)}")
            QMessageBox.critical(self, "Error", "Could not update channel settings")
            db.rollback()
        finally:
            db.close()
            
    def remove_member(self, channel_id: int, members_list: QListWidget):
        """Xóa thành viên khỏi channel"""
        selected = members_list.currentItem()
        if not selected:
            QMessageBox.warning(self, "Error", "Please select a member to remove")
            return
            
        member_id = selected.data(Qt.ItemDataRole.UserRole)
        db = SessionLocal()
        try:
            channel = db.query(Channel).get(channel_id)
            if member_id == channel.owner_id:
                QMessageBox.warning(self, "Error", "Cannot remove channel owner")
                return
                
            # Remove member
            membership = db.query(ChannelMembership).filter(
                ChannelMembership.channel_id == channel_id,
                ChannelMembership.user_id == member_id
            ).first()
            
            if membership:
                db.delete(membership)
                db.commit()

                members_list.takeItem(members_list.row(selected))
                QMessageBox.information(self, "Success", "Member removed successfully")
            else:
                QMessageBox.warning(self, "Error", "Member not found in channel")
                
        except Exception as e:
            logging.error(f"Error removing member: {str(e)}")
            QMessageBox.critical(self, "Error", "Could not remove member")
            db.rollback()
        finally:
            db.close()
            
    def show_context_menu(self, pos):
        """Hiển thị menu chuột phải"""
        item = self.channel_list.itemAt(pos)
        if item:
            channel_id = item.data(Qt.ItemDataRole.UserRole)
            db = SessionLocal()
            try:
                channel = db.query(Channel).get(channel_id)
                if channel and channel.owner_id == self.current_user_id:
                    menu = QMenu(self)
                    edit_action = menu.addAction("Edit Channel")
                    action = menu.exec(self.channel_list.mapToGlobal(pos))
                    if action == edit_action:
                        self.edit_channel(channel_id)
            finally:
                db.close() 