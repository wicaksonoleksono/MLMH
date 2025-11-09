import secrets
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from ...model.shared.users import User
from ...db import get_session
from ..SMTP.smtpService import SMTPService
from .autoLoginService import AutoLoginService


class PasswordResetService:
    """Service for handling password reset magic link functionality."""
    
    @staticmethod
    def generate_reset_token() -> str:
        """Generate secure reset token."""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def send_password_reset_email(email: str) -> Dict[str, Any]:
        """Send password reset magic link to user."""
        with get_session() as db:
            user = db.query(User).filter_by(email=email.lower()).first()
            if not user:
                # Don't reveal that email doesn't exist for security
                return {"status": "success", "message": "If email exists, reset link sent"}
            
            # Generate reset token with 1-hour expiration
            reset_token = PasswordResetService.generate_reset_token()
            user.password_reset_token = reset_token
            user.password_reset_expires_at = datetime.utcnow() + timedelta(hours=1)
            
            db.commit()
            
            # Send reset email using SMTP service
            try:
                template_path = os.path.join(
                    os.path.dirname(__file__), 
                    '../SMTP/password_reset_template.html'
                )
                
                # Create magic link URL
                from flask import request, url_for, current_app

                # Use BASE_URL from config - NO FALLBACK to ensure proper configuration
                base_url = current_app.config.get('BASE_URL')
                if not base_url:
                    raise ValueError("BASE_URL not configured in environment variables")
                reset_url = f"{base_url.rstrip('/')}/auth/reset-password?token={reset_token}"
                
                # Generate auto-login URL for after password reset
                try:
                    auto_login_url = AutoLoginService.generate_password_reset_auto_login_url(
                        user_id=user.id,
                        redirect_to='/'
                    )
                except Exception as e:
                    print(f"Warning: Could not generate auto-login URL for password reset: {e}")
                    auto_login_url = None

                template_data = {
                    'username': user.uname,  # Changed from 'user_name' to 'username' for consistency
                    'user_name': user.uname,  # Keep both for backward compatibility
                    'reset_url': reset_url,
                    'auto_login_url': auto_login_url,
                    'base_url': base_url,
                    'expiry_minutes': '60'
                }
                
                success = SMTPService.send_template_email(
                    to_email=user.email,
                    subject="Password Reset - Mental Health Assessment",
                    template_path=template_path,
                    template_data=template_data
                )
                
                if success:
                    return {"status": "success", "message": "If email exists, reset link sent"}
                else:
                    return {"status": "error", "message": "Failed to send email"}
                    
            except Exception as e:
                return {"status": "error", "message": f"Failed to send email: {str(e)}"}
    
    @staticmethod
    def validate_reset_token(token: str) -> Dict[str, Any]:
        """Validate password reset token and return user info."""
        with get_session() as db:
            user = db.query(User).filter_by(password_reset_token=token).first()
            if not user:
                return {"status": "error", "message": "Invalid or expired reset link"}
            
            # Check if token has expired
            if user.password_reset_expires_at and datetime.utcnow() > user.password_reset_expires_at:
                # Clean up expired token
                user.password_reset_token = None
                user.password_reset_expires_at = None
                db.commit()
                return {"status": "error", "message": "Reset link has expired"}
            
            return {
                "status": "success",
                "message": "Valid reset token",
                "user_id": user.id,
                "username": user.uname,
                "email": user.email
            }
    
    @staticmethod
    def reset_password(token: str, new_password: str) -> Dict[str, Any]:
        """Reset user password using valid token."""
        with get_session() as db:
            user = db.query(User).filter_by(password_reset_token=token).first()
            if not user:
                return {"status": "error", "message": "Invalid or expired reset link"}
            
            # Check if token has expired
            if user.password_reset_expires_at and datetime.utcnow() > user.password_reset_expires_at:
                # Clean up expired token
                user.password_reset_token = None
                user.password_reset_expires_at = None
                db.commit()
                return {"status": "error", "message": "Reset link has expired"}
            
            # Update password and clean up reset token
            print(f"DEBUG: Updating password for user {user.id} ({user.uname})")
            print(f"DEBUG: Old password hash: {user.password_hash[:20]}...")
            
            user.set_password(new_password)
            user.password_reset_token = None
            user.password_reset_expires_at = None
            
            print(f"DEBUG: New password hash: {user.password_hash[:20]}...")
            print(f"DEBUG: Committing changes to database...")
            
            db.commit()
            
            # Verify password was actually changed
            db.refresh(user)
            print(f"DEBUG: After commit, password hash: {user.password_hash[:20]}...")
            
            # Test the new password immediately
            test_result = user.check_password(new_password)
            print(f"DEBUG: Password verification test: {test_result}")
            
            # Generate auto-login token for seamless login after password reset
            try:
                from flask import current_app
                with current_app.app_context():
                    auto_login_url = AutoLoginService.generate_password_reset_auto_login_url(
                        user_id=user.id, 
                        redirect_to='/'
                    )
            except Exception as e:
                print(f"Warning: Could not generate auto-login URL after password reset: {e}")
                auto_login_url = None
            
            return {
                "status": "success",
                "message": "Password reset successfully",
                "user_id": user.id,
                "username": user.uname,
                "auto_login_url": auto_login_url
            }
    
    @staticmethod
    def can_request_reset(email: str) -> bool:
        """Check if password reset can be requested (rate limiting - 5 minutes)."""
        with get_session() as db:
            user = db.query(User).filter_by(email=email.lower()).first()
            if not user:
                return True  # Don't reveal if email exists
            
            if not user.password_reset_expires_at:
                return True
            
            # Allow new request if last one was sent more than 5 minutes ago
            # Calculate when reset was sent (expires_at - 1 hour)
            reset_sent_at = user.password_reset_expires_at - timedelta(hours=1)
            resend_time = reset_sent_at + timedelta(minutes=5)
            return datetime.utcnow() > resend_time
    
    @staticmethod
    def cleanup_expired_tokens() -> Dict[str, int]:
        """Clean up expired password reset tokens."""
        with get_session() as db:
            expired_users = db.query(User).filter(
                User.password_reset_expires_at < datetime.utcnow(),
                User.password_reset_token.is_not(None)
            ).all()
            
            cleaned_count = 0
            for user in expired_users:
                user.password_reset_token = None
                user.password_reset_expires_at = None
                cleaned_count += 1
            
            db.commit()
            return {"cleaned_tokens": cleaned_count}