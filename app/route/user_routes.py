from flask import Blueprint, request, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user
from ..services.shared.usManService import UserManagerService
from ..decorators import api_response, raw_response

user_bp = Blueprint('user', __name__, url_prefix='/user')


@user_bp.route('/register', methods=['POST'])
@api_response
def register():
    """User registration."""
    data = request.get_json()
    
    # Extract extended profile fields (only for regular users)
    user = UserManagerService.create_user(
        uname=data['uname'],
        password=data['password'],
        user_type_name='user',  # Default to regular user
        email=data.get('email'),
        phone=data.get('phone'),
        age=int(data.get('age')) if data.get('age') else None,
        gender=data.get('gender') or None,
        educational_level=data.get('educational_level') or None,
        cultural_background=data.get('cultural_background') or None,
        medical_conditions=data.get('medical_conditions') or None,
        medications=data.get('medications') or None,
        emergency_contact=data.get('emergency_contact') or None
    )
    return {"message": "Pendaftaran berhasil!", "user_id": user.id}


@user_bp.route('/login', methods=['POST'])
@api_response
def login():
    """User login."""
    data = request.get_json()
    user = UserManagerService.authenticate_user(data['uname'], data['password'])
    
    if user:
        login_user(user)
        return {"message": "Login berhasil", "user": {"id": user.id, "uname": user.uname, "type": user.user_type.name}}
    
    return {"message": "Nama pengguna atau kata sandi salah"}, 401


@user_bp.route('/logout', methods=['POST'])
@login_required
@api_response
def logout():
    """User logout."""
    logout_user()
    return {"message": "Logout berhasil"}


@user_bp.route('/profile', methods=['GET'])
@login_required
@api_response
def profile():
    """Get current user profile."""
    return {
        "user": {
            "id": current_user.id,
            "uname": current_user.uname,
            "email": current_user.email,
            "phone": current_user.phone,
            "age": current_user.age,
            "gender": current_user.gender,
            "educational_level": current_user.educational_level,
            "cultural_background": current_user.cultural_background,
            "medical_conditions": current_user.medical_conditions,
            "medications": current_user.medications,
            "emergency_contact": current_user.emergency_contact,
            "type": current_user.user_type.name,
            "is_admin": current_user.is_admin(),
            "is_active": current_user.is_active
        }
    }