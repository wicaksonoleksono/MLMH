from typing import Optional, List
from sqlalchemy.exc import IntegrityError
from ...model.shared.users import User
from ...model.shared.enums import UserType
from .database import db_session
from ...decorators import api_response


class UserManagerService:
    """User Manager Service for CRUD operations."""


    @staticmethod
    @api_response
    def create_user(uname: str, password: str, user_type_name: str,
                    email: Optional[str] = None, phone: Optional[str] = None,
                    age: Optional[int] = None, gender: Optional[str] = None,
                    educational_level: Optional[str] = None, cultural_background: Optional[str] = None,
                    medical_conditions: Optional[str] = None, medications: Optional[str] = None,
                    emergency_contact: Optional[str] = None) -> User:
        """Create a new user."""
        # Get user type by name
        user_type = db_session.query(UserType).filter_by(name=user_type_name).first()
        if not user_type:
            raise ValueError(f"User type '{user_type_name}' not found")

        # Create user - extended fields only for regular users
        if user_type_name.lower() == 'user':
            user = User.create_user(
                uname=uname,
                password=password,
                user_type_id=user_type.id,
                email=email,
                phone=phone,
                age=age,
                gender=gender,
                educational_level=educational_level,
                cultural_background=cultural_background,
                medical_conditions=medical_conditions,
                medications=medications,
                emergency_contact=emergency_contact
            )
        else:
            # Admin users only get basic fields
            user = User.create_user(
                uname=uname,
                password=password,
                user_type_id=user_type.id,
                email=email,
                phone=phone
            )

        try:
            db_session.add(user)
            db_session.commit()
            return user
        except IntegrityError:
            db_session.rollback()
            raise ValueError(f"Username '{uname}' already exists")

    @staticmethod
    @api_response
    def get_user_by_id(user_id: int) -> Optional[User]:
        """Get user by ID."""
        return db_session.query(User).filter_by(id=user_id).first()

    @staticmethod
    @api_response
    def get_user_by_username(uname: str) -> Optional[User]:
        """Get user by username."""
        return db_session.query(User).filter_by(uname=uname).first()

    @staticmethod
    @api_response
    def get_all_users(active_only: bool = True) -> List[User]:
        """Get all users."""
        query = db_session.query(User)
        if active_only:
            query = query.filter_by(is_active=True)
        return query.all()

    @staticmethod
    @api_response
    def update_user(user_id: int, **kwargs) -> Optional[User]:
        """Update user data."""
        user = db_session.query(User).filter_by(id=user_id).first()
        if not user:
            return None

        # Handle password separately
        if 'password' in kwargs:
            user.set_password(kwargs.pop('password'))

        # Handle user type by name
        if 'user_type_name' in kwargs:
            user_type = db_session.query(UserType).filter_by(name=kwargs.pop('user_type_name')).first()
            if user_type:
                user.user_type_id = user_type.id

        # Update other fields
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)

        try:
            db_session.commit()
            return user
        except IntegrityError:
            db_session.rollback()
            raise ValueError("Failed to update user: constraint violation")

    @staticmethod
    @api_response
    def delete_user(user_id: int) -> bool:
        """Soft delete user (set inactive)."""
        user = db_session.query(User).filter_by(id=user_id).first()
        if not user:
            return False

        user.is_active = False
        db_session.commit()
        return True

    @staticmethod
    @api_response
    def hard_delete_user(user_id: int) -> bool:
        """Hard delete user from database."""
        user = db_session.query(User).filter_by(id=user_id).first()
        if not user:
            return False

        db_session.delete(user)
        db_session.commit()
        return True

    @staticmethod
    def authenticate_user(uname: str, password: str) -> Optional[User]:
        """Authenticate user by username and password."""
        user = db_session.query(User).filter_by(uname=uname).first()
        if user and user.is_active and user.check_password(password):
            return user
        return None

    @staticmethod
    @api_response
    def get_users_by_type(user_type_name: str, active_only: bool = True) -> List[User]:
        """Get users by type name."""
        query = db_session.query(User).join(UserType).filter(UserType.name == user_type_name)
        if active_only:
            query = query.filter(User.is_active == True)
        return query.all()

    @staticmethod
    @api_response
    def count_users(active_only: bool = True) -> int:
        """Count total users."""
        query = db_session.query(User)
        if active_only:
            query = query.filter_by(is_active=True)
        return query.count()
