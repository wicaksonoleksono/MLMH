from flask_login import UserMixin
from typing import Dict, Any


class SimpleUser(UserMixin):
    """Simple user class for Flask-Login compatibility when using JWT."""
    
    def __init__(self, user_data: Dict[str, Any]):
        self.id = str(user_data['id'])  # Flask-Login expects string ID
        self.uname = user_data['uname']
        self.email = user_data.get('email')
        self.user_type_name = user_data['user_type_name']
        self.is_admin_user = user_data['is_admin']
        self.is_active_user = user_data['is_active']
        
        # Extended fields
        self.phone = user_data.get('phone')
        self.age = user_data.get('age')
        self.gender = user_data.get('gender')
        self.educational_level = user_data.get('educational_level')
        self.cultural_background = user_data.get('cultural_background')
        self.medical_conditions = user_data.get('medical_conditions')
        self.medications = user_data.get('medications')
        self.emergency_contact = user_data.get('emergency_contact')
        self.created_at = user_data.get('created_at')
        self.updated_at = user_data.get('updated_at')
    
    def is_admin(self) -> bool:
        """Check if user is admin."""
        return self.is_admin_user
    
    def is_user(self) -> bool:
        """Check if user is regular user type."""
        return not self.is_admin_user
    
    @property
    def is_active(self) -> bool:
        """Required by Flask-Login."""
        return self.is_active_user
    
    def get_id(self) -> str:
        """Required by Flask-Login."""
        return self.id