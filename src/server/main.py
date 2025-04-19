import socket
import threading
import json
import logging
import signal
import sys
from datetime import datetime
from src.server.config import *
from src.database.models import *
from src.database.config import SessionLocal, engine

Base.metadata.create_all(bind=engine)

logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

class ChatServer:
    def __init__(self):
        self.server_socket = None
        self.running = False
        self.clients = {} 
        self.channels = {} 
        self.p2p_peers = {}  
        
    def start(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((SERVER_HOST, SERVER_PORT))
            self.server_socket.listen(MAX_CONNECTIONS)
            self.running = True
            
            logging.info(f"Server started on {SERVER_HOST}:{SERVER_PORT}")
            
            signal.signal(signal.SIGINT, self.signal_handler)
            
            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    logging.info(f"New connection from {address}")
                    
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, address)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    
                    self.clients[address] = {
                        'socket': client_socket,
                        'thread': client_thread
                    }
                except socket.error as e:
                    if self.running:  # Only log if we're not shutting down
                        logging.error(f"Error accepting connection: {e}")
        except Exception as e:
            logging.error(f"Server error: {e}")
        finally:
            self.stop()
            
    def stop(self):
        logging.info("Shutting down server...")
        self.running = False
        
        for client_info in self.clients.values():
            try:
                client_info['socket'].close()
            except:
                pass
                
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
                
        logging.info("Server shutdown complete")
        sys.exit(0)
        
    def signal_handler(self, signum, frame):
        logging.info("Received shutdown signal")
        self.stop()

    def handle_client(self, client_socket, address):
        try:
            while self.running:
                data = client_socket.recv(BUFFER_SIZE)
                if not data:
                    break
                    
                message = data.decode()
                logging.info(f"Received from {address}: {message}")
                
                if message.strip().lower() == "shutdown":
                    if address[0] == "127.0.0.1":
                        logging.info("Received shutdown command from localhost")
                        self.stop()
                        return
                    else:
                        logging.warning(f"Shutdown attempt from {address} rejected")
                        client_socket.send("Shutdown command rejected: Only localhost can shutdown the server".encode())
                        continue
                
                client_socket.send(data)
                
        except Exception as e:
            logging.error(f"Error handling client {address}: {e}")
        finally:
            if address in self.clients:
                del self.clients[address]
            client_socket.close()
            logging.info(f"Client {address} disconnected")

    def process_message(self, client_socket, message):
        message_type = message.get('type')
        
        if message_type == 'submit_info':
            self.handle_submit_info(client_socket, message)
        elif message_type == 'get_list':
            self.handle_get_list(client_socket)
        elif message_type == 'text_message':
            self.handle_text_message(client_socket, message)
        elif message_type == 'file_message':
            self.handle_file_message(client_socket, message)
        elif message_type == 'create_channel':
            self.handle_create_channel(client_socket, message)
        elif message_type == 'join_channel':
            self.handle_join_channel(client_socket, message)

    def handle_submit_info(self, client_socket, message):
        peer_info = {
            'ip': message['ip'],
            'port': message['port'],
            'status': 'online'
        }
        self.p2p_peers[message['peer_id']] = peer_info
        self.clients[client_socket] = {
            'username': message['username'],
            'ip': message['ip'],
            'port': message['port']
        }
        logging.info(f"New peer connected: {message['peer_id']}")

    def handle_get_list(self, client_socket):
        peer_list = {
            'type': 'peer_list',
            'peers': self.p2p_peers
        }
        client_socket.send(json.dumps(peer_list).encode('utf-8'))

    def handle_text_message(self, client_socket, message):
        db = SessionLocal()
        try:
            new_message = Message(
                content=message['content'],
                sender_id=message['sender_id'],
                channel_id=message['channel_id']
            )
            db.add(new_message)
            db.commit()
            
            channel_id = message['channel_id']
            if channel_id in self.channels:
                for member in self.channels[channel_id]['members']:
                    if member != client_socket:
                        member.send(json.dumps(message).encode('utf-8'))
        finally:
            db.close()

    def handle_file_message(self, client_socket, message):
        target_peer = message['target_peer']
        if target_peer in self.p2p_peers:
            peer_info = self.p2p_peers[target_peer]
            response = {
                'type': 'p2p_connect',
                'peer_info': peer_info
            }
            client_socket.send(json.dumps(response).encode('utf-8'))

    def handle_create_channel(self, client_socket, message):
        db = SessionLocal()
        try:
            new_channel = Channel(
                name=message['name'],
                description=message.get('description', ''),
                owner_id=message['owner_id'],
                is_private=message.get('is_private', False),
                allow_visitors=message.get('allow_visitors', True)
            )
            db.add(new_channel)
            db.commit()
            
            self.channels[new_channel.id] = {
                'name': new_channel.name,
                'members': {client_socket}
            }
            
            response = {
                'type': 'channel_created',
                'channel_id': new_channel.id
            }
            client_socket.send(json.dumps(response).encode('utf-8'))
        finally:
            db.close()

    def handle_join_channel(self, client_socket, message):
        channel_id = message['channel_id']
        if channel_id in self.channels:
            self.channels[channel_id]['members'].add(client_socket)
            response = {
                'type': 'channel_joined',
                'channel_id': channel_id
            }
            client_socket.send(json.dumps(response).encode('utf-8'))

    def remove_client(self, client_socket):
        if client_socket in self.clients:
            username = self.clients[client_socket]['username']
            del self.clients[client_socket]
            
            for channel in self.channels.values():
                if client_socket in channel['members']:
                    channel['members'].remove(client_socket)
            
            logging.info(f"Client disconnected: {username}")

if __name__ == "__main__":
    server = ChatServer()
    server.start() 