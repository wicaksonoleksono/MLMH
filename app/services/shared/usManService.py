from typing import Optional, List
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from ...model.shared.users import User
from ...model.shared.enums import UserType
from ...decorators import api_response
from ...db import get_session


class UserManagerService:
    """User Manager Service for CRUD operations."""
    # TODO: ADD USERNAME VERIVICATION. MAYBE NOT IN HERE. 

    @staticmethod
    @api_response
    def create_user(uname: str, password: str, user_type_name: str,
                    email: Optional[str] = None, phone: Optional[str] = None,
                    age: Optional[int] = None, gender: Optional[str] = None,
                    educational_level: Optional[str] = None, cultural_background: Optional[str] = None,
                    medical_conditions: Optional[str] = None, medications: Optional[str] = None,
                    emergency_contact: Optional[str] = None) -> User:
        """Create a new user."""
        with get_session() as db:
            # Get user type by name
            user_type = db.query(UserType).filter_by(name=user_type_name).first()
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
                db.add(user)
                return user
            except IntegrityError:
                raise ValueError(f"Username '{uname}' already exists")

    @staticmethod
    def _get_user_data_by_id(user_id: int) -> Optional[dict]:
        """Internal method to get user data by ID (no decorator)."""
        with get_session() as db:
            user = db.query(User).options(joinedload(User.user_type)).filter_by(id=user_id).first()
            if user and user.is_active:
                return {
                    'id': user.id,
                    'uname': user.uname,
                    'email': user.email,
                    'phone': user.phone,
                    'age': user.age,
                    'gender': user.gender,
                    'educational_level': user.educational_level,
                    'cultural_background': user.cultural_background,
                    'medical_conditions': user.medical_conditions,
                    'medications': user.medications,
                    'emergency_contact': user.emergency_contact,
                    'user_type_id': user.user_type_id,
                    'user_type_name': user.user_type.name,
                    'is_active': user.is_active,
                    'is_admin': user.user_type.name.lower() == 'admin',
                    'created_at': user.created_at.isoformat() if user.created_at else None,
                    'updated_at': user.updated_at.isoformat() if user.updated_at else None
                }
            return None

    @staticmethod
    @api_response
    def get_user_by_id(user_id: int) -> Optional[dict]:
        """Get user by ID (API endpoint)."""
        return UserManagerService._get_user_data_by_id(user_id)

    @staticmethod
    @api_response
    def get_user_by_username(uname: str) -> Optional[User]:
        """Get user by username."""
        with get_session() as db:
            return db.query(User).filter_by(uname=uname).first()

    @staticmethod
    @api_response
    def get_all_users(active_only: bool = True) -> List[User]:
        """Get all users."""
        with get_session() as db:
            query = db.query(User)
            if active_only:
                query = query.filter_by(is_active=True)
            return query.all()

    @staticmethod
    @api_response
    def update_user(user_id: int, **kwargs) -> Optional[User]:
        """Update user data."""
        with get_session() as db:
            user = db.query(User).filter_by(id=user_id).first()
            if not user:
                return None

            # Handle password separately
            if 'password' in kwargs:
                user.set_password(kwargs.pop('password'))

            # Handle user type by name
            if 'user_type_name' in kwargs:
                user_type = db.query(UserType).filter_by(name=kwargs.pop('user_type_name')).first()
                if user_type:
                    user.user_type_id = user_type.id

            # Update other fields
            for key, value in kwargs.items():
                if hasattr(user, key):
                    setattr(user, key, value)

            try:
                return user
            except IntegrityError:
                raise ValueError("Failed to update user: constraint violation")

    @staticmethod
    @api_response
    def delete_user(user_id: int) -> bool:
        """Soft delete user (set inactive)."""
        with get_session() as db:
            user = db.query(User).filter_by(id=user_id).first()
            if not user:
                return False

            user.is_active = False
            return True

    @staticmethod
    @api_response
    def hard_delete_user(user_id: int) -> bool:
        """Hard delete user from database."""
        with get_session() as db:
            user = db.query(User).filter_by(id=user_id).first()
            if not user:
                return False

            db.delete(user)
            return True

    @staticmethod
    def authenticate_user(uname: str, password: str) -> Optional[dict]:
        """Authenticate user by username and password. Returns serialized user data."""
        with get_session() as db:
            user = db.query(User).options(joinedload(User.user_type)).filter_by(uname=uname).first()
            if user and user.is_active and user.check_password(password):
                # Return serialized data to avoid detached instance issues
                return {
                    'id': user.id,
                    'uname': user.uname,
                    'email': user.email,
                    'phone': user.phone,
                    'age': user.age,
                    'gender': user.gender,
                    'educational_level': user.educational_level,
                    'cultural_background': user.cultural_background,
                    'medical_conditions': user.medical_conditions,
                    'medications': user.medications,
                    'emergency_contact': user.emergency_contact,
                    'user_type_id': user.user_type_id,
                    'user_type_name': user.user_type.name,
                    'is_active': user.is_active,
                    'is_admin': user.user_type.name.lower() == 'admin',
                    'created_at': user.created_at.isoformat() if user.created_at else None,
                    'updated_at': user.updated_at.isoformat() if user.updated_at else None
                }
            return None

    @staticmethod
    @api_response
    def get_users_by_type(user_type_name: str, active_only: bool = True) -> List[User]:
        """Get users by type name."""
        with get_session() as db:
            query = db.query(User).join(UserType).filter(UserType.name == user_type_name)
            if active_only:
                query = query.filter(User.is_active == True)
            return query.all()

    @staticmethod
    @api_response
    def count_users(active_only: bool = True) -> int:
        """Count total users."""
        with get_session() as db:
            query = db.query(User)
            if active_only:
                query = query.filter_by(is_active=True)
            return query.count()
