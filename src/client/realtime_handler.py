from PySide6.QtCore import QObject, Signal
import socket
import threading
import json
import logging
from typing import Dict, List, Optional

class RealtimeHandler(QObject):
    # Signals
    friend_request_received = Signal(dict) 
    friend_request_accepted = Signal(dict)  
    friend_request_rejected = Signal(dict)  
    message_received = Signal(dict)  
    status_changed = Signal(dict)  
    
    def __init__(self, port: int):
        super().__init__()
        self.port = port
        self.connections: Dict[int, socket.socket] = {}  # user_id -> socket
        self.listen_thread = None
        self.running = False
        
    def start(self):
        self.running = True
        self.listen_thread = threading.Thread(target=self._listen_for_connections)
        self.listen_thread.daemon = True
        self.listen_thread.start()
        
    def stop(self):
        self.running = False
        for sock in self.connections.values():
            try:
                sock.close()
            except:
                pass
        self.connections.clear()
        
    def _listen_for_connections(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('0.0.0.0', self.port))
        server_socket.listen(5)
        
        while self.running:
            try:
                client_socket, address = server_socket.accept()
                threading.Thread(target=self._handle_connection, args=(client_socket,)).start()
            except:
                break
                
        server_socket.close()
        
    def _handle_connection(self, sock: socket.socket):
        try:
            while self.running:
                data = sock.recv(4096)
                if not data:
                    break
                    
                message = json.loads(data.decode())
                self._process_message(message)
        except:
            pass
        finally:
            sock.close()
            
    def _process_message(self, message: dict):
        message_type = message.get("type")
        if not message_type:
            return
            
        if message_type == "friend_request":
            self.friend_request_received.emit(message)
        elif message_type == "friend_request_accepted":
            self.friend_request_accepted.emit(message)
        elif message_type == "friend_request_rejected":
            self.friend_request_rejected.emit(message)
        elif message_type == "message":
            self.message_received.emit(message)
        elif message_type == "status_change":
            self.status_changed.emit(message)
            
    def connect_to_user(self, user_id: int, host: str, port: int) -> bool:
        if user_id in self.connections:
            return True
            
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, port))
            self.connections[user_id] = sock
            return True
        except Exception as e:
            logging.error(f"Error connecting to user {user_id}: {str(e)}")
            return False
            
    def send_message(self, user_id: int, message: dict) -> bool:
        if user_id not in self.connections:
            return False
            
        try:
            sock = self.connections[user_id]
            sock.send(json.dumps(message).encode())
            return True
        except Exception as e:
            logging.error(f"Error sending message to user {user_id}: {str(e)}")
            return False
            
    def broadcast_message(self, message: dict, exclude_user_ids: List[int] = None):
        if exclude_user_ids is None:
            exclude_user_ids = []
            
        for user_id, sock in self.connections.items():
            if user_id not in exclude_user_ids:
                try:
                    sock.send(json.dumps(message).encode())
                except:
                    pass 