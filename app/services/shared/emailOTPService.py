import random
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from ...model.shared.users import User
from ...db import get_session
from ..SMTP.smtpService import SMTPService


class EmailOTPService:
    """Service for handling email OTP verification functionality."""
    
    @staticmethod
    def generate_otp_code() -> str:
        """Generate 6-digit OTP code."""
        return f"{random.randint(100000, 999999)}"
    
    @staticmethod
    def send_otp_email(user_id: int) -> Dict[str, Any]:
        """Send OTP email to user."""
        with get_session() as db:
            user = db.query(User).filter_by(id=user_id).first()
            if not user:
                return {"status": "error", "message": "User not found"}
            
            if not user.email:
                return {"status": "error", "message": "User has no email address"}
            
            if user.email_verified:
                return {"status": "error", "message": "Email already verified"}
            
            # Generate new OTP code with 12-hour expiration
            otp_code = EmailOTPService.generate_otp_code()
            user.email_otp_code = otp_code
            user.email_otp_expires_at = datetime.utcnow() + timedelta(hours=12)
            
            db.commit()
            
            # Send OTP email using SMTP service
            try:
                template_path = os.path.join(
                    os.path.dirname(__file__), 
                    '../SMTP/otp_template.html'
                )
                
                template_data = {
                    'user_name': user.uname,
                    'otp_code': otp_code,
                    'expiry_hours': '12'
                }
                
                success = SMTPService.send_template_email(
                    to_email=user.email,
                    subject="Kode Verifikasi Email - Mental Health Assessment",
                    template_path=template_path,
                    template_data=template_data
                )
                
                if success:
                    return {"status": "success", "message": "OTP email sent"}
                else:
                    return {"status": "error", "message": "Failed to send email"}
                    
            except Exception as e:
                return {"status": "error", "message": f"Failed to send email: {str(e)}"}
    
    @staticmethod
    def verify_otp(user_id: int, otp_code: str) -> Dict[str, Any]:
        """Verify OTP code."""
        with get_session() as db:
            user = db.query(User).filter_by(id=user_id).first()
            if not user:
                return {"status": "error", "message": "User not found"}
            
            if user.email_verified:
                return {"status": "error", "message": "Email already verified"}
            
            if not user.email_otp_code:
                return {"status": "error", "message": "No OTP code found. Please request a new one."}
            
            # Check if OTP has expired
            if user.email_otp_expires_at and datetime.utcnow() > user.email_otp_expires_at:
                # Clean up expired OTP
                user.email_otp_code = None
                user.email_otp_expires_at = None
                db.commit()
                return {"status": "error", "message": "OTP code has expired. Please request a new one."}
            
            # Verify OTP code
            if user.email_otp_code != otp_code.strip():
                return {"status": "error", "message": "Invalid OTP code"}
            
            # Mark email as verified and clean up OTP
            user.email_verified = True
            user.email_otp_code = None
            user.email_otp_expires_at = None
            
            # Cancel scheduled deletion since email is now verified
            user.deletion_scheduled_at = None
            
            db.commit()
            
            return {
                "status": "success", 
                "message": "Email verified successfully",
                "user_id": user.id,
                "username": user.uname
            }
    
    @staticmethod
    def is_email_verified(user_id: int) -> bool:
        """Check if user's email is verified."""
        with get_session() as db:
            user = db.query(User).filter_by(id=user_id).first()
            return user.email_verified if user else False
    
    @staticmethod
    def can_resend_otp(user_id: int) -> bool:
        """Check if OTP can be resent (rate limiting - 5 minutes between sends)."""
        with get_session() as db:
            user = db.query(User).filter_by(id=user_id).first()
            if not user or user.email_verified:
                return False
            
            if not user.email_otp_expires_at:
                return True
            
            # Allow resending if last OTP was sent more than 5 minutes ago
            # Calculate when OTP was sent (expires_at - 12 hours)
            otp_sent_at = user.email_otp_expires_at - timedelta(hours=12)
            resend_time = otp_sent_at + timedelta(minutes=5)
            return datetime.utcnow() > resend_time
    
    @staticmethod
    def cleanup_expired_otps() -> Dict[str, int]:
        """Clean up expired OTP codes and DELETE unverified users. Returns counts."""
        with get_session() as db:
            # Find users with expired OTPs who haven't verified their email
            expired_unverified_users = db.query(User).filter(
                User.email_otp_expires_at < datetime.utcnow(),
                User.email_verified == False,
                User.email_otp_code.is_not(None)
            ).all()
            
            # Find users with expired OTPs who ARE verified (just clean OTP)
            expired_verified_users = db.query(User).filter(
                User.email_otp_expires_at < datetime.utcnow(),
                User.email_verified == True,
                User.email_otp_code.is_not(None)
            ).all()
            
            deleted_count = 0
            cleaned_count = 0
            
            # DELETE unverified users with expired OTPs (harsh but effective)
            for user in expired_unverified_users:
                print(f"AUTO-DELETING unverified user: {user.uname} (email: {user.email}) - OTP expired")
                db.delete(user)
                deleted_count += 1
            
            # Just clean OTP from verified users
            for user in expired_verified_users:
                user.email_otp_code = None
                user.email_otp_expires_at = None
                cleaned_count += 1
            
            db.commit()
            return {
                "deleted_users": deleted_count,
                "cleaned_otps": cleaned_count,
                "total_processed": deleted_count + cleaned_count
            }
    
    @staticmethod
    def force_cleanup_expired_users() -> Dict[str, int]:
        """Force cleanup - can be called manually or via cron job."""
        print("Running forced cleanup of expired OTP users...")
        result = EmailOTPService.cleanup_expired_otps()
        print(f"Cleanup complete: {result['deleted_users']} users deleted, {result['cleaned_otps']} OTPs cleaned")
        return result