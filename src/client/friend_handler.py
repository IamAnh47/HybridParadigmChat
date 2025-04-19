from PyQt6.QtWidgets import QMessageBox # type: ignore
from database.models import User, FriendRequest, Friendship
from database.config import SessionLocal
import logging

class FriendHandler:
    def __init__(self, current_user_id):
        self.current_user_id = current_user_id
    
    def send_friend_request(self, target_username):
        db = SessionLocal()
        try:
            target_user = db.query(User).filter(User.username == target_username).first()
            if not target_user:
                return False, "User not found"
            
            existing_friendship = db.query(Friendship).filter(
                ((Friendship.user_id == self.current_user_id) & (Friendship.friend_id == target_user.id)) |
                ((Friendship.user_id == target_user.id) & (Friendship.friend_id == self.current_user_id))
            ).first()
            if existing_friendship:
                return False, "Already friends"
            
            existing_request = db.query(FriendRequest).filter(
                ((FriendRequest.sender_id == self.current_user_id) & (FriendRequest.receiver_id == target_user.id)) |
                ((FriendRequest.sender_id == target_user.id) & (FriendRequest.receiver_id == self.current_user_id))
            ).first()
            if existing_request:
                return False, "Friend request already exists"
            
            new_request = FriendRequest(
                sender_id=self.current_user_id,
                receiver_id=target_user.id
            )
            db.add(new_request)
            db.commit()
            
            return True, "Friend request sent"
            
        except Exception as e:
            db.rollback()
            logging.error(f"Error sending friend request: {str(e)}")
            return False, str(e)
        finally:
            db.close()
    
    def accept_friend_request(self, request_id):
        db = SessionLocal()
        try:
            request = db.query(FriendRequest).filter(
                FriendRequest.id == request_id,
                FriendRequest.receiver_id == self.current_user_id
            ).first()
            
            if not request:
                return False, "Request not found"
            
            friendship1 = Friendship(
                user_id=request.sender_id,
                friend_id=request.receiver_id
            )
            friendship2 = Friendship(
                user_id=request.receiver_id,
                friend_id=request.sender_id
            )
            
            db.add(friendship1)
            db.add(friendship2)
            db.delete(request)
            db.commit()
            return True, "Friend request accepted"
            
        except Exception as e:
            db.rollback()
            logging.error(f"Error accepting friend request: {str(e)}")
            return False, str(e)
        finally:
            db.close()
    
    def reject_friend_request(self, request_id):
        db = SessionLocal()
        try:
            request = db.query(FriendRequest).filter(
                FriendRequest.id == request_id,
                FriendRequest.receiver_id == self.current_user_id
            ).first()
            
            if not request:
                return False, "Request not found"
            
            db.delete(request)
            db.commit()
            
            return True, "Friend request rejected"
            
        except Exception as e:
            db.rollback()
            logging.error(f"Error rejecting friend request: {str(e)}")
            return False, str(e)
        finally:
            db.close()
    
    def get_pending_requests(self):
        db = SessionLocal()
        try:
            requests = db.query(FriendRequest).filter(
                FriendRequest.receiver_id == self.current_user_id
            ).all()
            
            return [(req.id, req.sender.username) for req in requests]
            
        finally:
            db.close()
    
    def get_friends(self):
        db = SessionLocal()
        try:
            friendships = db.query(Friendship).filter(
                Friendship.user_id == self.current_user_id
            ).all()
            
            return [(f.friend_id, f.friend.username) for f in friendships]
            
        finally:
            db.close()
    
    def remove_friend(self, friend_id):
        db = SessionLocal()
        try:
            db.query(Friendship).filter(
                ((Friendship.user_id == self.current_user_id) & (Friendship.friend_id == friend_id)) |
                ((Friendship.user_id == friend_id) & (Friendship.friend_id == self.current_user_id))
            ).delete()
            
            db.commit()
            return True, "Friend removed"
            
        except Exception as e:
            db.rollback()
            logging.error(f"Error removing friend: {str(e)}")
            return False, str(e)
        finally:
            db.close()
