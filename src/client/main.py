import sys
import socket
import threading
import json
import logging
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                           QHBoxLayout, QLabel, QLineEdit, QPushButton,
                           QTextEdit, QListWidget, QStackedWidget, QMessageBox)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon, QPixmap
from src.client.config import *

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class NetworkThread(QThread):
    message_received = Signal(dict)
    
    def __init__(self, client_socket):
        super().__init__()
        self.client_socket = client_socket
        self.running = True
        
    def run(self):
        while self.running:
            try:
                data = self.client_socket.recv(4096).decode('utf-8')
                if not data:
                    break
                message = json.loads(data)
                self.message_received.emit(message)
            except Exception as e:
                logging.error(f"Error receiving message: {str(e)}")
                break
    
    def stop(self):
        self.running = False

class ChatClient(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hybrid ParadigmChat Chat")
        self.setGeometry(100, 100, WINDOW_WIDTH, WINDOW_HEIGHT)
        
        self.server_socket = None
        self.p2p_socket = None
        self.network_thread = None
        self.peer_list = {}
        
        self.init_ui()
        
        self.connect_to_server()
        
    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)
        
        left_sidebar = QWidget()
        left_sidebar.setFixedWidth(250)
        left_layout = QVBoxLayout(left_sidebar)
        
        # Channel list
        self.channel_list = QListWidget()
        self.channel_list.itemClicked.connect(self.channel_selected)
        left_layout.addWidget(QLabel("Channels"))
        left_layout.addWidget(self.channel_list)
        
        # Friend list
        self.friend_list = QListWidget()
        self.friend_list.itemClicked.connect(self.friend_selected)
        left_layout.addWidget(QLabel("Friends"))
        left_layout.addWidget(self.friend_list)
        
        main_content = QWidget()
        main_content_layout = QVBoxLayout(main_content)
        
        # Chat
        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        main_content_layout.addWidget(self.chat_area)
        
        message_input_layout = QHBoxLayout()
        self.message_input = QLineEdit()
        self.message_input.returnPressed.connect(self.send_message)
        send_button = QPushButton("Send")
        send_button.clicked.connect(self.send_message)
        message_input_layout.addWidget(self.message_input)
        message_input_layout.addWidget(send_button)
        main_content_layout.addLayout(message_input_layout)
        
        layout.addWidget(left_sidebar)
        layout.addWidget(main_content)
        
        self.create_menu_bar()
        
    def create_menu_bar(self):
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu("File")
        create_channel_action = file_menu.addAction("Create Channel")
        create_channel_action.triggered.connect(self.create_channel)
        
        settings_menu = menubar.addMenu("Settings")
        theme_action = settings_menu.addAction("Toggle Theme")
        theme_action.triggered.connect(self.toggle_theme)
        
    def connect_to_server(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.connect((SERVER_HOST, SERVER_PORT))
            
            self.network_thread = NetworkThread(self.server_socket)
            self.network_thread.message_received.connect(self.handle_message)
            self.network_thread.start()
            
            self.submit_peer_info()
            
        except Exception as e:
            QMessageBox.critical(self, "Connection Error", f"Failed to connect to server: {str(e)}")
            logging.error(f"Connection error: {str(e)}")
    
    def submit_peer_info(self):
        message = {
            'type': 'submit_info',
            'peer_id': f"{CLIENT_HOST}:{DEFAULT_PORT}",
            'ip': CLIENT_HOST,
            'port': DEFAULT_PORT,
            'username': "User" 
        }
        self.send_to_server(message)
    
    def send_to_server(self, message):
        try:
            self.server_socket.send(json.dumps(message).encode('utf-8'))
        except Exception as e:
            logging.error(f"Error sending message to server: {str(e)}")
    
    def handle_message(self, message):
        message_type = message.get('type')
        
        if message_type == 'peer_list':
            self.update_peer_list(message['peers'])
        elif message_type == 'text_message':
            self.display_message(message)
        elif message_type == 'p2p_connect':
            self.handle_p2p_connection(message['peer_info'])
    
    def update_peer_list(self, peers):
        self.peer_list = peers
        self.friend_list.clear()
        for peer_id, info in peers.items():
            self.friend_list.addItem(f"{peer_id} ({info['status']})")
    
    def display_message(self, message):
        self.chat_area.append(f"{message['sender']}: {message['content']}")
    
    def send_message(self):
        message_text = self.message_input.text()
        if message_text:
            message = {
                'type': 'text_message',
                'content': message_text,
                'sender': "User",  
                'channel_id': self.current_channel_id
            }
            self.send_to_server(message)
            self.message_input.clear()
    
    def channel_selected(self, item):
        self.current_channel_id = item.data(Qt.ItemDataRole.UserRole)
        self.load_channel_messages()
    
    def friend_selected(self, item):
        peer_id = item.text().split()[0]
        if peer_id in self.peer_list:
            self.initiate_p2p_connection(peer_id)
    
    def create_channel(self):
        pass
    
    def toggle_theme(self):
        pass
    
    def load_channel_messages(self):
        pass
    
    def initiate_p2p_connection(self, peer_id):
        if peer_id in self.peer_list:
            peer_info = self.peer_list[peer_id]
            message = {
                'type': 'file_message',
                'target_peer': peer_id
            }
            self.send_to_server(message)
    
    def handle_p2p_connection(self, peer_info):
        pass
    
    def closeEvent(self, event):
        if self.network_thread:
            self.network_thread.stop()
        if self.server_socket:
            self.server_socket.close()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    client = ChatClient()
    client.show()
    sys.exit(app.exec()) 