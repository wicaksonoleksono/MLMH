from flask import Blueprint, request, redirect, url_for, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from ..services.shared.usManService import UserManagerService
from ..decorators import raw_response, api_response
from ..utils.jwt_utils import JWTManager

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/register', methods=['POST'])
@api_response
def register():
    """User registration."""
    data = request.get_json()

    # Extract extended profile fields (only for regular users)
    try:
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
        return {"message": "Pendaftaran berhasil!"}
    except ValueError as e:
        return {"error": str(e)}, 400


@auth_bp.route('/login', methods=['POST'])
@raw_response
def login():
    """User login with JWT token."""
    data = request.get_json()
    user_data = UserManagerService.authenticate_user(data['uname'], data['password'])

    if user_data:
        token = JWTManager.generate_token(user_data)

        # Create SimpleUser for Flask-Login session support (for templates)
        from ..utils.auth_models import SimpleUser
        simple_user = SimpleUser(user_data)
        login_user(simple_user)

        return {
            "status": "OLKORECT",
            "message": "Login berhasil",
            "data": {
                "token": token,
                "user": {
                    "id": user_data['id'],
                    "uname": user_data['uname'],
                    "type": user_data['user_type_name'],
                    "is_admin": user_data['is_admin']
                }
            }
        }

    return {"status": "SNAFU", "error": "Nama pengguna atau kata sandi salah"}, 401


@auth_bp.route('/logout', methods=['POST'])
@login_required
@api_response
def logout():
    """User logout."""
    logout_user()
    return {"message": "Logout berhasil"}


@auth_bp.route('/profile', methods=['GET'])
@login_required
@raw_response
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
            "type": current_user.user_type_name,
            "is_admin": current_user.is_admin(),
            "is_active": current_user.is_active
        }
    }
