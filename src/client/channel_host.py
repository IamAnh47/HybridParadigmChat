import socket
import threading
import json
import logging
import time
import os
from datetime import datetime
from src.client.system_logger import SystemLogger
from src.database.config import SessionLocal
from src.database.models import Channel, Message, User, ChannelMembership

class ChannelHost: 
    def __init__(self, user_id, base_port=8000):

        self.user_id = user_id
        self.base_port = base_port
        self.host_port = None
        self.is_running = False
        self.server_socket = None
        self.client_connections = {}  # {user_id: (address, port)}
        self.hosted_channels = {}  # {channel_id: port}
        
        # Initialize logger
        self.logger = SystemLogger(log_dir="logs/channel_hosts")
        self.channel_data = {}
        self.network_logger = logging.getLogger('network.channel_host')
    
    def find_available_port(self):
        """Find an available port starting from base_port"""
        port = self.base_port
        while port < self.base_port + 1000: 
            try:
                # Try to bind to the port
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_socket.bind(('localhost', port))
                test_socket.close()
                return port
            except socket.error:
                # Port is in use, try the next one
                port += 1
        
        error_msg = f"Could not find available port after trying 1000 ports starting from {self.base_port}"
        self.network_logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    def start_hosting(self):
        """Start hosting channels owned by the current user"""
        if self.is_running:
            return
        
        # Find an available port
        self.host_port = self.find_available_port()
        self.network_logger.info(f"Starting channel host on port {self.host_port}")
        
        # Log the start of hosting
        self.logger.log_connection("localhost", self.host_port, "start_hosting", "initializing")
        
        # Start the server socket
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.bind(('0.0.0.0', self.host_port))
            self.server_socket.listen(5)
            self.is_running = True
            
            self.logger.log_connection("0.0.0.0", self.host_port, "start_hosting", "success")
            threading.Thread(target=self.accept_connections, daemon=True).start()
            self.load_hosted_channels()
            
            return True
        except Exception as e:
            self.network_logger.error(f"Error starting channel host: {str(e)}")
            self.logger.log_connection("0.0.0.0", self.host_port, "start_hosting", f"error: {str(e)}")
            return False
    
    def load_hosted_channels(self):
        db = SessionLocal()
        try:
            channels = db.query(Channel).filter(Channel.owner_id == self.user_id).all()
            
            for channel in channels:
                # Register channel with this host
                self.hosted_channels[channel.id] = self.host_port
                
                # Log channel hosting
                self.logger.log_channel_hosting(
                    channel.id, 
                    channel.name, 
                    "load", 
                    "success"
                )
                
                # Load channel data for synchronization
                self.load_channel_data(channel.id)
        except Exception as e:
            self.network_logger.error(f"Error loading hosted channels: {str(e)}")
        finally:
            db.close()
    
    def load_channel_data(self, channel_id):
        """Load channel data from database for the specified channel"""
        db = SessionLocal()
        try:
            # Get channel info
            channel = db.query(Channel).get(channel_id)
            if not channel:
                self.network_logger.error(f"Channel {channel_id} not found")
                return
            
            # Get messages
            messages = db.query(Message).filter(
                Message.channel_id == channel_id
            ).order_by(Message.created_at.desc()).limit(100).all()
            
            # Get members
            members = db.query(ChannelMembership).filter(
                ChannelMembership.channel_id == channel_id
            ).all()
            
            # Store data for synchronization
            self.channel_data[channel_id] = {
                "info": {
                    "name": channel.name,
                    "is_private": channel.is_private,
                    "created_at": channel.created_at.isoformat() if channel.created_at else None,
                    "owner_id": channel.owner_id
                },
                "messages": [
                    {
                        "id": msg.id,
                        "content": msg.content,
                        "sender_id": msg.sender_id,
                        "created_at": msg.created_at.isoformat() if msg.created_at else None,
                        "has_media": msg.has_media,
                        "media_type": msg.media_type,
                        "media_path": msg.media_path,
                        "media_name": msg.media_name
                    } for msg in messages
                ],
                "members": [
                    {
                        "user_id": member.user_id,
                        "joined_at": member.joined_at.isoformat() if member.joined_at else None
                    } for member in members
                ]
            }
            
            # Log success
            self.network_logger.info(f"Loaded data for channel {channel_id} ({channel.name})")
            self.logger.log_channel_hosting(
                channel_id, 
                channel.name, 
                "load_data", 
                f"success - {len(messages)} messages, {len(members)} members"
            )
            
        except Exception as e:
            self.network_logger.error(f"Error loading channel {channel_id} data: {str(e)}")
            self.logger.log_channel_hosting(
                channel_id, 
                "unknown", 
                "load_data", 
                f"error: {str(e)}"
            )
        finally:
            db.close()
    
    def accept_connections(self):
        while self.is_running:
            try:
                client_socket, address = self.server_socket.accept()
                
                # Log connection
                self.logger.log_connection(
                    address[0], 
                    address[1], 
                    "accept", 
                    "connected"
                )
                
                # Start a thread to handle this client
                threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, address),
                    daemon=True
                ).start()
                
            except Exception as e:
                if self.is_running:  
                    self.network_logger.error(f"Error accepting connection: {str(e)}")
    
    def handle_client(self, client_socket, address):
        try:
            auth_data = client_socket.recv(1024)
            auth_json = json.loads(auth_data.decode('utf-8'))
            
            if 'user_id' not in auth_json:
                self.network_logger.warning(f"Client {address} did not provide user_id")
                client_socket.close()
                return
            
            user_id = auth_json['user_id']
            self.client_connections[user_id] = (address[0], address[1])
            
            # Log successful authentication
            self.logger.log_connection(
                address[0], 
                address[1], 
                "authenticate", 
                f"success - User ID: {user_id}"
            )
            
            # Send acknowledgment
            response = {
                "status": "authenticated",
                "host_id": self.user_id,
                "timestamp": datetime.now().isoformat()
            }
            client_socket.send(json.dumps(response).encode('utf-8'))
            
            # Handle client requests
            while self.is_running:
                try:
                    client_socket.settimeout(1.0)
                    data = client_socket.recv(8192)
                    
                    if not data:
                        break
                    
                    # Log data reception
                    self.logger.log_data_transaction(
                        "receive",
                        address[0],
                        address[1],
                        "request",
                        len(data)
                    )
                    
                    # Process the request
                    request = json.loads(data.decode('utf-8'))
                    response = self.process_client_request(request, user_id)
                    
                    # Send response
                    response_data = json.dumps(response).encode('utf-8')
                    client_socket.send(response_data)
                    
                    # Log response
                    self.logger.log_data_transaction(
                        "send",
                        address[0],
                        address[1],
                        "response",
                        len(response_data)
                    )
                    
                except socket.timeout:
                    continue
                except json.JSONDecodeError:
                    self.network_logger.warning(f"Received invalid JSON from {address}")
                    continue
                except Exception as e:
                    self.network_logger.error(f"Error handling client {address}: {str(e)}")
                    break
            
            if user_id in self.client_connections:
                del self.client_connections[user_id]
            
            # Log disconnection
            self.logger.log_connection(
                address[0],
                address[1],
                "disconnect",
                f"user_id: {user_id}"
            )
            
        except Exception as e:
            self.network_logger.error(f"Error in client handler for {address}: {str(e)}")
        finally:
            client_socket.close()
    
    def process_client_request(self, request, user_id):
        if 'action' not in request:
            return {"status": "error", "message": "Missing action parameter"}
        
        action = request['action']
        
        # Different actions that can be performed
        if action == "get_channel_info":
            return self.handle_get_channel_info(request, user_id)
        elif action == "get_channel_messages":
            return self.handle_get_channel_messages(request, user_id)
        elif action == "send_message":
            return self.handle_send_message(request, user_id)
        elif action == "fetch_updates":
            return self.handle_fetch_updates(request, user_id)
        else:
            return {"status": "error", "message": f"Unknown action: {action}"}
    
    def handle_get_channel_info(self, request, user_id):
        if 'channel_id' not in request:
            return {"status": "error", "message": "Missing channel_id parameter"}
        
        channel_id = request['channel_id']
        if channel_id not in self.hosted_channels:
            return {"status": "error", "message": "Channel not hosted on this server"}

        if not self.is_channel_member(channel_id, user_id):
            return {"status": "error", "message": "User is not a member of this channel"}

        if channel_id in self.channel_data:
            return {
                "status": "success",
                "channel_info": self.channel_data[channel_id]["info"]
            }
        else:
            # If not in cache, try to load 
            self.load_channel_data(channel_id)
            if channel_id in self.channel_data:
                return {
                    "status": "success",
                    "channel_info": self.channel_data[channel_id]["info"]
                }
            else:
                return {"status": "error", "message": "Failed to load channel data"}
    
    def handle_get_channel_messages(self, request, user_id):
        if 'channel_id' not in request:
            return {"status": "error", "message": "Missing channel_id parameter"}
        
        channel_id = request['channel_id']
        if channel_id not in self.hosted_channels:
            return {"status": "error", "message": "Channel not hosted on this server"}
        
        # Check if user is a member
        if not self.is_channel_member(channel_id, user_id):
            return {"status": "error", "message": "User is not a member of this channel"}
        
        # Get optional parameters
        limit = request.get('limit', 50)
        before_id = request.get('before_id', None)
        
        # Return channel messages from cached data
        if channel_id in self.channel_data:
            messages = self.channel_data[channel_id]["messages"]
            
            if before_id:
                try:
                    before_index = next(i for i, msg in enumerate(messages) if msg["id"] == before_id)
                    messages = messages[before_index + 1:]
                except (StopIteration, IndexError):
                    pass
            
            # Limit the number of messages
            messages = messages[:limit]
            
            return {
                "status": "success",
                "messages": messages
            }
        else:
            self.load_channel_data(channel_id)
            if channel_id in self.channel_data:
                messages = self.channel_data[channel_id]["messages"][:limit]
                return {
                    "status": "success",
                    "messages": messages
                }
            else:
                return {"status": "error", "message": "Failed to load channel data"}
    
def handle_send_message(self, request, user_id):
    if 'channel_id' not in request:
        return {"status": "error", "message": "Missing channel_id parameter"}
    if 'content' not in request and not request.get('has_media', False):
        return {"status": "error", "message": "Message must have content or media"}

    channel_id = request['channel_id']

    if channel_id not in self.hosted_channels:
        return {"status": "error", "message": "Channel not hosted on this server"}

    if not self.is_channel_member(channel_id, user_id):
        return {"status": "error", "message": "User is not a member of this channel"}

    db = SessionLocal()
    try:
        content = request.get('content', '')
        has_media = request.get('has_media', False)
        media_type = request.get('media_type', None)
        media_path = request.get('media_path', None)
        media_name = request.get('media_name', None)

        new_message = Message(
            content=content,
            sender_id=user_id,
            channel_id=channel_id,
            has_media=has_media,
            media_type=media_type,
            media_path=media_path,
            media_name=media_name
        )
        db.add(new_message)
        db.commit()

        db.refresh(new_message)

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

        if channel_id in self.channel_data:
            self.channel_data[channel_id]["messages"].insert(0, message_dict)
            if len(self.channel_data[channel_id]["messages"]) > 200:
                self.channel_data[channel_id]["messages"] = self.channel_data[channel_id]["messages"][:100]

        self.logger.log_data_transaction(
            "message",
            "localhost", 
            self.host_port,
            "channel_message",
            len(content) + (len(media_path) if media_path else 0)
        )

        self.notify_channel_members(channel_id, {
            "type": "new_message",
            "channel_id": channel_id,
            "message": message_dict
        }, exclude_user_ids=[user_id])

        return {
            "status": "success",
            "message_id": new_message.id,
            "timestamp": new_message.created_at.isoformat() if new_message.created_at else None
        }

    except Exception as e:
        db.rollback()
        self.network_logger.error(f"Error sending message to channel {channel_id}: {str(e)}")
        return {"status": "error", "message": f"Failed to send message: {str(e)}"}
    finally:
        db.close()


def handle_fetch_updates(self, request, user_id):
    if 'channel_id' not in request:
        return {"status": "error", "message": "Missing channel_id parameter"}
    if 'last_message_id' not in request:
        return {"status": "error", "message": "Missing last_message_id parameter"}

    channel_id = request['channel_id']
    last_message_id = request['last_message_id']

    if channel_id not in self.hosted_channels:
        return {"status": "error", "message": "Channel not hosted on this server"}

    if not self.is_channel_member(channel_id, user_id):
        return {"status": "error", "message": "User is not a member of this channel"}

    db = SessionLocal()
    try:
        messages = db.query(Message).filter(
            Message.channel_id == channel_id,
            Message.id > last_message_id
        ).order_by(Message.created_at).all()

        message_dicts = [
            {
                "id": msg.id,
                "content": msg.content,
                "sender_id": msg.sender_id,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
                "has_media": msg.has_media,
                "media_type": msg.media_type,
                "media_path": msg.media_path,
                "media_name": msg.media_name
            } for msg in messages
        ]

        self.logger.log_data_transaction(
            "fetch",
            "localhost", 
            self.host_port,
            "channel_updates",
            len(message_dicts)
        )

        return {
            "status": "success",
            "channel_id": channel_id,
            "new_messages": message_dicts
        }

    except Exception as e:
        self.network_logger.error(f"Error fetching updates for channel {channel_id}: {str(e)}")
        return {"status": "error", "message": f"Failed to fetch updates: {str(e)}"}
    finally:
        db.close()


def is_channel_member(self, channel_id, user_id):
    if channel_id in self.channel_data:
        channel_info = self.channel_data[channel_id]["info"]
        if channel_info["owner_id"] == user_id:
            return True
        for member in self.channel_data[channel_id]["members"]:
            if member["user_id"] == user_id:
                return True
        return False

    db = SessionLocal()
    try:
        channel = db.query(Channel).get(channel_id)
        if channel and channel.owner_id == user_id:
            return True

        membership = db.query(ChannelMembership).filter(
            ChannelMembership.channel_id == channel_id,
            ChannelMembership.user_id == user_id
        ).first()

        return membership is not None
    except Exception as e:
        self.network_logger.error(f"Error checking channel membership: {str(e)}")
        return False
    finally:
        db.close()


def notify_channel_members(self, channel_id, data, exclude_user_ids=None):
    pass


def create_channel(self, name, is_private=False):
    db = SessionLocal()
    try:
        new_channel = Channel(
            name=name,
            owner_id=self.user_id,
            is_private=is_private
        )
        db.add(new_channel)
        db.commit()

        db.refresh(new_channel)

        membership = ChannelMembership(
            channel_id=new_channel.id,
            user_id=self.user_id
        )
        db.add(membership)
        db.commit()

        self.hosted_channels[new_channel.id] = self.host_port

        self.channel_data[new_channel.id] = {
            "info": {
                "name": new_channel.name,
                "is_private": new_channel.is_private,
                "created_at": new_channel.created_at.isoformat() if new_channel.created_at else None,
                "owner_id": new_channel.owner_id
            },
            "messages": [],
            "members": [
                {
                    "user_id": self.user_id,
                    "joined_at": datetime.now().isoformat()
                }
            ]
        }

        self.logger.log_channel_hosting(
            new_channel.id, 
            new_channel.name, 
            "create", 
            "success"
        )

        return new_channel.id
    except Exception as e:
        db.rollback()
        self.network_logger.error(f"Error creating channel: {str(e)}")
        self.logger.log_channel_hosting(
            0, name, "create", f"error: {str(e)}"
        )
        return None
    finally:
        db.close()


def stop_hosting(self):
    if not self.is_running:
        return

    self.is_running = False

    try:
        self.client_connections.clear()
    except Exception as e:
        logging.error(f"Error clearing client connections: {str(e)}")

    if self.server_socket:
        try:
            self.server_socket.close()
        except Exception as e:
            logging.error(f"Error closing server socket: {str(e)}")

    try:
        if hasattr(self, 'logger') and self.logger:
            try:
                self.logger.log_connection(
                    "localhost", 
                    self.host_port, 
                    "stop_hosting", 
                    "success"
                )
                self.logger.close()
            except Exception as le:
                logging.error(f"Error using logger: {str(le)}")
    except Exception as e:
        logging.error(f"Error accessing logger: {str(e)}")

    try:
        if hasattr(self, 'network_logger') and self.network_logger:
            try:
                self.network_logger.info(f"Stopped channel hosting on port {self.host_port}")
            except Exception as e:
                logging.info(f"Stopped channel hosting on port {self.host_port}")
    except Exception as e:
        logging.error(f"Error using network logger: {str(e)}")

    try:
        self.hosted_channels.clear()
        self.channel_data.clear()
    except Exception as e:
        logging.error(f"Error clearing channel data: {str(e)}")

    self.host_port = None
