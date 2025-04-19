from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtCore import QTimer
from database.models import ChannelMembership, Message, FriendRequest, Channel
from database.config import SessionLocal
import logging
from datetime import datetime, timedelta
from PySide6.QtGui import QIcon
from src.client.settings_handler import SettingsHandler

class NotificationHandler:
    def __init__(self, current_user_id):
        self.current_user_id = current_user_id
        self.tray_icon = None
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self.check_notifications)
        self.last_check = datetime.utcnow()
        self.settings = SettingsHandler()
        
    def init_tray_icon(self):
        if not self.tray_icon:
            self.tray_icon = QSystemTrayIcon()
            self.tray_icon.setIcon(QIcon("icon.png"))  # You'll need to provide an icon
            
            menu = QMenu()
            show_action = menu.addAction("Show")
            show_action.triggered.connect(self.show_window)
            quit_action = menu.addAction("Quit")
            quit_action.triggered.connect(self.quit_application)
            
            self.tray_icon.setContextMenu(menu)
            self.tray_icon.show()
    
    def start_checking(self, interval=30000):  # Check every 30 seconds
        self.check_timer.start(interval)
    
    def stop_checking(self):
        self.check_timer.stop()
    
    def check_notifications(self):
        try:
            privacy_settings = self.settings.get_privacy_settings()
            if not privacy_settings.get("enable_notifications", True):
                return
                
            new_messages = self.get_new_messages()
            if new_messages:
                self.show_message_notification(new_messages)
            
            new_requests = self.get_new_friend_requests()
            if new_requests:
                self.show_friend_request_notification(new_requests)
            
            new_invites = self.get_new_channel_invites()
            if new_invites:
                self.show_channel_invite_notification(new_invites)
            
            self.last_check = datetime.utcnow()
            
        except Exception as e:
            logging.error(f"Error checking notifications: {str(e)}")
    
    def get_new_messages(self):
        db = SessionLocal()
        try:
            channels = db.query(Channel).join(Channel.members).filter(
                ChannelMembership.user_id == self.current_user_id
            ).all()
            
            channel_ids = [c.id for c in channels]
            
            messages = db.query(Message).filter(
                Message.channel_id.in_(channel_ids),
                Message.sender_id != self.current_user_id,
                Message.created_at > self.last_check
            ).all()
            
            return [{
                'id': m.id,
                'content': m.content,
                'sender': m.sender.username,
                'channel': m.channel.name,
                'timestamp': m.created_at
            } for m in messages]
            
        finally:
            db.close()
    
    def get_new_friend_requests(self):
        db = SessionLocal()
        try:
            requests = db.query(FriendRequest).filter(
                FriendRequest.receiver_id == self.current_user_id,
                FriendRequest.created_at > self.last_check
            ).all()
            
            return [{
                'id': r.id,
                'sender': r.sender.username,
                'timestamp': r.created_at
            } for r in requests]
            
        finally:
            db.close()
    
    def get_new_channel_invites(self):
        db = SessionLocal()
        try:
            return []
            
        finally:
            db.close()
    
    def show_message_notification(self, messages):
        if not self.tray_icon:
            return
            
        privacy_settings = self.settings.get_privacy_settings()
        if not privacy_settings.get("enable_notifications", True):
            return
        
        channel_messages = {}
        for msg in messages:
            if msg['channel'] not in channel_messages:
                channel_messages[msg['channel']] = []
            channel_messages[msg['channel']].append(msg)
        
        for channel, msgs in channel_messages.items():
            sender_names = set(msg['sender'] for msg in msgs)
            sender_list = ", ".join(sender_names)
            
            if len(msgs) == 1:
                message = f"New message from {sender_list} in {channel}"
            else:
                message = f"{len(msgs)} new messages from {sender_list} in {channel}"
            
            self.tray_icon.showMessage(
                "New Messages",
                message,
                QSystemTrayIcon.MessageIcon.Information,
                5000  # Show for 5 seconds
            )
    
    def show_friend_request_notification(self, requests):
        if not self.tray_icon:
            return
            
        privacy_settings = self.settings.get_privacy_settings()
        if not privacy_settings.get("enable_notifications", True):
            return
        
        sender_names = ", ".join(r['sender'] for r in requests)
        
        if len(requests) == 1:
            message = f"New friend request from {sender_names}"
        else:
            message = f"New friend requests from {sender_names}"
        
        self.tray_icon.showMessage(
            "Friend Requests",
            message,
            QSystemTrayIcon.MessageIcon.Information,
            5000
        )
    
    def show_channel_invite_notification(self, invites):
        if not self.tray_icon:
            return
            
        privacy_settings = self.settings.get_privacy_settings()
        if not privacy_settings.get("enable_notifications", True):
            return
        
        channel_names = ", ".join(i['channel'] for i in invites)
        
        if len(invites) == 1:
            message = f"New channel invite to {channel_names}"
        else:
            message = f"New channel invites to {channel_names}"
        
        self.tray_icon.showMessage(
            "Channel Invites",
            message,
            QSystemTrayIcon.MessageIcon.Information,
            5000
        )
    
    def show_window(self):
        pass
    
    def quit_application(self):
        pass 