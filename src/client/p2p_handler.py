import socket
import threading
import json
import os
import logging
from datetime import datetime
from .config import *

class P2PHandler:
    def __init__(self, port=None):
        self.port = port or DEFAULT_PORT
        self.socket = None
        self.connections = {}
        self.running = False
        
    def start(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((CLIENT_HOST, self.port))
            self.socket.listen(MAX_P2P_CONNECTIONS)
            
            self.running = True
            self.listen_thread = threading.Thread(target=self.listen_for_connections)
            self.listen_thread.start()
            
            logging.info(f"P2P handler started on port {self.port}")
            
        except Exception as e:
            logging.error(f"Failed to start P2P handler: {str(e)}")
            raise
    
    def stop(self):
        self.running = False
        if self.socket:
            self.socket.close()
        for conn in self.connections.values():
            conn.close()
        self.connections.clear()
    
    def listen_for_connections(self):
        while self.running:
            try:
                conn, addr = self.socket.accept()
                peer_id = f"{addr[0]}:{addr[1]}"
                self.connections[peer_id] = conn
                
                thread = threading.Thread(
                    target=self.handle_connection,
                    args=(conn, peer_id)
                )
                thread.start()
                
            except Exception as e:
                if self.running:
                    logging.error(f"Error accepting connection: {str(e)}")
    
    def handle_connection(self, conn, peer_id):
        try:
            while self.running:
                data = conn.recv(4096)
                if not data:
                    break
                
                message = json.loads(data.decode('utf-8'))
                self.process_message(conn, peer_id, message)
                
        except Exception as e:
            logging.error(f"Error handling connection from {peer_id}: {str(e)}")
        finally:
            if peer_id in self.connections:
                del self.connections[peer_id]
            conn.close()
    
    def process_message(self, conn, peer_id, message):
        message_type = message.get('type')
        
        if message_type == 'file_transfer_request':
            self.handle_file_transfer_request(conn, peer_id, message)
        elif message_type == 'file_transfer_response':
            self.handle_file_transfer_response(conn, peer_id, message)
        elif message_type == 'file_chunk':
            self.handle_file_chunk(conn, peer_id, message)
    
    def handle_file_transfer_request(self, conn, peer_id, message):
        file_name = message['file_name']
        file_size = message['file_size']
        
        file_ext = os.path.splitext(file_name)[1].lower()
        if file_ext not in ALLOWED_FILE_TYPES:
            response = {
                'type': 'file_transfer_response',
                'status': 'rejected',
                'reason': 'File type not allowed'
            }
            conn.send(json.dumps(response).encode('utf-8'))
            return
        
        if file_size > MAX_FILE_SIZE:
            response = {
                'type': 'file_transfer_response',
                'status': 'rejected',
                'reason': 'File too large'
            }
            conn.send(json.dumps(response).encode('utf-8'))
            return
        
        response = {
            'type': 'file_transfer_response',
            'status': 'accepted'
        }
        conn.send(json.dumps(response).encode('utf-8'))
    
    def handle_file_transfer_response(self, conn, peer_id, message):
        if message['status'] == 'accepted':
            self.send_file(conn, message['file_path'])
        else:
            logging.warning(f"File transfer rejected: {message.get('reason', 'Unknown reason')}")
    
    def handle_file_chunk(self, conn, peer_id, message):
        pass
    
    def send_file(self, conn, file_path):
        try:
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            
            info = {
                'type': 'file_transfer_request',
                'file_name': file_name,
                'file_size': file_size
            }
            conn.send(json.dumps(info).encode('utf-8'))
            
            response = json.loads(conn.recv(4096).decode('utf-8'))
            if response['status'] != 'accepted':
                return
            
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(4096)
                    if not chunk:
                        break
                    
                    message = {
                        'type': 'file_chunk',
                        'data': chunk.hex()
                    }
                    conn.send(json.dumps(message).encode('utf-8'))
            
            logging.info(f"File {file_name} sent successfully")
            
        except Exception as e:
            logging.error(f"Error sending file: {str(e)}")
    
    def connect_to_peer(self, peer_info):
        try:
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.connect((peer_info['ip'], peer_info['port']))
            
            peer_id = f"{peer_info['ip']}:{peer_info['port']}"
            self.connections[peer_id] = conn
            
            thread = threading.Thread(
                target=self.handle_connection,
                args=(conn, peer_id)
            )
            thread.start()
            
            return conn
            
        except Exception as e:
            logging.error(f"Error connecting to peer: {str(e)}")
            return None 