import socket
import threading
import json
import os
import base64
import logging
import time
from datetime import datetime
from src.client.system_logger import SystemLogger
import struct
import random

class MediaTransferNode:
    def __init__(self, user_id, username, media_port=None):
        self.user_id = user_id
        self.username = username
        self.is_running = False
        self.server_socket = None
        
        self.media_port = media_port if media_port else self._find_available_port(9000, 9999)
        
        self.peer_connections = {}  # {user_id: (address, port)}
        
        self.logger = SystemLogger(log_dir="logs/media_transfers")
        self.logger.log(f"Initialized media transfer node for user {username} (ID: {user_id}) on port {self.media_port}")
        
        self.media_cache = {}  # {media_id: {"path": path, "type": type, "size": size}}
        
        self.media_received_callbacks = []
        
    def _find_available_port(self, start_range, end_range):
        reserved_ports = set()
        
        reserved_ports.update([8080, 8888, 9090, 3306, 5432])
        
        tried_ports = set()
        
        for _ in range(50):  # Try 50 random ports first
            port = random.randint(start_range, end_range)
            
            if port in tried_ports or port in reserved_ports:
                continue
                
            tried_ports.add(port)
            
            try:
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_socket.settimeout(0.5)  # Short timeout
                test_socket.bind(('0.0.0.0', port))
                test_socket.close()
                logging.info(f"Found available media transfer port: {port}")
                return port
            except socket.error:
                continue
                
        for port in range(start_range, end_range + 1):
            if port in tried_ports or port in reserved_ports:
                continue
                
            tried_ports.add(port)
            
            try:
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_socket.settimeout(0.5)  # Short timeout
                test_socket.bind(('0.0.0.0', port))
                test_socket.close()
                logging.info(f"Found available media transfer port: {port}")
                return port
            except socket.error:
                continue
                
        logging.warning("Could not find available port in specified range, using random high port")
        return random.randint(10000, 60000)
        
    def start(self):
        if self.is_running:
            return
            
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.bind(('0.0.0.0', self.media_port))
            self.server_socket.listen(10)  # Allow up to 10 pending connections
            
            self.server_socket.settimeout(1.0)
            
            self.is_running = True
            
            self.logger.log_connection(
                "0.0.0.0", 
                self.media_port, 
                "start_media_node", 
                "success"
            )
            
            self.accept_thread = threading.Thread(target=self._accept_connections, daemon=True)
            self.accept_thread.start()
            
            return True
        except Exception as e:
            logging.error(f"Error starting media transfer node: {str(e)}")
            self.logger.log_connection(
                "0.0.0.0", 
                self.media_port, 
                "start_media_node", 
                f"error: {str(e)}"
            )
            return False
            
    def _accept_connections(self):
        while self.is_running:
            try:
                client_socket, address = self.server_socket.accept()
                
                self.logger.log_connection(
                    address[0],
                    address[1],
                    "peer_connect",
                    "connected"
                )
                
                threading.Thread(
                    target=self._handle_peer,
                    args=(client_socket, address),
                    daemon=True
                ).start()
                
            except socket.timeout:
                continue
            except Exception as e:
                if self.is_running:  # Only log if we're still supposed to be running
                    logging.error(f"Error accepting media connection: {str(e)}")
                    
    def _handle_peer(self, client_socket, address):
        try:
            client_socket.settimeout(10.0)  # Set a longer timeout for the initial message
            auth_data = client_socket.recv(1024)
            auth_json = json.loads(auth_data.decode('utf-8'))
            
            if 'user_id' not in auth_json or 'username' not in auth_json:
                self.logger.log(f"Peer {address} did not provide proper authentication")
                client_socket.close()
                return
                
            peer_id = auth_json['user_id']
            peer_username = auth_json['username']
            
            self.peer_connections[peer_id] = (address[0], address[1], client_socket)
            
            self.logger.log_connection(
                address[0],
                address[1],
                "peer_authenticate",
                f"User ID: {peer_id}, Username: {peer_username}"
            )
            
            response = {
                "status": "authenticated",
                "user_id": self.user_id,
                "username": self.username,
                "timestamp": datetime.now().isoformat()
            }
            client_socket.send(json.dumps(response).encode('utf-8'))
            
            client_socket.settimeout(1.0)
            
            buffer = b''
            message_size = None
            
            while self.is_running:
                try:
                    if message_size is None:
                        header_data = client_socket.recv(8)
                        if not header_data:
                            break
                            
                        message_size = struct.unpack('!Q', header_data)[0]
                        
                    chunk = client_socket.recv(min(4096, message_size - len(buffer)))
                    if not chunk:
                        break
                        
                    buffer += chunk
                    
                    if len(buffer) == message_size:
                        message = json.loads(buffer.decode('utf-8'))
                        self._handle_peer_message(message, peer_id, peer_username)
                        
                        buffer = b''
                        message_size = None
                        
                except socket.timeout:
                    continue
                except Exception as e:
                    logging.error(f"Error handling peer {peer_id}: {str(e)}")
                    break
                    
            if peer_id in self.peer_connections:
                del self.peer_connections[peer_id]
                
            self.logger.log_connection(
                address[0],
                address[1],
                "peer_disconnect",
                f"User ID: {peer_id}, Username: {peer_username}"
            )
            
        except Exception as e:
            logging.error(f"Error in peer handler for {address}: {str(e)}")
        finally:
            client_socket.close()
            
    def _handle_peer_message(self, message, peer_id, peer_username):
        if 'action' not in message:
            return
            
        action = message['action']
        
        if action == 'send_media':
            self._handle_received_media(message, peer_id, peer_username)
        elif action == 'request_media':
            self._handle_media_request(message, peer_id)
            
    def _handle_received_media(self, message, peer_id, peer_username):
        try:
            media_id = message.get('media_id')
            media_type = message.get('media_type')
            media_name = message.get('media_name')
            media_data_b64 = message.get('media_data')
            target_id = message.get('target_id')  # User or channel ID
            is_channel = message.get('is_channel', False)
            
            if target_id != self.user_id and not is_channel:
                return
                
            if not all([media_id, media_type, media_name, media_data_b64]):
                self.logger.log(f"Received incomplete media data from peer {peer_id}")
                return
                
            media_data = base64.b64decode(media_data_b64)
            
            base_dir = os.path.join(os.getcwd(), "media")
            if not os.path.exists(base_dir):
                os.makedirs(base_dir)
                
            type_dir = os.path.join(base_dir, media_type + "s")  # "images" or "videos"
            if not os.path.exists(type_dir):
                os.makedirs(type_dir)
                
            filename = f"{os.path.splitext(media_name)[0]}_{media_id}{os.path.splitext(media_name)[1]}"
            media_path = os.path.join(type_dir, filename)
            
            with open(media_path, 'wb') as f:
                f.write(media_data)
                
            self.logger.log_data_transaction(
                "receive",
                "p2p", 
                self.media_port,
                f"media_{media_type}",
                len(media_data)
            )
            
            self.media_cache[media_id] = {
                "path": os.path.relpath(media_path, os.getcwd()),
                "type": media_type,
                "size": len(media_data),
                "from_user_id": peer_id,
                "from_username": peer_username
            }
            
            message_data = {
                "media_id": media_id,
                "media_path": os.path.relpath(media_path, os.getcwd()),
                "media_type": media_type,
                "media_name": media_name,
                "from_user_id": peer_id,
                "from_username": peer_username,
                "target_id": target_id,
                "is_channel": is_channel,
                "content": message.get('content', '')  # Optional text content
            }
            
            for callback in self.media_received_callbacks:
                callback(message_data)
                
        except Exception as e:
            logging.error(f"Error handling received media: {str(e)}")
            
    def _handle_media_request(self, message, peer_id):
        try:
            media_id = message.get('media_id')
            
            if media_id in self.media_cache:
                media_info = self.media_cache[media_id]
                media_path = media_info['path']
                
                if not os.path.exists(media_path):
                    return
                    
                with open(media_path, 'rb') as f:
                    media_data = f.read()
                    
                media_data_b64 = base64.b64encode(media_data).decode('utf-8')
                
                self.send_media_to_peer(
                    peer_id,
                    media_id,
                    media_info['type'],
                    os.path.basename(media_path),
                    media_data_b64,
                    message.get('target_id'),
                    message.get('is_channel', False),
                    message.get('content', '')
                )
                
        except Exception as e:
            logging.error(f"Error handling media request: {str(e)}")
            
    def send_media(self, media_path, media_type, target_id, is_channel=False, content=''):
        try:
            import uuid
            media_id = str(uuid.uuid4())
            
            media_name = os.path.basename(media_path)
            
            self.media_cache[media_id] = {
                "path": media_path,
                "type": media_type,
                "size": os.path.getsize(media_path)
            }
            
            if is_channel:
                for peer_id, conn_info in list(self.peer_connections.items()):
                    with open(media_path, 'rb') as f:
                        media_data = f.read()
                        
                    media_data_b64 = base64.b64encode(media_data).decode('utf-8')
                    
                    self.send_media_to_peer(
                        peer_id,
                        media_id,
                        media_type,
                        media_name,
                        media_data_b64,
                        target_id,
                        is_channel,
                        content
                    )
            else:
                if target_id in self.peer_connections:
                    with open(media_path, 'rb') as f:
                        media_data = f.read()
                        
                    media_data_b64 = base64.b64encode(media_data).decode('utf-8')
                    
                    self.send_media_to_peer(
                        target_id,
                        media_id,
                        media_type,
                        media_name,
                        media_data_b64,
                        target_id,
                        is_channel,
                        content
                    )
                else:
                    logging.warning(f"Peer {target_id} not connected, cannot send media directly")
                    return None
                    
            return {
                "media_id": media_id,
                "media_path": media_path,
                "media_type": media_type,
                "media_name": media_name
            }
            
        except Exception as e:
            logging.error(f"Error sending media: {str(e)}")
            return None
            
    def send_media_to_peer(self, peer_id, media_id, media_type, media_name, media_data_b64, target_id, is_channel, content=''):
        if peer_id not in self.peer_connections:
            logging.warning(f"Peer {peer_id} not connected, cannot send media")
            return False
            
        try:
            message = {
                "action": "send_media",
                "media_id": media_id,
                "media_type": media_type,
                "media_name": media_name,
                "media_data": media_data_b64,
                "target_id": target_id,
                "is_channel": is_channel,
                "content": content,
                "sender_id": self.user_id,
                "sender_username": self.username,
                "timestamp": datetime.now().isoformat()
            }
            
            message_json = json.dumps(message)
            message_bytes = message_json.encode('utf-8')
            
            peer_socket = self.peer_connections[peer_id][2]
            
            header = struct.pack('!Q', len(message_bytes))
            peer_socket.sendall(header + message_bytes)
            
            self.logger.log_data_transaction(
                "send",
                self.peer_connections[peer_id][0],
                self.peer_connections[peer_id][1],
                f"media_{media_type}",
                len(media_data_b64)
            )
            
            return True
            
        except Exception as e:
            logging.error(f"Error sending media to peer {peer_id}: {str(e)}")
            
            if peer_id in self.peer_connections:
                try:
                    self.peer_connections[peer_id][2].close()
                except:
                    pass
                del self.peer_connections[peer_id]
                
            return False
            
    def connect_to_peer(self, peer_id, peer_username, peer_address, peer_port):
        if peer_id in self.peer_connections:
            logging.info(f"Already connected to peer {peer_id}")
            return True
            
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(10.0)  # 10 seconds timeout for connection
            
            client_socket.connect((peer_address, peer_port))
            
            auth_message = {
                "user_id": self.user_id,
                "username": self.username,
                "timestamp": datetime.now().isoformat()
            }
            client_socket.send(json.dumps(auth_message).encode('utf-8'))
            
            response_data = client_socket.recv(1024)
            response = json.loads(response_data.decode('utf-8'))
            
            if response.get('status') != 'authenticated':
                logging.error(f"Failed to authenticate with peer {peer_id}")
                client_socket.close()
                return False
                
            self.peer_connections[peer_id] = (peer_address, peer_port, client_socket)
            
            self.logger.log_connection(
                peer_address,
                peer_port,
                "peer_connect",
                f"Connected to {peer_username} (ID: {peer_id})"
            )
            
            threading.Thread(
                target=self._handle_peer_connection,
                args=(client_socket, (peer_address, peer_port), peer_id, peer_username),
                daemon=True
            ).start()
            
            return True
            
        except Exception as e:
            logging.error(f"Error connecting to peer {peer_id}: {str(e)}")
            return False
            
    def _handle_peer_connection(self, client_socket, address, peer_id, peer_username):
        try:
            client_socket.settimeout(1.0)
            
            buffer = b''
            message_size = None
            
            while self.is_running:
                try:
                    if message_size is None:
                        header_data = client_socket.recv(8)
                        if not header_data:
                            break
                            
                        message_size = struct.unpack('!Q', header_data)[0]
                        
                    chunk = client_socket.recv(min(4096, message_size - len(buffer)))
                    if not chunk:
                        break
                        
                    buffer += chunk
                    
                    if len(buffer) == message_size:
                        message = json.loads(buffer.decode('utf-8'))
                        self._handle_peer_message(message, peer_id, peer_username)
                        
                        buffer = b''
                        message_size = None
                        
                except socket.timeout:
                    continue
                except Exception as e:
                    logging.error(f"Error handling messages from peer {peer_id}: {str(e)}")
                    break
                    
            if peer_id in self.peer_connections:
                del self.peer_connections[peer_id]
                
            self.logger.log_connection(
                address[0],
                address[1],
                "peer_disconnect",
                f"Disconnected from {peer_username} (ID: {peer_id})"
            )
            
        except Exception as e:
            logging.error(f"Error in peer connection handler for {peer_id}: {str(e)}")
        finally:
            client_socket.close()
            
    def register_media_received_callback(self, callback):
        if callback not in self.media_received_callbacks:
            self.media_received_callbacks.append(callback)
            
    def stop(self):
        if not self.is_running:
            return
            
        self.is_running = False
        
        for peer_id, (_, _, socket) in list(self.peer_connections.items()):
            try:
                socket.close()
            except:
                pass
                
        self.peer_connections.clear()
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
                
        self.logger.log_connection(
            "0.0.0.0",
            self.media_port,
            "stop_media_node",
            "success"
        )
        
        self.logger.close()
        
        logging.info(f"Stopped media transfer node on port {self.media_port}") 