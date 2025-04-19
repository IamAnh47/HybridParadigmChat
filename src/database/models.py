from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from .config import Base

class UserStatus(enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    INVISIBLE = "invisible"

class UserRole(enum.Enum):
    ADMIN = "admin"
    USER = "user"
    VISITOR = "visitor"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    status = Column(String, default="offline")
    role = Column(String, default="user")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    owned_channels = relationship("Channel", back_populates="owner")
    sent_messages = relationship("Message", foreign_keys="Message.sender_id", back_populates="sender")
    received_messages = relationship("Message", foreign_keys="Message.receiver_id", back_populates="receiver")
    sent_friend_requests = relationship("FriendRequest", foreign_keys="FriendRequest.sender_id", back_populates="sender")
    received_friend_requests = relationship("FriendRequest", foreign_keys="FriendRequest.receiver_id", back_populates="receiver")
    
    # Friendship 
    friendships = relationship("Friendship", foreign_keys="Friendship.user_id", back_populates="user")
    friend_of = relationship("Friendship", foreign_keys="Friendship.friend_id", back_populates="friend")
    
    # Channel 
    channel_memberships = relationship("ChannelMembership", back_populates="user")

class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    is_private = Column(Boolean, default=False)
    allow_visitors = Column(Boolean, default=True)
    allow_visitor_messages = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="owned_channels")
    members = relationship("ChannelMembership", back_populates="channel", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="channel", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(String)
    sender_id = Column(Integer, ForeignKey("users.id"))
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=True)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_direct = Column(Boolean, default=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # New fields for media messages
    has_media = Column(Boolean, default=False)
    media_type = Column(String, nullable=True)  
    media_path = Column(String, nullable=True) 
    media_name = Column(String, nullable=True) 

    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_messages")
    channel = relationship("Channel", back_populates="messages")

class FriendRequest(Base):
    __tablename__ = "friend_requests"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"))
    receiver_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_friend_requests")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_friend_requests")

class Friendship(Base):
    __tablename__ = "friendships"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    friend_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", foreign_keys=[user_id], back_populates="friendships")
    friend = relationship("User", foreign_keys=[friend_id], back_populates="friend_of")

class ChannelMembership(Base):
    __tablename__ = "channel_memberships"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    channel_id = Column(Integer, ForeignKey("channels.id"))
    role = Column(String, default="member")
    joined_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="channel_memberships")
    channel = relationship("Channel", back_populates="members") 