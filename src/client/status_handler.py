from database.models import User
from database.config import SessionLocal
import logging
from datetime import datetime

class StatusHandler:
    def __init__(self, current_user_id):
        self.current_user_id = current_user_id
    
    def update_status(self, status):
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == self.current_user_id).first()
            if not user:
                return False, "User not found"
            
            user.status = status
            user.last_seen = datetime.utcnow()
            db.commit()
            
            return True, "Status updated successfully"
            
        except Exception as e:
            db.rollback()
            logging.error(f"Error updating status: {str(e)}")
            return False, str(e)
        finally:
            db.close()
    
    def get_user_status(self, user_id):
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return None
            
            return {
                'status': user.status,
                'last_seen': user.last_seen
            }
            
        finally:
            db.close()
    
    def get_online_users(self):
        db = SessionLocal()
        try:
            users = db.query(User).filter(
                User.status == 'online',
                User.id != self.current_user_id
            ).all()
            
            return [{
                'id': u.id,
                'username': u.username,
                'last_seen': u.last_seen
            } for u in users]
            
        finally:
            db.close()
    
    def get_friend_statuses(self):
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == self.current_user_id).first()
            friends = user.friends
            
            return [{
                'id': f.friend_id,
                'username': f.friend.username,
                'status': f.friend.status,
                'last_seen': f.friend.last_seen
            } for f in friends]
            
        finally:
            db.close()
    
    def set_invisible(self):
        return self.update_status('invisible')
    
    def set_online(self):
        return self.update_status('online')
    
    def set_offline(self):
        return self.update_status('offline')
    
    def get_status_history(self, user_id, limit=100):
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return []
            
            return [{
                'status': user.status,
                'timestamp': user.last_seen
            }]
            
        finally:
            db.close()
    
    def get_status_statistics(self, time_range=None):
        db = SessionLocal()
        try:
            query = db.query(User)
            
            if time_range:
                pass
            
            total_users = query.count()
            online_users = query.filter(User.status == 'online').count()
            offline_users = query.filter(User.status == 'offline').count()
            invisible_users = query.filter(User.status == 'invisible').count()
            
            return {
                'total': total_users,
                'online': online_users,
                'offline': offline_users,
                'invisible': invisible_users
            }
            
        finally:
            db.close() 