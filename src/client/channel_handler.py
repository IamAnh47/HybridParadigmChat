from database.models import Channel, ChannelMembership, User
from database.config import SessionLocal
import logging

class ChannelHandler:
    def __init__(self, current_user_id):
        self.current_user_id = current_user_id
    
    def create_channel(self, name, description, is_private=False, allow_visitors=True):
        db = SessionLocal()
        try:
            # Check if channel name already exists
            existing_channel = db.query(Channel).filter(Channel.name == name).first()
            if existing_channel:
                return False, "Channel name already exists"
            
            # Create new channel
            new_channel = Channel(
                name=name,
                description=description,
                is_private=is_private,
                allow_visitors=allow_visitors,
                owner_id=self.current_user_id
            )
            db.add(new_channel)
            
            # Add creator as member
            membership = ChannelMembership(
                user_id=self.current_user_id,
                channel_id=new_channel.id,
                role="owner"
            )
            db.add(membership)
            
            db.commit()
            return True, "Channel created successfully"
            
        except Exception as e:
            db.rollback()
            logging.error(f"Error creating channel: {str(e)}")
            return False, str(e)
        finally:
            db.close()
    
    def join_channel(self, channel_id):
        db = SessionLocal()
        try:
            channel = db.query(Channel).filter(Channel.id == channel_id).first()
            if not channel:
                return False, "Channel not found"
            
            # Check if already a member
            existing_membership = db.query(ChannelMembership).filter(
                ChannelMembership.user_id == self.current_user_id,
                ChannelMembership.channel_id == channel_id
            ).first()
            if existing_membership:
                return False, "Already a member of this channel"
            
            # Check if channel allows visitors
            if not channel.allow_visitors:
                return False, "Channel does not allow visitors"
            
            # Add member
            membership = ChannelMembership(
                user_id=self.current_user_id,
                channel_id=channel_id,
                role="member"
            )
            db.add(membership)
            db.commit()
            
            return True, "Joined channel successfully"
            
        except Exception as e:
            db.rollback()
            logging.error(f"Error joining channel: {str(e)}")
            return False, str(e)
        finally:
            db.close()
    
    def leave_channel(self, channel_id):
        db = SessionLocal()
        try:
            # Get membership
            membership = db.query(ChannelMembership).filter(
                ChannelMembership.user_id == self.current_user_id,
                ChannelMembership.channel_id == channel_id
            ).first()
            
            if not membership:
                return False, "Not a member of this channel"
            
            # Check if owner
            if membership.role == "owner":
                return False, "Channel owner cannot leave channel"
            
            # Remove membership
            db.delete(membership)
            db.commit()
            
            return True, "Left channel successfully"
            
        except Exception as e:
            db.rollback()
            logging.error(f"Error leaving channel: {str(e)}")
            return False, str(e)
        finally:
            db.close()
    
    def get_channel_members(self, channel_id):
        db = SessionLocal()
        try:
            members = db.query(ChannelMembership).filter(
                ChannelMembership.channel_id == channel_id
            ).all()
            
            return [(m.user_id, m.user.username, m.role) for m in members]
            
        finally:
            db.close()
    
    def get_user_channels(self):
        db = SessionLocal()
        try:
            memberships = db.query(ChannelMembership).filter(
                ChannelMembership.user_id == self.current_user_id
            ).all()
            
            return [(m.channel_id, m.channel.name, m.role) for m in memberships]
            
        finally:
            db.close()
    
    def update_channel_settings(self, channel_id, name=None, description=None, is_private=None, allow_visitors=None):
        db = SessionLocal()
        try:
            # Check if user is owner
            membership = db.query(ChannelMembership).filter(
                ChannelMembership.user_id == self.current_user_id,
                ChannelMembership.channel_id == channel_id,
                ChannelMembership.role == "owner"
            ).first()
            
            if not membership:
                return False, "Only channel owner can update settings"
            
            # Update channel
            channel = db.query(Channel).filter(Channel.id == channel_id).first()
            if name:
                channel.name = name
            if description:
                channel.description = description
            if is_private is not None:
                channel.is_private = is_private
            if allow_visitors is not None:
                channel.allow_visitors = allow_visitors
            
            db.commit()
            return True, "Channel settings updated successfully"
            
        except Exception as e:
            db.rollback()
            logging.error(f"Error updating channel settings: {str(e)}")
            return False, str(e)
        finally:
            db.close()
    
    def search_channels(self, query):
        db = SessionLocal()
        try:
            channels = db.query(Channel).filter(
                Channel.name.ilike(f"%{query}%")
            ).all()
            
            return [(c.id, c.name, c.description) for c in channels]
            
        finally:
            db.close()
    
    def get_channel_info(self, channel_id):
        db = SessionLocal()
        try:
            channel = db.query(Channel).filter(Channel.id == channel_id).first()
            if not channel:
                return None
            
            return {
                'id': channel.id,
                'name': channel.name,
                'description': channel.description,
                'is_private': channel.is_private,
                'allow_visitors': channel.allow_visitors,
                'owner_id': channel.owner_id
            }
            
        finally:
            db.close() 