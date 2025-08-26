import jwt
from datetime import datetime, timedelta
from flask import current_app
from typing import Optional, Dict, Any


class JWTManager:
    """JWT token management utility."""
    
    @staticmethod
    def generate_token(user_data: Dict[str, Any], expires_in_hours: int = 24) -> str:
        """Generate JWT token for user."""
        payload = {
            'user_id': user_data['id'],
            'username': user_data['uname'],
            'user_type': user_data['user_type_name'],
            'is_admin': user_data['is_admin'],
            'exp': datetime.utcnow() + timedelta(hours=expires_in_hours),
            'iat': datetime.utcnow(),
            'iss': 'mental-health-app'
        }
        
        secret = current_app.config['SECRET_KEY']
        return jwt.encode(payload, secret, algorithm='HS256')
    
    @staticmethod
    def decode_token(token: str) -> Optional[Dict[str, Any]]:
        """Decode and validate JWT token."""
        try:
            secret = current_app.config['SECRET_KEY']
            payload = jwt.decode(token, secret, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    @staticmethod
    def verify_token(token: str) -> Optional[Dict[str, Any]]:
        """Verify token and return user data if valid."""
        payload = JWTManager.decode_token(token)
        if payload and payload.get('exp', 0) > datetime.utcnow().timestamp():
            return {
                'user_id': payload.get('user_id'),
                'username': payload.get('username'),
                'user_type': payload.get('user_type'),
                'is_admin': payload.get('is_admin', False)
            }
        return None
    
    @staticmethod
    def refresh_token(token: str) -> Optional[str]:
        """Refresh JWT token if it's still valid but close to expiry."""
        payload = JWTManager.decode_token(token)
        if payload:
            # Create new token with same user data
            user_data = {
                'id': payload.get('user_id'),
                'uname': payload.get('username'),
                'user_type_name': payload.get('user_type'),
                'is_admin': payload.get('is_admin', False)
            }
            return JWTManager.generate_token(user_data)
        return None