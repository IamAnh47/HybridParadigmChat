from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QListWidget, QTextEdit, QTextBrowser,
                             QLineEdit, QStackedWidget, QMenu, QSystemTrayIcon,
                             QMessageBox, QInputDialog, QFrame, QDialog, QListWidgetItem,
                             QTabWidget, QStyle, QCheckBox)
from PySide6.QtCore import Qt, QSize, Signal, QTimer, QUrl, QThread, QProcess
from PySide6.QtGui import QIcon, QAction, QFont, QDesktopServices, QCursor
from src.client.auth_dialog import AuthDialog
from src.client.channel_dialog import ChannelDialog
from src.client.friend_dialog import FriendDialog
from src.client.settings_dialog import SettingsDialog
from src.database.models import User, Channel, Message, FriendRequest, Friendship, ChannelMembership
from src.database.config import SessionLocal
import logging
from sqlalchemy import or_, and_
from sqlalchemy.orm import joinedload, Session
from src.client.realtime_handler import RealtimeHandler
from functools import partial
from PySide6.QtWidgets import QApplication
import os
from src.client.settings_handler import SettingsHandler
from datetime import datetime
import shutil
from PIL import Image, ImageDraw, ImageFont
import logging
import sys
import re
import subprocess
import signal
from src.client.system_logger import SystemLogger
from src.client.channel_host import ChannelHost
from src.client.media_transfer import MediaTransferNode
import socket
import random

class DirectWriteFilter:
    def __init__(self, original_stream):
        self.original_stream = original_stream
        
    def write(self, text):
        if "DirectWrite:" not in text and "OpenType support missing" not in text:
            self.original_stream.write(text)
            
    def flush(self):
        self.original_stream.flush()

sys.stdout = DirectWriteFilter(sys.stdout)
sys.stderr = DirectWriteFilter(sys.stderr)

class VideoOpenerThread(QThread):
    active_processes = []
    
    def __init__(self, url):
        super().__init__()
        self.url = url
        self.process = None
        self.settings = SettingsHandler()
        
    def run(self):
        try:
            performance_settings = self.settings.get_performance_settings()
            use_external = performance_settings.get("use_external_player", False)
            reduce_background = performance_settings.get("reduce_background", False)
            
            if reduce_background:
                import gc
                gc.collect()
            
            if isinstance(self.url, QUrl) and self.url.scheme() == "file":
                path = self.url.toLocalFile()
                path = path.replace("%5C", "\\").replace("%20", " ")
                if not os.path.exists(path):
                    logging.error(f"Video file not found: {path}")
                    return
                
                VideoOpenerThread.cleanup_processes()
                
                if use_external and os.name == 'nt':
                    try:
                        mpv_path = os.path.join(os.getcwd(), "tools", "mpv.exe")
                        if os.path.exists(mpv_path):
                            quality = performance_settings.get("video_quality", "Balanced")
                            if quality == "Low Quality (Faster)":
                                args = [mpv_path, "--vo=gpu", "--hwdec=auto", "--scale=bilinear", path]
                            elif quality == "Balanced":
                                args = [mpv_path, "--vo=gpu", "--hwdec=auto", path]
                            else:
                                args = [mpv_path, path]
                                
                            self.process = subprocess.Popen(
                                args, 
                                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS
                            )
                            VideoOpenerThread.active_processes.append(self.process)
                            return
                    except Exception as e:
                        logging.error(f"Error using lightweight player: {str(e)}")
                
                if os.name == 'nt':
                    os.startfile(path)
                else:
                    try:
                        if sys.platform == 'darwin':
                            self.process = subprocess.Popen(['open', path])
                        else:
                            self.process = subprocess.Popen(['xdg-open', path])
                        if self.process:
                            VideoOpenerThread.active_processes.append(self.process)
                    except Exception as e:
                        logging.error(f"Error using subprocess: {str(e)}")
                        QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            else:
                QDesktopServices.openUrl(self.url)
                
        except Exception as e:
            logging.error(f"Error opening video in thread: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
    
    @classmethod
    def cleanup_processes(cls):
        for process in cls.active_processes[:]:
            if process.poll() is not None:
                cls.active_processes.remove(process)
    
    @classmethod
    def terminate_all(cls):
        for process in cls.active_processes[:]:
            try:
                process.terminate()
                cls.active_processes.remove(process)
            except Exception as e:
                logging.error(f"Error terminating process: {str(e)}")
                try:
                    if os.name == 'nt':
                        process.kill()
                    else:
                        os.kill(process.pid, signal.SIGKILL)
                except:
                    pass
                cls.active_processes.remove(process)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hybrid ParadigmChat Chat")
        self.setMinimumSize(1200, 800)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #36393f;
            }
            QWidget {
                color: #ffffff;
            }
            QListWidget {
                background-color: #2f3136;
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
            QTextEdit {
                background-color: #40444b;
                border: none;
                padding: 10px;
                color: #ffffff;
            }
            QLineEdit {
                background-color: #40444b;
                border: none;
                padding: 10px;
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
            QMenu {
                background-color: #2f3136;
                color: #ffffff;
                border: 1px solid #202225;
            }
            QMenu::item:selected {
                background-color: #40444b;
            }
        """)
        
        self.current_user_id = None
        self.port = None
        self.visitor_username = None
        self.current_channel = None
        self.current_friend = None
        self.settings_menu = None
        self.channel_list = None
        self.friend_list = None
        self.chat_area = None
        self.channel_name_label = None
        self.message_input = None
        self.pending_list = None
        self.realtime_handler = None
        
        self.should_auto_scroll = True
        self.last_scroll_position = 0
        
        self.unread_channel_messages = {}
        self.unread_friend_messages = {}
        
        self.paused_updates_channel = {} 
        self.paused_updates_friend = {} 
        
        self.system_logger = None
        self.channel_host = None
        self.base_port = self.find_available_base_port()
        
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.auto_update_ui)
        self.update_timer.start(1000)
        
        self.init_ui_structure()
        
        if not self.show_auth_dialog():
            QTimer.singleShot(0, self.close)
            return
        
        self.show()
        
    def init_ui_structure(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        left_sidebar = QWidget()
        left_sidebar.setFixedWidth(240)
        left_sidebar.setStyleSheet("background-color: #2f3136;")
        left_layout = QVBoxLayout(left_sidebar)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(10)
        
        channel_title = QLabel("Channels")
        channel_title.setFont(QFont("Arial", 12, QFont.Bold))
        left_layout.addWidget(channel_title)
        self.channel_list = QListWidget()
        self.channel_list.itemClicked.connect(self.channel_selected)
        left_layout.addWidget(self.channel_list)
        add_channel_btn = QPushButton("Create/Join Channel", objectName="createJoinChannelButton")
        add_channel_btn.clicked.connect(self.create_or_join_channel)
        left_layout.addWidget(add_channel_btn)
        
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        left_layout.addWidget(separator)
        
        friend_title = QLabel("Friends")
        friend_title.setFont(QFont("Arial", 12, QFont.Bold))
        left_layout.addWidget(friend_title)
        
        friend_tabs = QTabWidget()
        friend_tabs.setStyleSheet("""
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
        """)
        
        self.friend_list = QListWidget()
        self.friend_list.itemClicked.connect(self.friend_selected)
        friend_tabs.addTab(self.friend_list, "Friends")
        
        self.pending_list = QListWidget()
        self.pending_list.itemClicked.connect(self.pending_friend_selected)
        friend_tabs.addTab(self.pending_list, "Pending")
        
        left_layout.addWidget(friend_tabs)
        
        add_friend_btn = QPushButton("Add Friend", objectName="addFriendButton")
        add_friend_btn.clicked.connect(self.add_friend)
        left_layout.addWidget(add_friend_btn)
        
        left_layout.addStretch()
        main_layout.addWidget(left_sidebar)
        
        main_content = QWidget()
        main_content.setStyleSheet("background-color: #36393f;")
        main_content_layout = QVBoxLayout(main_content)
        main_content_layout.setContentsMargins(0, 0, 0, 0)
        main_content_layout.setSpacing(0)
        
        channel_info = QWidget()
        channel_info.setFixedHeight(50)
        channel_info.setStyleSheet("background-color: #2f3136; padding-left: 10px; padding-right: 10px;")
        channel_info_layout = QHBoxLayout(channel_info)
        channel_info_layout.setObjectName("channelInfoLayout")
        
        self.channel_name_label = QLabel("Select a channel or friend")
        self.channel_name_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        channel_info_layout.addWidget(self.channel_name_label)
        
        self.pause_updates_checkbox = QCheckBox("View history")
        self.pause_updates_checkbox.setStyleSheet("""
            QCheckBox {
                color: #ffffff;
                margin-left: 10px;
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
        self.pause_updates_checkbox.stateChanged.connect(self.toggle_updates)
        self.pause_updates_checkbox.setVisible(False) 
        channel_info_layout.addWidget(self.pause_updates_checkbox)
        
        channel_info_layout.addStretch()
        
        main_content_layout.addWidget(channel_info)
        
        self.chat_area = QTextBrowser()
        self.chat_area.setReadOnly(True)
        self.chat_area.setStyleSheet("background-color: #40444b; border: none; padding: 10px; color: #dcddde;")
        self.chat_area.setOpenExternalLinks(True)
        self.chat_area.anchorClicked.connect(self.handle_link_clicked)
        self.chat_area.verticalScrollBar().valueChanged.connect(self.scroll_position_changed)
        
        main_content_layout.addWidget(self.chat_area)
        
        message_input_container = QWidget()
        message_input_container.setStyleSheet("background-color: #36393f; padding: 10px;")
        message_input_layout_outer = QVBoxLayout(message_input_container)
        message_input_layout_outer.setContentsMargins(0,0,0,0)
        
        message_input_layout = QHBoxLayout()
        message_input_layout.setContentsMargins(0,0,0,0)
        message_input_layout.setSpacing(5)
        
        attach_image_btn = QPushButton()
        attach_image_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogStart))
        attach_image_btn.setToolTip("Attach Image")
        attach_image_btn.setFixedSize(32, 32)
        attach_image_btn.setStyleSheet("""
            QPushButton {
                background-color: #5865f2;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #4752c4;
            }
        """)
        attach_image_btn.clicked.connect(self.attach_image)
        
        attach_video_btn = QPushButton()
        attach_video_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogListView))
        attach_video_btn.setToolTip("Attach Video")
        attach_video_btn.setFixedSize(32, 32)
        attach_video_btn.setStyleSheet("""
            QPushButton {
                background-color: #5865f2;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #4752c4;
            }
        """)
        attach_video_btn.clicked.connect(self.attach_video)
        
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Type a message...")
        self.message_input.returnPressed.connect(self.send_message)
        self.message_input.setStyleSheet("""
            QLineEdit {
                background-color: #40444b;
                border: none;
                padding: 10px;
                color: #dcddde;
                border-radius: 5px;
                font-size: 14px;
            }
        """)
        
        message_input_layout.addWidget(attach_image_btn)
        message_input_layout.addWidget(attach_video_btn)
        message_input_layout.addWidget(self.message_input)
        
        message_input_layout_outer.addLayout(message_input_layout)
        
        self.selected_media_label = QLabel("")
        self.selected_media_label.setStyleSheet("color: #dcddde; padding-left: 5px;")
        self.selected_media_label.setVisible(False)
        message_input_layout_outer.addWidget(self.selected_media_label)
        
        self.selected_media_path = None
        self.selected_media_type = None
        
        main_content_layout.addWidget(message_input_container)
        main_layout.addWidget(main_content)
        
        self.create_menu_bar()
        self.create_tray_icon()
        
    def create_menu_bar(self):
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: #2f3136;
                color: #ffffff;
            }
            QMenuBar::item:selected {
                background-color: #40444b;
            }
        """)
        
        file_menu = menubar.addMenu("File")
        
        create_channel_action = QAction("Create/Join Channel", self)
        create_channel_action.triggered.connect(self.create_or_join_channel)
        file_menu.addAction(create_channel_action)
        
        add_friend_action = QAction("Add Friend", self)
        add_friend_action.triggered.connect(self.add_friend)
        file_menu.addAction(add_friend_action)
        
        file_menu.addSeparator()
        
        network_info_action = QAction("Network Info", self)
        network_info_action.triggered.connect(self.show_network_info)
        file_menu.addAction(network_info_action)
        
        file_menu.addSeparator()
        
        logout_action = QAction("Logout", self)
        logout_action.triggered.connect(self.logout)
        file_menu.addAction(logout_action)
        
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_application)
        file_menu.addAction(quit_action)
        
        self.settings_menu = menubar.addMenu("Settings")
        
        user_settings_action = QAction("User Settings", self)
        user_settings_action.triggered.connect(self.show_user_settings)
        if self.settings_menu:
            self.settings_menu.addAction(user_settings_action)
        else:
            logging.error("Failed to create Settings menu.")
        
        help_menu = menubar.addMenu("Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
    def show_network_info(self):
        if not self.current_user_id:
            QMessageBox.information(self, "Network Info", "You need to be logged in to view network information.")
            return
        
        info_text = f"Client Port: {self.port}\n"
        
        if self.channel_host and self.channel_host.is_running:
            info_text += f"\nChannel Hosting:\n"
            info_text += f"Host Port: {self.channel_host.host_port}\n"
            info_text += f"Hosted Channels: {len(self.channel_host.hosted_channels)}\n"
            
            if self.channel_host.hosted_channels:
                info_text += "\nHosted Channel Details:\n"
                db = SessionLocal()
                try:
                    for channel_id in self.channel_host.hosted_channels:
                        channel = db.query(Channel).get(channel_id)
                        if channel:
                            info_text += f"- {channel.name} (ID: {channel.id})\n"
                finally:
                    db.close()
        else:
            info_text += "\nChannel Hosting: Not active\n"
        
        QMessageBox.information(self, "Network Information", info_text)
    
    def create_or_join_channel(self):
        if not self.current_user_id:
            QMessageBox.warning(self, "Access Denied", "You must be logged in to create or join channels.")
            return
        
        db = SessionLocal()
        pre_existing_channels = []
        try:
            pre_existing_channels = [c.id for c in db.query(Channel).filter(Channel.owner_id == self.current_user_id).all()]
        except Exception as e:
            logging.error(f"Error listing pre-existing channels: {str(e)}")
        finally:
            db.close()
            
        dialog = ChannelDialog(self.current_user_id, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            db = SessionLocal()
            try:
                current_channels = [c for c in db.query(Channel).filter(Channel.owner_id == self.current_user_id).all()]
                
                new_channels = [c for c in current_channels if c.id not in pre_existing_channels]
                
                if new_channels and self.channel_host:
                    for new_channel in new_channels:
                        channel_id = new_channel.id
                        
                        self.channel_host.hosted_channels[channel_id] = self.channel_host.host_port
                        self.channel_host.load_channel_data(channel_id)
                        
                        if self.system_logger:
                            self.system_logger.log_channel_hosting(
                                channel_id, 
                                new_channel.name, 
                                "create", 
                                f"hosted on port {self.channel_host.host_port}"
                            )
            except Exception as e:
                logging.error(f"Error checking for new channels: {str(e)}")
            finally:
                db.close()
                
            self.load_channels()
    
    def logout(self):
        if self.current_user_id:
            db = SessionLocal()
            try:
                user = db.query(User).get(self.current_user_id)
                if user:
                    if user.status != "invisible":
                        self.set_status("offline")
            except Exception as e:
                logging.error(f"Error saving user status: {str(e)}")
            finally:
                db.close()
            
            if self.channel_host:
                self.channel_host.stop_hosting()
                self.channel_host = None
            
            if self.system_logger:
                self.system_logger.log_connection("localhost", self.port, "user_logout", f"User ID: {self.current_user_id}")
                self.system_logger.close()
                self.system_logger = None
            
            if self.visitor_username:
                db = SessionLocal()
                try:
                    user = db.query(User).get(self.current_user_id)
                    if user:
                        db.delete(user)
                        db.commit()
                except Exception as e:
                    logging.error(f"Error deleting visitor user: {str(e)}")
                    db.rollback()
                finally:
                    db.close()

        self.current_user_id = None
        self.visitor_username = None
        self.port = None
        self.current_channel = None
        self.current_friend = None

        self.channel_list.clear()
        self.friend_list.clear()
        self.chat_area.clear()
        self.channel_name_label.setText("Select a channel or friend")
        self.setWindowTitle("Hybrid ParadigmChat Chat")
        self.update_status_button()

        if not self.show_auth_dialog():
            self.close()
            
    def quit_application(self):
        if self.current_user_id:
            db = SessionLocal()
            try:
                user = db.query(User).get(self.current_user_id)
                if user:
                    if user.status != "invisible":
                        self.set_status("offline")
            except Exception as e:
                logging.error(f"Error saving user status: {str(e)}")
            finally:
                db.close()
        
        if self.system_logger:
            self.system_logger.log("Application exit")
            self.system_logger.close()
        
        if self.channel_host:
            self.channel_host.stop_hosting()
        
        VideoOpenerThread.terminate_all()
        
        self.close()
        
        import os
        import sys
        os._exit(0)
        
    def closeEvent(self, event):
        if self.current_user_id:
            try:
                db = SessionLocal()
                try:
                    user = db.query(User).get(self.current_user_id)
                    if user:
                        if user.status != "invisible":
                            self.set_status("offline")
                except Exception as e:
                    logging.error(f"Error saving user status on close: {str(e)}")
                finally:
                    db.close()
            except Exception as e:
                logging.error(f"Database error on close: {str(e)}")
        
        try:
            if self.system_logger:
                self.system_logger.log("Application closed")
                self.system_logger.close()
        except Exception as e:
            logging.error(f"Error closing system logger: {str(e)}")
        
        try:
            if hasattr(self, 'channel_host') and self.channel_host:
                self.channel_host.stop_hosting()
        except Exception as e:
            logging.error(f"Error stopping channel host: {str(e)}")
                
        try:
            if hasattr(self, 'realtime_handler') and self.realtime_handler:
                self.realtime_handler.stop()
        except Exception as e:
            logging.error(f"Error stopping realtime handler: {str(e)}")
            
        try:
            if hasattr(self, 'update_timer') and self.update_timer:
                self.update_timer.stop()
        except Exception as e:
            logging.error(f"Error stopping update timer: {str(e)}")
            
        try:
            VideoOpenerThread.terminate_all()
        except Exception as e:
            logging.error(f"Error terminating video processes: {str(e)}")
            
        event.accept()
        
        try:
            import os
            os._exit(0)  
        except Exception as e:
            import sys
            sys.exit(0)
        
    def show_auth_dialog(self) -> bool:
        dialog = AuthDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.port = dialog.port
            self.current_user_id = dialog.user_id
            self.visitor_username = dialog.visitor_username
            
            self.update_ui_after_auth()
            return True
        else:
            return False
            
    def update_ui_after_auth(self):
        add_friend_btn = self.centralWidget().findChild(QPushButton, "addFriendButton")
        create_join_btn = self.centralWidget().findChild(QPushButton, "createJoinChannelButton")
        
        if self.current_user_id:
            username = "User"
            status_to_set = "online"  
            
            self.system_logger = SystemLogger()
            self.system_logger.log(f"User {self.current_user_id} logged in - Port: {self.port}")
            
            db = SessionLocal()
            try:
                user = db.query(User).get(self.current_user_id)
                if user:
                    username = user.username
                    
                    if user.status != "invisible":
                        user.status = "online"
                        db.commit()
                        
                        if hasattr(self, 'realtime_handler') and self.realtime_handler:
                            self.realtime_handler.broadcast_message({
                                "type": "status_change",
                                "user_id": self.current_user_id,
                                "status": "online"
                            }, exclude_user_ids=[self.current_user_id])
                else:
                    logging.error(f"Failed to fetch user with ID {self.current_user_id} after auth.")
                    self.logout()
                    return
            finally:
                db.close()

            self.init_channel_hosting()

            self.setWindowTitle(f"Hybrid ParadigmChat Chat - {username} (Port: {self.port})")
            self.load_channels()
            self.load_friends()
            self.load_pending_requests()
            self.update_status_button()

            if add_friend_btn: add_friend_btn.setEnabled(True)
            if create_join_btn: create_join_btn.setEnabled(True)
            if hasattr(self, 'settings_menu') and self.settings_menu:
                self.settings_menu.setEnabled(True)

            self.realtime_handler = RealtimeHandler(self.port)
            self.realtime_handler.start()
            
            self.realtime_handler.friend_request_received.connect(self.handle_friend_request_received)
            self.realtime_handler.friend_request_accepted.connect(self.handle_friend_request_accepted)
            self.realtime_handler.friend_request_rejected.connect(self.handle_friend_request_rejected)
            self.realtime_handler.message_received.connect(self.handle_message_received)
            self.realtime_handler.status_changed.connect(self.handle_status_changed)
            
            if self.current_user_id or self.visitor_username:
                self.update_timer.start(1000)
            else:
                logging.warning("UI update timer not started due to missing user ID or visitor username.")
            
            if self.system_logger:
                self.system_logger.log_connection("localhost", self.port, "user_login", f"User ID: {self.current_user_id}")
            
        elif self.visitor_username:
            self.setWindowTitle(f"Hybrid ParadigmChat Chat - Visitor: {self.visitor_username} (Port: {self.port})")
            self.load_channels()
            self.friend_list.clear()
            self.chat_area.clear()
            self.channel_name_label.setText("Browse public channels")
            self.update_status_button()

            if add_friend_btn: add_friend_btn.setEnabled(False)
            if create_join_btn: create_join_btn.setEnabled(False)
            if hasattr(self, 'settings_menu') and self.settings_menu:
                self.settings_menu.setEnabled(False)
                
            if self.visitor_username:
                self.update_timer.start(1000)
            else:
                logging.warning("UI update timer not started for visitor due to missing visitor username.")
            
            if self.system_logger:
                self.system_logger.log_connection("localhost", self.port, "visitor_login", f"Visitor: {self.visitor_username}")
    
    def init_channel_hosting(self):
        if not self.current_user_id:
            return

        self.channel_host = ChannelHost(self.current_user_id, self.base_port + 1)
        
        success = self.channel_host.start_hosting()
        
        if success:
            logging.info(f"Started channel hosting on port {self.channel_host.host_port}")
            
            if self.system_logger:
                self.system_logger.log(f"Started channel hosting for user {self.current_user_id} on port {self.channel_host.host_port}")
        else:
            logging.error("Failed to start channel hosting")
            
            if self.system_logger:
                self.system_logger.log(f"Failed to start channel hosting for user {self.current_user_id}")
            
    def update_status_button(self):
        channel_info_layout = self.centralWidget().findChild(QHBoxLayout, "channelInfoLayout")
        if not channel_info_layout:
            logging.error("Cannot find channelInfoLayout to update status button.")
            return
        
        status_btn = self.centralWidget().findChild(QPushButton, "statusButton")
        
        if self.current_user_id:
            current_status = "Offline"
            db = SessionLocal()
            try:
                user = db.query(User).get(self.current_user_id)
                if user:
                    current_status = user.status.capitalize()
                else:
                    logging.warning(f"User {self.current_user_id} not found for status update.")
            finally:
                db.close()

            if not status_btn:
                status_btn = QPushButton(current_status, objectName="statusButton")
                status_btn.setFixedWidth(80)
                status_btn.setStyleSheet("padding: 5px; font-size: 12px;")
                status_btn.clicked.connect(self.show_status_menu)
                channel_info_layout.addWidget(status_btn)
            else:
                status_btn.setText(current_status)
                status_btn.show()
        elif status_btn:
            status_btn.hide()
            
    def load_channels(self):
        self.channel_list.clear()
        if not self.current_user_id and not self.visitor_username:
            return
            
        db = SessionLocal()
        try:
            channels = []
            
            if self.current_user_id:
                owned_channels = db.query(Channel).filter(Channel.owner_id == self.current_user_id).all()
                
                joined_channels = db.query(Channel).join(Channel.members).filter(
                    ChannelMembership.user_id == self.current_user_id,
                    Channel.owner_id != self.current_user_id
                ).all()
                
                channels = owned_channels + joined_channels
                
            elif self.visitor_username:
                channels = db.query(Channel).filter(
                    Channel.allow_visitors == True
                ).all()
            
            def channel_sort_key(channel):
                has_unread = self.unread_channel_messages.get(channel.id, 0) > 0
                if has_unread:
                    return (0, channel.name)
                else:
                    return (1, channel.name)
            
            sorted_channels = sorted(channels, key=channel_sort_key)
            
            for channel in sorted_channels:
                    channel_widget = QWidget()
                    channel_layout = QHBoxLayout()
                    channel_layout.setContentsMargins(8, 5, 8, 5)  
                    
                    icon = "🔒" if channel.is_private else "#"
                    name_label = QLabel(f"{icon} {channel.name}")
                    
                    if self.unread_channel_messages.get(channel.id, 0) > 0:
                        name_label.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold;")
                    else:
                        name_label.setStyleSheet("color: #ffffff; font-size: 13px;")
                    
                    channel_layout.addWidget(name_label)
                    channel_layout.addStretch()
                    
                    if self.current_user_id and channel.owner_id == self.current_user_id:
                        from functools import partial
                        
                        edit_btn = QPushButton("⋮")  
                        edit_btn.setFixedSize(16, 16)  
                        edit_btn.setStyleSheet("""
                            QPushButton {
                                background-color: #5865f2;
                                border: none;
                                border-radius: 8px;
                                color: #ffffff;
                                font-size: 12px;
                                padding: 0px;
                            }
                            QPushButton:hover {
                                background-color: #4752c4;
                            }
                        """)
                        edit_btn.clicked.connect(partial(self.edit_channel, channel.id))
                        channel_layout.addWidget(edit_btn)
                    
                    channel_widget.setLayout(channel_layout)
                    
                    item = QListWidgetItem()
                    item.setSizeHint(QSize(channel_widget.sizeHint().width(), 32))  
                    item.setData(Qt.ItemDataRole.UserRole, channel.id)
                    self.channel_list.addItem(item)
                    self.channel_list.setItemWidget(item, channel_widget)
                    
        except Exception as e:
            logging.error(f"Error loading channels: {str(e)}")
            QMessageBox.critical(self, "Error", "Could not load channel list.")
        finally:
            db.close()
            
    def edit_channel(self, channel_id: int):
        dialog = ChannelDialog(self.current_user_id, self)
        dialog.edit_channel(channel_id)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_channels()
            
    def load_friends(self):
        self.friend_list.clear()
        if not self.current_user_id:
            return
            
        db = SessionLocal()
        try:
            q1 = db.query(User).join(
                Friendship, User.id == Friendship.friend_id
            ).filter(Friendship.user_id == self.current_user_id)
            q2 = db.query(User).join(
                Friendship, User.id == Friendship.user_id
            ).filter(Friendship.friend_id == self.current_user_id)

            friends_query = q1.union(q2)
            friends = friends_query.order_by(User.username).all()

            friends = [friend for friend in friends if friend.id != self.current_user_id]
            
            def friend_sort_key(friend):
                has_unread = self.unread_friend_messages.get(friend.id, 0) > 0
                is_online = friend.status == "online"
                if has_unread:
                    return (0, 0 if is_online else 1, friend.username)
                elif is_online:
                    return (1, 0, friend.username)
                else:
                    return (2, 0, friend.username)
            
            sorted_friends = sorted(friends, key=friend_sort_key)
            
            for friend in sorted_friends:
                friend_widget = QWidget()
                friend_layout = QHBoxLayout()
                friend_layout.setContentsMargins(10, 5, 10, 5)  
                
                status_icon = "🟢" if friend.status == "online" else "⚪"
                name_label = QLabel(f"{status_icon} {friend.username}")
                
                if self.unread_friend_messages.get(friend.id, 0) > 0:
                    name_label.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: bold;")  
                else:
                    name_label.setStyleSheet("color: #ffffff; font-size: 12px;")  
                
                friend_layout.addWidget(name_label)
                friend_layout.addStretch()
                
                friend_widget.setLayout(friend_layout)
                
                item = QListWidgetItem()
                item.setSizeHint(QSize(friend_widget.sizeHint().width(), 36))  
                item.setData(Qt.ItemDataRole.UserRole, friend.id)
                self.friend_list.addItem(item)
                self.friend_list.setItemWidget(item, friend_widget)
                
        except Exception as e:
             logging.error(f"Error loading friends: {str(e)}")
             QMessageBox.critical(self, "Error", "Could not load friend list.")
        finally:
            db.close()
            
    def channel_selected(self, item):
        channel_id = item.data(Qt.ItemDataRole.UserRole)
        self.current_channel = channel_id
        self.current_friend = None
        
        self.unread_channel_messages[channel_id] = 0
        
        self.pause_updates_checkbox.setVisible(True)
        self.pause_updates_checkbox.setChecked(self.paused_updates_channel.get(channel_id, False))
        
        self.load_channel_messages()
        self.load_channels()  
        
        db = SessionLocal()
        try:
            channel = db.query(Channel).get(channel_id)
            if channel:
                self.channel_name_label.setText(f"# {channel.name}")
            else:
                self.channel_name_label.setText("Channel not found")
        finally:
             db.close()
        
    def friend_selected(self, item):
        friend_id = item.data(Qt.ItemDataRole.UserRole)
        if friend_id == self.current_user_id:
             return
        self.current_friend = friend_id
        self.current_channel = None
        
        self.unread_friend_messages[friend_id] = 0
        
        self.pause_updates_checkbox.setVisible(True)
        self.pause_updates_checkbox.setChecked(self.paused_updates_friend.get(friend_id, False))
        
        self.load_friend_messages()
        self.load_friends() 
        
        db = SessionLocal()
        try:
            friend = db.query(User).get(friend_id)
            if friend:
                self.channel_name_label.setText(f"@ {friend.username}")
            else:
                self.channel_name_label.setText("Friend not found")
        finally:
            db.close()
        
    def load_channel_messages(self):
        self.chat_area.clear()
        if not self.current_channel:
            return
        if not self.current_user_id and not self.visitor_username:
            return
            
        db = SessionLocal()
        try:
            messages = db.query(Message).filter(
                Message.channel_id == self.current_channel
            ).order_by(Message.created_at).limit(100).all()
            
            sender_ids = {msg.sender_id for msg in messages}
            senders = db.query(User).filter(User.id.in_(sender_ids)).all()
            sender_map = {sender.id: sender.username for sender in senders}

            for message in messages:
                if message.sender_id == self.current_user_id:
                    sender_display = "<b>~You~</b>"
                else:
                    sender_name = sender_map.get(message.sender_id, f"User {message.sender_id}")
                    sender_display = f"<b>{sender_name}</b>"
                
                if message.has_media:
                    if message.media_type == "image":
                        if message.content:
                            self.append_to_chat(f"{sender_display}: {message.content}")
                        self.append_to_chat(f'<img src="{message.media_path}" width="200" />')
                    else: 
                        if message.content:
                            self.append_to_chat(f"{sender_display}: {message.content}<br/><i>[Video]</i>")
                        else:
                            self.append_to_chat(f"{sender_display}: <i>[Video]</i>")
                            
                        thumbnail_path = self.generate_video_thumbnail(message.media_path)
                        
                        file_path = os.path.abspath(message.media_path)
                        file_url = QUrl.fromLocalFile(file_path).toString()
                        self.append_to_chat(f'<a href="{file_url}"><img src="{thumbnail_path}" width="320" height="180" style="border:2px solid #5865f2; border-radius:8px;"/></a>')
                else:
                    self.append_to_chat(f"{sender_display}: {message.content}")
        except Exception as e:
             logging.error(f"Error loading channel messages: {str(e)}")
        finally:
            db.close()
            
    def load_friend_messages(self):
        self.chat_area.clear()
        if not self.current_friend or not self.current_user_id:
            return
            
        db = SessionLocal()
        try:
            messages = db.query(Message).filter(
                or_(
                    and_(Message.sender_id == self.current_user_id, Message.receiver_id == self.current_friend),
                    and_(Message.sender_id == self.current_friend, Message.receiver_id == self.current_user_id)
                ),
                Message.is_direct == True
            ).order_by(Message.created_at).all()
            
            friend = db.query(User).get(self.current_friend)
            if not friend:
                self.append_to_chat("Friend not found")
                return
                
            for message in messages:
                if message.sender_id == self.current_user_id:
                    sender_display = "<b>~You~</b>"
                else:
                    sender_display = f"<b>{friend.username}</b>"
                
                if message.has_media:
                    if message.media_type == "image":
                        if message.content:
                            self.append_to_chat(f"{sender_display}: {message.content}")
                        self.append_to_chat(f'<img src="{message.media_path}" width="200" />')
                    else:  
                        if message.content:
                            self.append_to_chat(f"{sender_display}: {message.content}<br/><i>[Video]</i>")
                        else:
                            self.append_to_chat(f"{sender_display}: <i>[Video]</i>")
                            
                        thumbnail_path = self.generate_video_thumbnail(message.media_path)
                        
                        file_path = os.path.abspath(message.media_path)
                        file_url = QUrl.fromLocalFile(file_path).toString()
                        self.append_to_chat(f'<a href="{file_url}"><img src="{thumbnail_path}" width="320" height="180" style="border:2px solid #5865f2; border-radius:8px;"/></a>')
                else:
                    self.append_to_chat(f"{sender_display}: {message.content}")
                    
            self.mark_messages_as_read(self.current_friend)
            
        except Exception as e:
            logging.error(f"Error loading friend messages: {str(e)}")
            QMessageBox.critical(self, "Error", "Could not load messages")
        finally:
            db.close()
            
    def mark_messages_as_read(self, friend_id):
        if not self.current_user_id:
            return
            
        db = SessionLocal()
        try:
            messages = db.query(Message).filter(
                Message.sender_id == friend_id,
                Message.receiver_id == self.current_user_id,
                Message.is_direct == True,
                Message.is_read == False
            ).all()
            
            for message in messages:
                message.is_read = True
                
            db.commit()
        except Exception as e:
            logging.error(f"Error marking messages as read: {str(e)}")
            db.rollback()
        finally:
            db.close()
        
    def send_message(self):
        message = self.message_input.text().strip()
        
        if not message and not self.selected_media_path:
            return
            
        if self.current_channel:
            if not self.current_user_id and not self.visitor_username: return
            self.send_channel_message(message)
        elif self.current_friend:
             if not self.current_user_id: return
             self.send_direct_message(message)

        self.message_input.clear()
        self.clear_selected_media()
        
    def send_channel_message(self, message):
        sender_id_to_use = self.current_user_id
        if not sender_id_to_use:
            logging.warning("Visitor tried to send channel message.")
            return

        db = SessionLocal()
        try:
            channel = db.query(Channel).get(self.current_channel)
            if not channel:
                QMessageBox.warning(self, "Error", "Channel not found")
                return
                
            if not channel.allow_visitor_messages and not self.current_user_id:
                QMessageBox.warning(self, "Error", "Visitors are not allowed to send messages in this channel")
                return
                
            has_media = self.selected_media_path is not None
            media_path = None
            media_type = None
            media_name = None
            
            if has_media:
                media_path = self.save_media_file(self.selected_media_path, self.selected_media_type)
                media_type = self.selected_media_type
                media_name = os.path.basename(self.selected_media_path)
            
            new_message = Message(
                content=message,
                sender_id=sender_id_to_use,
                channel_id=self.current_channel,
                has_media=has_media,
                media_type=media_type,
                media_path=media_path,
                media_name=media_name
            )
            db.add(new_message)
            db.commit()

            if self.system_logger:
                self.system_logger.log_data_transaction(
                    "send",
                    "localhost",
                    self.port,
                    "channel_message",
                    len(message) + (len(media_path) if media_path else 0)
                )

            if has_media:
                if media_type == "image":
                    if message:
                        self.append_to_chat(f"<b>~You~</b>: {message}", True)
                    self.append_to_chat(f'<img src="{media_path}" width="200" />', True)
                else: 
                    if message:
                        self.append_to_chat(f"<b>~You~</b>: {message}<br/><i>[Video]</i>", True)
                    else:
                        self.append_to_chat(f"<b>~You~</b>: <i>[Video]</i>", True)
                        
                        thumbnail_path = self.generate_video_thumbnail(media_path)
                        
                        file_path = os.path.abspath(media_path)
                        file_url = QUrl.fromLocalFile(file_path).toString()
                        self.append_to_chat(f'<a href="{file_url}"><img src="{thumbnail_path}" width="320" height="180" style="border:2px solid #5865f2; border-radius:8px;"/></a>', True)
            else:
                self.append_to_chat(f"<b>~You~</b>: {message}", True)
            
            sender_username = f"Visitor {self.visitor_username}"
            if self.current_user_id:
                user = db.query(User).get(self.current_user_id)
                sender_username = user.username if user else f"User {self.current_user_id}"
            
            if self.realtime_handler:
                members = db.query(ChannelMembership).filter(
                    ChannelMembership.channel_id == self.current_channel,
                    ChannelMembership.user_id != self.current_user_id  
                ).all()
                
                message_data = {
                        "type": "message",
                        "sender_id": self.current_user_id,
                        "sender_username": sender_username,
                        "content": message,
                        "channel_id": self.current_channel,
                        "is_direct": False
                }
                
                if has_media:
                    message_data.update({
                        "has_media": True,
                        "media_type": media_type,
                        "media_path": media_path,
                        "media_name": media_name
                    })
                
                for member in members:
                    self.realtime_handler.send_message(member.user_id, message_data)
                    
                    if self.system_logger:
                        self.system_logger.log_data_transaction(
                            "send",
                            "localhost",
                            self.port,
                            f"channel_message_to_user_{member.user_id}",
                            len(message) + (len(media_path) if media_path else 0)
                        )
                
                if self.channel_host and self.channel_host.is_running and channel.id in self.channel_host.hosted_channels:
                    if self.system_logger:
                        self.system_logger.log_channel_hosting(
                            channel.id,
                            channel.name,
                            "message",
                            f"from user {self.current_user_id}"
                        )
                    
                    if self.channel_host.channel_data.get(channel.id):
                        message_dict = {
                            "id": new_message.id,
                            "content": new_message.content,
                            "sender_id": new_message.sender_id,
                            "created_at": new_message.created_at.isoformat() if new_message.created_at else None,
                            "has_media": new_message.has_media,
                            "media_type": new_message.media_type,
                            "media_path": new_message.media_path,
                            "media_name": new_message.media_name
                        }
                        self.channel_host.channel_data[channel.id]["messages"].insert(0, message_dict)
                    
        except Exception as e:
            logging.error(f"Error sending channel message: {str(e)}")
            QMessageBox.critical(self, "Error", "Could not send message.")
            db.rollback()
        finally:
            db.close()
            
    def send_direct_message(self, message):
        if not self.current_user_id or not self.current_friend:
            return
            
        db = SessionLocal()
        try:
            has_media = self.selected_media_path is not None
            media_path = None
            media_type = None
            media_name = None
            
            if has_media:
                media_path = self.save_media_file(self.selected_media_path, self.selected_media_type)
                media_type = self.selected_media_type
                media_name = os.path.basename(self.selected_media_path)
                
            new_message = Message(
                content=message,
                sender_id=self.current_user_id,
                receiver_id=self.current_friend,
                is_direct=True,
                has_media=has_media,
                media_type=media_type,
                media_path=media_path,
                media_name=media_name
            )
            db.add(new_message)
            db.commit()
            
            sender = db.query(User).get(self.current_user_id)
            sender_username = sender.username if sender else f"User {self.current_user_id}"
            
            if has_media:
                if media_type == "image":
                    if message:
                        self.append_to_chat(f"<b>~You~</b>: {message}", True)
                    self.append_to_chat(f'<img src="{media_path}" width="200" />', True)
                else:  
                    if message:
                        self.append_to_chat(f"<b>~You~</b>: {message}<br/><i>[Video]</i>", True)
                    else:
                        self.append_to_chat(f"<b>~You~</b>: <i>[Video]</i>", True)
                        
                        thumbnail_path = self.generate_video_thumbnail(media_path)
                        
                        file_path = os.path.abspath(media_path)
                        file_url = QUrl.fromLocalFile(file_path).toString()
                        self.append_to_chat(f'<a href="{file_url}"><img src="{thumbnail_path}" width="320" height="180" style="border:2px solid #5865f2; border-radius:8px;"/></a>', True)
            else:
                self.append_to_chat(f"<b>~You~</b>: {message}", True)
            
            if self.realtime_handler:
                message_data = {
                    "type": "message",
                    "sender_id": self.current_user_id,
                    "sender_username": sender_username,
                    "content": message,
                    "is_direct": True
                }
                
                if has_media:
                    message_data.update({
                        "has_media": True,
                        "media_type": media_type,
                        "media_path": media_path,
                        "media_name": media_name
                    })
                    
                self.realtime_handler.send_message(self.current_friend, message_data)
            
            self.mark_messages_as_read(self.current_friend)
            
        except Exception as e:
            logging.error(f"Error sending direct message: {str(e)}")
            QMessageBox.critical(self, "Error", "Could not send message")
            db.rollback()
        finally:
            db.close()
            
    def add_friend(self):
        if not self.current_user_id:
            QMessageBox.warning(self, "Access Denied", "You must be logged in to add friends.")
            return
            
        dialog = FriendDialog(self.current_user_id, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_pending_requests()
            
    def show_status_menu(self):
        if not self.current_user_id: return

        menu = QMenu(self)
        online_action = menu.addAction("🟢 Online")
        invisible_action = menu.addAction("👻 Invisible")

        online_action.triggered.connect(lambda: self.set_status("online"))
        invisible_action.triggered.connect(lambda: self.set_status("invisible"))

        sender_button = self.sender()
        if isinstance(sender_button, QPushButton):
             menu.exec(sender_button.mapToGlobal(sender_button.rect().bottomLeft()))
        else:
             menu.exec(QCursor.pos())
        
    def set_status(self, status):
        if not self.current_user_id:
            return
            
        db = SessionLocal()
        try:
            user = db.query(User).get(self.current_user_id)
            if user:
                user.status = status
                db.commit()
                
                if self.realtime_handler:
                    self.realtime_handler.broadcast_message({
                        "type": "status_change",
                        "user_id": self.current_user_id,
                        "status": status
                    }, exclude_user_ids=[self.current_user_id])
                
                self.update_status_button()
                self.load_friends()
            else:
                logging.warning(f"User {self.current_user_id} not found when trying to set status.")
        except Exception as e:
            logging.error(f"Error setting status: {str(e)}")
            db.rollback()
        finally:
            db.close()
            
    def show_user_settings(self):
        if not self.current_user_id:
             QMessageBox.warning(self, "Access Denied", "You must be logged in to view settings.")
             return
        dialog = SettingsDialog(self.current_user_id, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
             self.update_ui_after_auth()

    def show_about(self):
        QMessageBox.about(self, "About",
            "Hybrid ParadigmChat Chat Application\n"
            "Version 1.0\n"
            "A hybrid client-server and P2P chat application."
        )
        
    def logout(self):
        if self.current_user_id:
            db = SessionLocal()
            try:
                user = db.query(User).get(self.current_user_id)
                if user:
                    if user.status != "invisible":
                        self.set_status("offline")
            except Exception as e:
                logging.error(f"Error saving user status: {str(e)}")
            finally:
                db.close()
            
            if self.channel_host:
                self.channel_host.stop_hosting()
                self.channel_host = None
            
            if self.system_logger:
                self.system_logger.log_connection("localhost", self.port, "user_logout", f"User ID: {self.current_user_id}")
                self.system_logger.close()
                self.system_logger = None
            
            if self.visitor_username:
                db = SessionLocal()
                try:
                    user = db.query(User).get(self.current_user_id)
                    if user:
                        db.delete(user)
                        db.commit()
                except Exception as e:
                    logging.error(f"Error deleting visitor user: {str(e)}")
                    db.rollback()
                finally:
                    db.close()

        self.current_user_id = None
        self.visitor_username = None
        self.port = None
        self.current_channel = None
        self.current_friend = None

        self.channel_list.clear()
        self.friend_list.clear()
        self.chat_area.clear()
        self.channel_name_label.setText("Select a channel or friend")
        self.setWindowTitle("Hybrid ParadigmChat Chat")
        self.update_status_button()

        if not self.show_auth_dialog():
            self.close()
        
    def quit_application(self):
        if self.current_user_id:
            db = SessionLocal()
            try:
                user = db.query(User).get(self.current_user_id)
                if user:
                    if user.status != "invisible":
                        self.set_status("offline")
            except Exception as e:
                logging.error(f"Error saving user status: {str(e)}")
            finally:
                db.close()
        
        if self.system_logger:
            self.system_logger.log("Application exit")
            self.system_logger.close()
        
        if self.channel_host:
            self.channel_host.stop_hosting()
        
        VideoOpenerThread.terminate_all()
        
        self.close()
        
        import os
        import sys
        os._exit(0)  
        
    def closeEvent(self, event):
        if self.current_user_id:
            try:
                db = SessionLocal()
                try:
                    user = db.query(User).get(self.current_user_id)
                    if user:
                        if user.status != "invisible":
                            self.set_status("offline")
                except Exception as e:
                    logging.error(f"Error saving user status on close: {str(e)}")
                finally:
                    db.close()
            except Exception as e:
                logging.error(f"Database error on close: {str(e)}")
        
        try:
            if self.system_logger:
                self.system_logger.log("Application closed")
                self.system_logger.close()
        except Exception as e:
            logging.error(f"Error closing system logger: {str(e)}")
        
        try:
            if hasattr(self, 'channel_host') and self.channel_host:
                self.channel_host.stop_hosting()
        except Exception as e:
            logging.error(f"Error stopping channel host: {str(e)}")
                
        try:
            if hasattr(self, 'realtime_handler') and self.realtime_handler:
                self.realtime_handler.stop()
        except Exception as e:
            logging.error(f"Error stopping realtime handler: {str(e)}")
            
        try:
            if hasattr(self, 'update_timer') and self.update_timer:
                self.update_timer.stop()
        except Exception as e:
            logging.error(f"Error stopping update timer: {str(e)}")
            
        try:
            VideoOpenerThread.terminate_all()
        except Exception as e:
            logging.error(f"Error terminating video processes: {str(e)}")
            
            event.accept()
        
        try:
            import os
            os._exit(0)  
        except Exception as e:
            import sys
            sys.exit(0)

    def update_friend_list(self):
        if self.current_user_id:
            self.load_friends()
        
    def load_pending_requests(self):
        self.pending_list.clear()
        if not self.current_user_id:
            return
            
        db = SessionLocal()
        try:
            requests = db.query(FriendRequest).filter(
                FriendRequest.receiver_id == self.current_user_id,
                FriendRequest.status == "pending"
            ).all()
            
            for request in requests:
                sender = db.query(User).get(request.sender_id)
                if sender:
                    item = QListWidgetItem(f"Pending: {sender.username}")
                    item.setData(Qt.ItemDataRole.UserRole, request.id)
                    self.pending_list.addItem(item)
                    
        except Exception as e:
            logging.error(f"Error loading pending requests: {str(e)}")
        finally:
            db.close()
            
    def pending_friend_selected(self, item):
        request_id = item.data(Qt.ItemDataRole.UserRole)
        if not request_id:
            return
            
        menu = QMenu(self)
        accept_action = menu.addAction("Accept")
        reject_action = menu.addAction("Reject")
        
        action = menu.exec(self.pending_list.mapToGlobal(self.pending_list.visualItemRect(item).bottomLeft()))
        
        if action == accept_action:
            self.accept_friend_request(request_id)
        elif action == reject_action:
            self.reject_friend_request(request_id)
            
    def accept_friend_request(self, request_id: int):
        db = SessionLocal()
        try:
            request = db.query(FriendRequest).filter(FriendRequest.id == request_id).first()
            if not request:
                QMessageBox.warning(self, "Error", "Friend request not found")
                return

            sender = db.query(User).filter(User.id == request.sender_id).first()
            receiver = db.query(User).filter(User.id == request.receiver_id).first()

            if not sender or not receiver:
                QMessageBox.warning(self, "Error", "User not found")
                return

            friendship1 = Friendship(user_id=sender.id, friend_id=receiver.id)
            friendship2 = Friendship(user_id=receiver.id, friend_id=sender.id)
            db.add(friendship1)
            db.add(friendship2)

            db.delete(request)
            db.commit()

            if self.realtime_handler:
                self.realtime_handler.send_message(sender.id, {
                    "type": "friend_request_accepted",
                    "friend_id": receiver.id,
                    "friend_username": receiver.username
                })

            self.load_friends()
            self.load_pending_requests()

            QMessageBox.information(self, "Success", f"You are now friends with {sender.username}!")
        except Exception as e:
            logging.error(f"Error accepting friend request: {str(e)}")
            QMessageBox.critical(self, "Error", "Failed to accept friend request")
            db.rollback()
        finally:
            db.close()
            
    def reject_friend_request(self, request_id):
        db = SessionLocal()
        try:
            request = db.query(FriendRequest).get(request_id)
            if request and request.receiver_id == self.current_user_id:
                request.status = "rejected"
                db.commit()
                
                self.load_pending_requests()
                
                QMessageBox.information(self, "Success", "Friend request rejected.")
            else:
                QMessageBox.warning(self, "Error", "Invalid friend request.")
        except Exception as e:
            logging.error(f"Error rejecting friend request: {str(e)}")
            db.rollback()
            QMessageBox.critical(self, "Error", "Could not reject friend request.")
        finally:
            db.close()
            
    def handle_friend_request_received(self, data: dict):
        item = QListWidgetItem(f"Pending: {data['sender_username']}")
        item.setData(Qt.ItemDataRole.UserRole, data['request_id'])
        self.pending_list.addItem(item)
        
    def handle_friend_request_accepted(self, data: dict):
        status_icon = "🟢" if data.get('status') == "online" else "⚪"
        item = QListWidgetItem(f"{status_icon} {data['friend_username']}")
        item.setData(Qt.ItemDataRole.UserRole, data['friend_id'])
        self.friend_list.addItem(item)
        
        for i in range(self.pending_list.count()):
            item = self.pending_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == data['request_id']:
                self.pending_list.takeItem(i)
                break
                
    def handle_friend_request_rejected(self, data: dict):
        for i in range(self.pending_list.count()):
            item = self.pending_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == data['request_id']:
                self.pending_list.takeItem(i)
                break
                
    def handle_message_received(self, data: dict):
        logging.debug(f"Nhận được tin nhắn: {data}")
        
        if self.system_logger:
            msg_type = "direct" if data.get("is_direct") else "channel"
            self.system_logger.log_data_transaction(
                "receive",
                "localhost",
                self.port,
                f"{msg_type}_message",
                len(data.get("content", "")) + 
                (len(data.get("media_path", "")) if data.get("has_media") else 0)
            )
        
        if data.get("is_direct"):
            sender_id = data["sender_id"]
            
            if self.current_friend == sender_id:
                sender_display = f"<b>{data['sender_username']}</b>"
                
                if data.get("has_media"):
                    if data['media_type'] == "image":
                        if data['content']:
                            self.append_to_chat(f"{sender_display}: {data['content']}")
                        self.append_to_chat(f'<img src="{data["media_path"]}" width="200" />')
                    else:  
                        if data['content']:
                            self.append_to_chat(f"{sender_display}: {data['content']}<br/><i>[Video]</i>")
                        else:
                            self.append_to_chat(f"{sender_display}: <i>[Video]</i>")
                            
                        thumbnail_path = self.generate_video_thumbnail(data["media_path"])
                        
                        file_path = os.path.abspath(data["media_path"])
                        file_url = QUrl.fromLocalFile(file_path).toString()
                        self.append_to_chat(f'<a href="{file_url}"><img src="{thumbnail_path}" width="320" height="180" style="border:2px solid #5865f2; border-radius:8px;"/></a>')
                else:
                    self.append_to_chat(f"{sender_display}: {data['content']}")
                    
                self.mark_messages_as_read(self.current_friend)
            else:
                current_count = self.unread_friend_messages.get(sender_id, 0)
                self.unread_friend_messages[sender_id] = current_count + 1
                self.load_friends()
        else:
            channel_id = data.get("channel_id") 
            if self.current_channel == channel_id:
                if data['sender_id'] == self.current_user_id:
                    sender_display = "<b>~You~</b>"
                else:
                    sender_display = f"<b>{data['sender_username']}</b>"
                
                if data.get("has_media"):
                    if data['media_type'] == "image":
                        if data['content']:
                            self.append_to_chat(f"{sender_display}: {data['content']}")
                        self.append_to_chat(f'<img src="{data["media_path"]}" width="200" />')
                    else:  
                        if data['content']:
                            self.append_to_chat(f"{sender_display}: {data['content']}<br/><i>[Video]</i>")
                        else:
                            self.append_to_chat(f"{sender_display}: <i>[Video]</i>")
                            
                        thumbnail_path = self.generate_video_thumbnail(data["media_path"])
                        
                        file_path = os.path.abspath(data["media_path"])
                        file_url = QUrl.fromLocalFile(file_path).toString()
                        self.append_to_chat(f'<a href="{file_url}"><img src="{thumbnail_path}" width="320" height="180" style="border:2px solid #5865f2; border-radius:8px;"/></a>')
                else:
                    self.append_to_chat(f"{sender_display}: {data['content']}")
            else:
                current_count = self.unread_channel_messages.get(channel_id, 0)
                self.unread_channel_messages[channel_id] = current_count + 1
                self.load_channels()
                
        self.load_recent_messages()
        
    def handle_status_changed(self, data: dict):
        for i in range(self.friend_list.count()):
            item = self.friend_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == data['user_id']:
                status_icon = "🟢" if data['status'] == "online" else "⚪"
                item.setText(f"{status_icon} {item.text().split(' ')[1]}")
                break
        
    def send_friend_request(self, target_user_id: int):
        db = SessionLocal()
        try:
            new_request = FriendRequest(
                sender_id=self.current_user_id,
                receiver_id=target_user_id,
                status="pending"
            )
            db.add(new_request)
            db.commit()
            
            if self.realtime_handler:
                target_user = db.query(User).get(target_user_id)
                if target_user:
                    self.realtime_handler.send_message(target_user_id, {
                        "type": "friend_request",
                        "sender_id": self.current_user_id,
                        "sender_username": target_user.username
                    })
            
            QMessageBox.information(self, "Success", "Friend request sent!")
            
        except Exception as e:
            logging.error(f"Error sending friend request: {str(e)}")
            QMessageBox.critical(self, "Error", "Could not send friend request")
            db.rollback()
        finally:
            db.close()

    def auto_update_ui(self):
        if self.current_user_id:
            self.load_friends()
            
            self.load_pending_requests()
            
            if self.current_friend and not self.paused_updates_friend.get(self.current_friend, False):
                self.load_friend_messages()
            elif self.current_channel and not self.paused_updates_channel.get(self.current_channel, False):
                self.load_channel_messages()
                
        elif self.visitor_username:
            
            self.update_timer.stop()
        else:
            logging.warning("auto_update_ui called with no user ID and no visitor username.") 

    def attach_image(self):
        from PySide6.QtWidgets import QFileDialog
        
        image_formats = "Images (*.png *.jpg *.jpeg *.gif *.bmp)"
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "", image_formats
        )
        
        if file_path:
            if os.path.getsize(file_path) > 5 * 1024 * 1024:
                QMessageBox.warning(
                    self, "File too large", 
                    "Image files must be smaller than 5MB."
                )
                return
            
            self.selected_media_path = file_path
            self.selected_media_type = "image"
            
            filename = os.path.basename(file_path)
            self.selected_media_label.setText(f"Selected image: {filename}")
            self.selected_media_label.setVisible(True)
            
            self.message_input.setFocus()

    def attach_video(self):
        from PySide6.QtWidgets import QFileDialog
        
        video_formats = "Videos (*.mp4 *.avi *.mov *.wmv *.mkv)"
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Video", "", video_formats
        )
        
        if file_path:
            if os.path.getsize(file_path) > 50 * 1024 * 1024:
                QMessageBox.warning(
                    self, "File too large", 
                    "Video files must be smaller than 50MB."
                )
                return
            
            self.selected_media_path = file_path
            self.selected_media_type = "video"
            
            filename = os.path.basename(file_path)
            self.selected_media_label.setText(f"Selected video: {filename}")
            self.selected_media_label.setVisible(True)
            
            self.message_input.setFocus()
            
    def clear_selected_media(self):
        self.selected_media_path = None
        self.selected_media_type = None
        self.selected_media_label.setText("")
        self.selected_media_label.setVisible(False)

    def save_media_file(self, source_path, media_type):
        base_dir = os.path.join(os.getcwd(), "media")
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)
            
        type_dir = os.path.join(base_dir, media_type + "s")  
        if not os.path.exists(type_dir):
            os.makedirs(type_dir)
            
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = os.path.basename(source_path)
        name, ext = os.path.splitext(filename)
        unique_filename = f"{name}_{timestamp}{ext}"
        
        dest_path = os.path.join(type_dir, unique_filename)
        
        import shutil
        shutil.copy2(source_path, dest_path)
        
        return os.path.relpath(dest_path, os.getcwd())

    def handle_link_clicked(self, url):
        url_str = url.toString()
        
        if url_str.endswith(('.mp4', '.avi', '.mov', '.wmv', '.mkv')):
            try:
                if not url_str.startswith('file:'):
                    file_path = url_str.replace('\\', '/')
                    
                    if not os.path.isabs(file_path):
                        file_path = os.path.abspath(file_path)
                    
                    file_url = QUrl.fromLocalFile(file_path)
                else:
                    file_url = url
                
                self.video_opener = VideoOpenerThread(file_url)
                self.video_opener.start()
                
                self.statusBar().showMessage(f"Opening video player...", 3000)
                
            except Exception as e:
                logging.error(f"Error opening video: {str(e)}")
                QMessageBox.warning(self, "Error", f"Could not open video: {str(e)}")
    
    def generate_video_thumbnail(self, video_path):
        base_dir = os.path.join(os.getcwd(), "media", "thumbnails")
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)
            
        video_filename = os.path.basename(video_path)
        name, _ = os.path.splitext(video_filename)
        thumbnail_path = os.path.join(base_dir, f"{name}_thumb.png")
        
        if os.path.exists(thumbnail_path):
            return os.path.relpath(thumbnail_path, os.getcwd())
        
        if not os.path.exists(video_path):
            logging.error(f"Video file not found: {video_path}")
            return self.create_generic_thumbnail(thumbnail_path, "FILE NOT FOUND")
        
        try:
            import cv2
            logging.info(f"Opening video file: {video_path}")
            
            video = cv2.VideoCapture(video_path)
            
            if not video.isOpened():
                logging.error(f"Could not open video file: {video_path}")
                return self.create_generic_thumbnail(thumbnail_path, "CANNOT OPEN")
                
            fps = video.get(cv2.CAP_PROP_FPS)
            frame_count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count/fps if fps > 0 else 0
            
            logging.info(f"Video properties: {fps} fps, {frame_count} frames, {duration:.2f} seconds")
            
            positions = [1, 5, 10, 0]  
            
            for pos in positions:
                if pos > 0:
                    video.set(cv2.CAP_PROP_POS_MSEC, pos * 1000)
                else:
                    video.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    
                success, frame = video.read()
                
                if success and frame is not None and frame.size > 0:
                    logging.info(f"Successfully extracted frame at position {pos}s")
                    break
            
            if not success or frame is None or frame.size == 0:
                logging.error("Failed to extract any usable frame from video")
                return self.create_generic_thumbnail(thumbnail_path, "NO FRAME")
                
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            height, width = frame_rgb.shape[:2]
            target_width, target_height = 320, 180
            
            if width / height > target_width / target_height:
                new_width = target_width
                new_height = int(height * (target_width / width))
            else:
                new_height = target_height
                new_width = int(width * (target_height / height))
            
            resized_frame = cv2.resize(frame_rgb, (new_width, new_height))
            
            img = Image.new('RGB', (target_width, target_height), color=(0, 0, 0))
            
            frame_img = Image.fromarray(resized_frame)
            x_offset = (target_width - new_width) // 2
            y_offset = (target_height - new_height) // 2
            img.paste(frame_img, (x_offset, y_offset))
            
            overlay = Image.new('RGBA', (target_width, target_height), (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            
            center_x, center_y = target_width // 2, target_height // 2
            circle_radius = min(target_width, target_height) // 6
            
            overlay_draw.ellipse(
                (center_x - circle_radius, center_y - circle_radius,
                 center_x + circle_radius, center_y + circle_radius),
                fill=(0, 0, 0, 160)
            )
            
            play_offset = circle_radius // 3  
            triangle_points = [
                (center_x - circle_radius//2 + play_offset, center_y - circle_radius//2),
                (center_x + circle_radius//2, center_y),
                (center_x - circle_radius//2 + play_offset, center_y + circle_radius//2)
            ]
            overlay_draw.polygon(triangle_points, fill=(255, 255, 255, 230))
            
            img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
            
            if duration > 0:
                mins = int(duration) // 60
                secs = int(duration) % 60
                duration_text = f"{mins}:{secs:02d}"
                
                text_width = 40  
                text_height = 14
                margin = 5
                overlay_draw = ImageDraw.Draw(img)
                overlay_draw.rectangle(
                    (target_width - text_width - margin, 
                     target_height - text_height - margin,
                     target_width - margin,
                     target_height - margin),
                    fill=(0, 0, 0, 200)
                )
                try:
                    font = ImageFont.truetype("arial.ttf", 12)
                except:
                    font = ImageFont.load_default()
                overlay_draw.text(
                    (target_width - text_width - margin + 5, 
                     target_height - text_height - margin + 1),
                    duration_text,
                    fill=(255, 255, 255),
                    font=font
                )
            
            img.save(thumbnail_path)
            
            video.release()
            
            logging.info(f"Created video thumbnail: {thumbnail_path}")
            return os.path.relpath(thumbnail_path, os.getcwd())
                
        except Exception as e:
            logging.error(f"Error creating video thumbnail: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return self.create_generic_thumbnail(thumbnail_path, "ERROR")
    
    def create_generic_thumbnail(self, thumbnail_path, status_text="VIDEO"):
        width, height = 320, 180
        img = Image.new('RGB', (width, height), color=(40, 40, 40))
        
        draw = ImageDraw.Draw(img)
        
        center_x, center_y = width // 2, height // 2
        play_button_size = min(width, height) // 3
        play_x = center_x - play_button_size // 4
        
        triangle_points = [
            (play_x, center_y - play_button_size // 2),
            (play_x + play_button_size, center_y),
            (play_x, center_y + play_button_size // 2)
        ]
        draw.polygon(triangle_points, fill=(200, 200, 200))
        
        try:
            font = ImageFont.truetype("arial.ttf", 14)
        except:
            font = ImageFont.load_default()
            
        text_width = draw.textlength(status_text, font=font)
        draw.text((center_x - text_width/2, height - 30), status_text, fill=(200, 200, 200), font=font)
        
        img.save(thumbnail_path)
        
        return os.path.relpath(thumbnail_path, os.getcwd())

    def scroll_position_changed(self, value):
        scrollbar = self.chat_area.verticalScrollBar()
        
        max_value = scrollbar.maximum()
        
        scroll_threshold = 30
        self.should_auto_scroll = (max_value - value) <= scroll_threshold
        
        self.last_scroll_position = value
        
    def append_to_chat(self, text, force_scroll=False):
        scrollbar = self.chat_area.verticalScrollBar()
        was_at_bottom = self.should_auto_scroll
        current_pos = scrollbar.value()
        
        self.chat_area.append(text)
        
        if force_scroll or was_at_bottom:
            QTimer.singleShot(10, lambda: scrollbar.setValue(scrollbar.maximum()))
        else:
            QTimer.singleShot(10, lambda: scrollbar.setValue(current_pos)) 

    def toggle_updates(self, state):
        if self.current_channel:
            self.paused_updates_channel[self.current_channel] = (state == Qt.CheckState.Checked.value)
        elif self.current_friend:
            self.paused_updates_friend[self.current_friend] = (state == Qt.CheckState.Checked.value)

    def find_available_base_port(self):
        base = random.randint(8000, 9000)
        
        client_port = getattr(self, 'port', None)
        
        for offset in range(100):  
            port = base + offset
            
            if client_port and port == client_port:
                continue
                
            if port in [8080, 8888, 9090]:  
                continue
                
            try:
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_socket.settimeout(0.5)  
                test_socket.bind(('localhost', port))
                test_socket.close()
                logging.info(f"Found available base port: {port}")
                return port
            except socket.error:
                continue
            except Exception as e:
                logging.error(f"Error checking port {port}: {str(e)}")
        
        logging.warning("Couldn't find available port in primary range, trying secondary range")
        return random.randint(10000, 60000)

    def create_tray_icon(self):
        settings = SettingsHandler()
        privacy_settings = settings.get_privacy_settings()
        
        if not privacy_settings.get("enable_notifications", True):
            return
            
        self.tray_icon = QSystemTrayIcon(self)
        try:
            icon_set = False
            if os.path.exists("icon.png"):
                self.tray_icon.setIcon(QIcon("icon.png"))
                icon_set = True
            if not icon_set:
                self.tray_icon.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_MessageBoxInformation))
        except Exception as e:
            logging.error(f"Lỗi khi thiết lập icon: {str(e)}")
            try:
                self.tray_icon.setIcon(QIcon.fromTheme("dialog-information"))
            except:
                logging.error("Không thể thiết lập bất kỳ icon nào cho system tray")
        
        tray_menu = QMenu()
        show_action = tray_menu.addAction("Show")
        show_action.triggered.connect(self.show)
        
        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(self.quit_application)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()