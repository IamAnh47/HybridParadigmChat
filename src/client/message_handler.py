from database.models import ChannelMembership, Message, User, Channel
from database.config import SessionLocal
import logging
from datetime import datetime, timedelta

class MessageHandler:
    def __init__(self, current_user_id):
        self.current_user_id = current_user_id
    
    def send_message(self, channel_id, content):
        db = SessionLocal()
        try:
            membership = db.query(Channel).join(Channel.members).filter(
                Channel.id == channel_id,
                ChannelMembership.user_id == self.current_user_id
            ).first()
            
            if not membership:
                return False, "Not a member of this channel"
            
            new_message = Message(
                content=content,
                sender_id=self.current_user_id,
                channel_id=channel_id
            )
            db.add(new_message)
            db.commit()
            
            return True, "Message sent successfully"
            
        except Exception as e:
            db.rollback()
            logging.error(f"Error sending message: {str(e)}")
            return False, str(e)
        finally:
            db.close()
    
    def get_channel_messages(self, channel_id, limit=100, before=None):
        db = SessionLocal()
        try:
            query = db.query(Message).filter(Message.channel_id == channel_id)
            
            if before:
                query = query.filter(Message.created_at < before)
            
            messages = query.order_by(Message.created_at.desc()).limit(limit).all()
            
            return [{
                'id': m.id,
                'content': m.content,
                'sender_id': m.sender_id,
                'sender_name': m.sender.username,
                'created_at': m.created_at
            } for m in messages]
            
        finally:
            db.close()
    
    def get_unread_messages(self, channel_id, last_read=None):
        db = SessionLocal()
        try:
            query = db.query(Message).filter(
                Message.channel_id == channel_id,
                Message.sender_id != self.current_user_id
            )
            
            if last_read:
                query = query.filter(Message.created_at > last_read)
            
            messages = query.order_by(Message.created_at.asc()).all()
            
            return [{
                'id': m.id,
                'content': m.content,
                'sender_id': m.sender_id,
                'sender_name': m.sender.username,
                'created_at': m.created_at
            } for m in messages]
            
        finally:
            db.close()
    
    def get_recent_messages(self, limit=20):
        db = SessionLocal()
        try:
            channels = db.query(Channel).join(Channel.members).filter(
                ChannelMembership.user_id == self.current_user_id
            ).all()
            
            channel_ids = [c.id for c in channels]
            
            messages = db.query(Message).filter(
                Message.channel_id.in_(channel_ids)
            ).order_by(Message.created_at.desc()).limit(limit).all()
            
            return [{
                'id': m.id,
                'content': m.content,
                'sender_id': m.sender_id,
                'sender_name': m.sender.username,
                'channel_id': m.channel_id,
                'channel_name': m.channel.name,
                'created_at': m.created_at
            } for m in messages]
            
        finally:
            db.close()
    
    def search_messages(self, query, channel_id=None):
        db = SessionLocal()
        try:
            search_query = db.query(Message).filter(
                Message.content.ilike(f"%{query}%")
            )
            
            if channel_id:
                search_query = search_query.filter(Message.channel_id == channel_id)
            else:
                channels = db.query(Channel).join(Channel.members).filter(
                    ChannelMembership.user_id == self.current_user_id
                ).all()
                channel_ids = [c.id for c in channels]
                search_query = search_query.filter(Message.channel_id.in_(channel_ids))
            
            messages = search_query.order_by(Message.created_at.desc()).all()
            
            return [{
                'id': m.id,
                'content': m.content,
                'sender_id': m.sender_id,
                'sender_name': m.sender.username,
                'channel_id': m.channel_id,
                'channel_name': m.channel.name,
                'created_at': m.created_at
            } for m in messages]
            
        finally:
            db.close()
    
    def get_message_count(self, channel_id, time_range=None):
        db = SessionLocal()
        try:
            query = db.query(Message).filter(Message.channel_id == channel_id)
            
            if time_range:
                start_time = datetime.utcnow() - timedelta(hours=time_range)
                query = query.filter(Message.created_at >= start_time)
            
            return query.count()
            
        finally:
            db.close()
    
    def get_user_message_count(self, user_id, time_range=None):
        db = SessionLocal()
        try:
            query = db.query(Message).filter(Message.sender_id == user_id)
            
            if time_range:
                start_time = datetime.utcnow() - timedelta(hours=time_range)
                query = query.filter(Message.created_at >= start_time)
            
            return query.count()
            
        finally:
            db.close() 