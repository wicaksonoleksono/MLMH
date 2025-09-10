from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from flask import current_app
from ...utils.jwt_utils import JWTManager
from ...model.shared.users import User
from ...model.shared.auto_login_tokens import AutoLoginToken
from ...db import get_session
import jwt
import uuid


class AutoLoginService:
    """Service for handling auto-login JWT tokens with purpose-specific functionality."""
    
    # Define valid purposes for auto-login tokens
    VALID_PURPOSES = [
        'auto_login_session2',
        'auto_login_password_reset', 
        'auto_login_general'
    ]
    
    @staticmethod
    def generate_auto_login_token(user_id: int, purpose: str, redirect_to: str = None, 
                                expires_in_hours: int = 24, single_use: bool = True) -> str:
        """
        Generate auto-login JWT token with specific purpose and redirect.
        
        Args:
            user_id: ID of the user
            purpose: Purpose of the token (must be in VALID_PURPOSES)
            redirect_to: Where to redirect after auto-login
            expires_in_hours: Token expiration time in hours
            single_use: Whether token can only be used once
            
        Returns:
            JWT token string
        """
        if purpose not in AutoLoginService.VALID_PURPOSES:
            raise ValueError(f"Invalid purpose. Must be one of: {AutoLoginService.VALID_PURPOSES}")
        
        # Get user data for token
        with get_session() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")
        
        # Generate unique JTI for tracking single-use tokens
        jti = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)
        
        payload = {
            'user_id': user_id,
            'username': user.uname,
            'purpose': purpose,
            'redirect_to': redirect_to,
            'single_use': single_use,
            'jti': jti,  # JWT ID for tracking
            'exp': expires_at,
            'iat': datetime.utcnow(),
            'iss': 'mental-health-app-autologin'
        }
        
        # If single-use, create tracking record
        if single_use:
            with get_session() as db:
                token_record = AutoLoginToken.create_token_record(
                    user_id=user_id,
                    token_jti=jti,
                    purpose=purpose,
                    expires_at=expires_at
                )
                db.add(token_record)
                db.commit()
        
        secret = current_app.config['SECRET_KEY']
        return jwt.encode(payload, secret, algorithm='HS256')
    
    @staticmethod
    def validate_auto_login_token(token: str) -> Dict[str, Any]:
        """
        Validate auto-login token and return user data and redirect info.
        
        Args:
            token: JWT token string
            
        Returns:
            Dict with validation result and user data
        """
        try:
            secret = current_app.config['SECRET_KEY']
            payload = jwt.decode(token, secret, algorithms=['HS256'])
            
            # Check if token is for auto-login purpose
            purpose = payload.get('purpose')
            if purpose not in AutoLoginService.VALID_PURPOSES:
                return {
                    'valid': False,
                    'error': 'Invalid token purpose',
                    'user_data': None,
                    'redirect_to': None
                }
            
            # Check single-use token status if applicable
            jti = payload.get('jti')
            single_use = payload.get('single_use', False)
            
            if single_use and jti:
                # Check if token has been used
                token_record = AutoLoginToken.find_valid_token(jti)
                if not token_record:
                    return {
                        'valid': False,
                        'error': 'Token has already been used or expired',
                        'user_data': None,
                        'redirect_to': None
                    }
            
            # Check if user still exists and build user data within session
            user_id = payload.get('user_id')
            with get_session() as db:
                user = db.query(User).filter(User.id == user_id).first()
                if not user:
                    return {
                        'valid': False,
                        'error': 'User not found',
                        'user_data': None,
                        'redirect_to': None
                    }
                
                # Build user data while session is still active
                user_data = {
                    'id': user.id,
                    'uname': user.uname,
                    'user_type_name': user.user_type.name,
                    'is_admin': user.is_admin(),
                    'is_active': user.is_active,
                    'email': user.email,
                    'email_verified': user.email_verified
                }
            
            # Return validation result
            return {
                'valid': True,
                'error': None,
                'user_data': user_data,
                'redirect_to': payload.get('redirect_to'),
                'purpose': purpose,
                'single_use': single_use,
                'jti': jti
            }
            
        except jwt.ExpiredSignatureError:
            return {
                'valid': False,
                'error': 'Token has expired',
                'user_data': None,
                'redirect_to': None
            }
        except jwt.InvalidTokenError:
            return {
                'valid': False,
                'error': 'Invalid token',
                'user_data': None,
                'redirect_to': None
            }
        except Exception as e:
            return {
                'valid': False,
                'error': f'Token validation error: {str(e)}',
                'user_data': None,
                'redirect_to': None
            }
    
    @staticmethod
    def generate_session2_auto_login_url(user_id: int, session2_path: str = None) -> str:
        """
        Generate auto-login URL specifically for Session 2 continuation.
        
        Args:
            user_id: ID of the user
            session2_path: Custom path for Session 2 (defaults to config)
            
        Returns:
            Complete auto-login URL for Session 2
        """
        # Get Session 2 path from config if not provided
        if not session2_path:
            session2_path = '/'  # Just go to BASE_URL
        
        # Generate auto-login token
        token = AutoLoginService.generate_auto_login_token(
            user_id=user_id,
            purpose='auto_login_session2',
            redirect_to=session2_path,
            expires_in_hours=48,  # Longer expiration for Session 2
            single_use=True
        )
        
        # Build complete URL using BASE_URL
        base_url = current_app.config.get('BASE_URL', 'http://localhost:5000')
        auto_login_url = f"{base_url.rstrip('/')}/auth/auto-login?token={token}"
        
        return auto_login_url
    
    @staticmethod
    def generate_password_reset_auto_login_url(user_id: int, redirect_to: str = '/') -> str:
        """
        Generate auto-login URL for post-password-reset login.
        
        Args:
            user_id: ID of the user
            redirect_to: Where to redirect after auto-login
            
        Returns:
            Complete auto-login URL for password reset flow
        """
        # Generate auto-login token
        token = AutoLoginService.generate_auto_login_token(
            user_id=user_id,
            purpose='auto_login_password_reset',
            redirect_to=redirect_to,
            expires_in_hours=2,  # Short expiration for password reset
            single_use=True
        )
        
        # Build complete URL using BASE_URL
        base_url = current_app.config.get('BASE_URL', 'http://localhost:5000')
        auto_login_url = f"{base_url.rstrip('/')}/auth/auto-login?token={token}"
        
        return auto_login_url
    
    @staticmethod
    def invalidate_auto_login_token(jti: str) -> bool:
        """
        Invalidate a specific auto-login token by marking it as used.
        
        Args:
            jti: JWT ID of the token to invalidate
            
        Returns:
            True if token was found and invalidated, False otherwise
        """
        with get_session() as db:
            token_record = db.query(AutoLoginToken).filter(
                AutoLoginToken.token_jti == jti,
                AutoLoginToken.used == False
            ).first()
            
            if token_record:
                token_record.mark_as_used()
                db.commit()
                return True
            
            return False
    
    @staticmethod
    def invalidate_user_auto_login_tokens(user_id: int, purpose: str = None):
        """
        Invalidate all auto-login tokens for a user.
        
        Args:
            user_id: ID of the user
            purpose: Specific purpose to invalidate (optional)
        """
        with get_session() as db:
            query = db.query(AutoLoginToken).filter(
                AutoLoginToken.user_id == user_id,
                AutoLoginToken.used == False
            )
            
            # Filter by purpose if specified
            if purpose:
                query = query.filter(AutoLoginToken.purpose == purpose)
            
            tokens = query.all()
            for token in tokens:
                token.mark_as_used()
            
            db.commit()
            return len(tokens)
    
    @staticmethod
    def get_redirect_url_for_user(user_data: Dict[str, Any], default_redirect: str = '/') -> str:
        """
        Determine appropriate redirect URL based on user type and status.
        
        Args:
            user_data: User data from validated token
            default_redirect: Default redirect if no specific logic applies
            
        Returns:
            Appropriate redirect URL for the user
        """
        # Admin users go to admin dashboard
        if user_data.get('is_admin'):
            return '/admin'
        
        # Regular users go to user dashboard or specified redirect
        return default_redirect if default_redirect != '/' else '/dashboard'