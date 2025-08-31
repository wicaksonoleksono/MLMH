"""User service for handling user profile updates and authentication."""

from app.db import get_session
from app.model.shared.users import User
from sqlalchemy.exc import IntegrityError
import logging

logger = logging.getLogger(__name__)


class UserService:
    @staticmethod
    def update_profile(user_id, username=None, email=None):
        """Update user profile information."""
        # Convert user_id to int if it's a string
        if isinstance(user_id, str):
            user_id = int(user_id)
            
        with get_session() as db:
            try:
                user = db.query(User).filter_by(id=user_id).first()
                if not user:
                    return {"status": "SNAFU", "error": "User not found"}

                # Update username if provided
                if username:
                    # Check if username is already taken by another user
                    existing_user = db.query(User).filter_by(uname=username).first()
                    if existing_user and existing_user.id != user_id:
                        return {"status": "SNAFU", "error": "Username already taken"}
                    user.uname = username

                # Update email if provided
                if email is not None:  # Allow setting to None/empty
                    user.email = email

                db.commit()
                return {"status": "OLKORECT", "message": "Profile updated successfully"}

            except IntegrityError as e:
                db.rollback()
                logger.error(f"Integrity error updating profile: {str(e)}")
                return {"status": "SNAFU", "error": "Failed to update profile"}
            except Exception as e:
                db.rollback()
                logger.error(f"Error updating profile: {str(e)}")
                return {"status": "SNAFU", "error": "Failed to update profile"}

    @staticmethod
    def update_password(user_id, current_password, new_password):
        """Update user password with current password verification."""
        # Convert user_id to int if it's a string
        if isinstance(user_id, str):
            user_id = int(user_id)
            
        with get_session() as db:
            try:
                user = db.query(User).filter_by(id=user_id).first()
                if not user:
                    return {"status": "SNAFU", "error": "User not found"}

                # Verify current password
                if not user.check_password(current_password):
                    return {"status": "SNAFU", "error": "Current password is incorrect"}

                # Update to new password
                user.set_password(new_password)
                db.commit()
                return {"status": "OLKORECT", "message": "Password updated successfully"}

            except Exception as e:
                db.rollback()
                logger.error(f"Error updating password: {str(e)}")
                return {"status": "SNAFU", "error": "Failed to update password"}

    @staticmethod
    def authenticate_user(user_id, password):
        """Authenticate user with password."""
        # Convert user_id to int if it's a string
        if isinstance(user_id, str):
            user_id = int(user_id)
            
        with get_session() as db:
            try:
                user = db.query(User).filter_by(id=user_id).first()
                if not user:
                    return False
                return user.check_password(password)
            except Exception as e:
                logger.error(f"Error authenticating user: {str(e)}")
                return False