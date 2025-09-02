from flask import Blueprint, request, redirect, url_for, jsonify, render_template, flash
from flask_login import login_user, logout_user, login_required, current_user
from ..services.shared.usManService import UserManagerService
from ..decorators import raw_response, api_response
from ..utils.jwt_utils import JWTManager

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
@raw_response
def login():
    """User login with JWT token."""
    if request.method == 'GET':
        if current_user.is_authenticated:
            return redirect(url_for('main.serve_index'))
        return render_template('auth/login.html')
    
    # Handle POST request
    if request.is_json:
        # Handle API request (JSON)
        data = request.get_json()
        username = data['uname']
        password = data['password']
    else:
        # Handle form submission
        username = request.form.get('username')
        password = request.form.get('password')

    user_data = UserManagerService.authenticate_user(username, password)

    if user_data:
        token = JWTManager.generate_token(user_data)

        # Create SimpleUser for Flask-Login session support (for templates)
        from ..utils.auth_models import SimpleUser
        simple_user = SimpleUser(user_data)
        login_user(simple_user)

        # If this was a form submission, redirect to index
        if not request.is_json:
            return redirect(url_for('main.serve_index'))

        # If this was an API request, return JSON
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

    # If this was a form submission, show error and redisplay form
    if not request.is_json:
        flash('Nama pengguna atau kata sandi salah.', 'error')
        return render_template('auth/login.html'), 401

    # If this was an API request, return JSON error
    return {"status": "SNAFU", "error": "Nama pengguna atau kata sandi salah"}, 401


@auth_bp.route('/register', methods=['GET', 'POST'])
@raw_response
def register():
    """User registration."""
    if request.method == 'GET':
        if current_user.is_authenticated:
            return redirect(url_for('main.serve_index'))
        return render_template('auth/register.html')
    
    # Handle POST request
    if request.is_json:
        # Handle API request (JSON)
        data = request.get_json()
    else:
        # Handle form submission
        # Validate required fields
        required_fields = ['username', 'email', 'password', 'confirm_password', 'age', 'gender', 'educational_level', 'cultural_background']
        for field in required_fields:
            if not request.form.get(field):
                flash(f'Field {field} harus diisi.', 'error')
                return render_template('auth/register.html'), 400
        
        # Validate password confirmation
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Kata sandi dan konfirmasi kata sandi tidak cocok.', 'error')
            return render_template('auth/register.html'), 400
            
        if len(password) < 6:
            flash('Kata sandi harus minimal 6 karakter.', 'error')
            return render_template('auth/register.html'), 400
        
        # Create data dict from form
        data = {
            'uname': request.form.get('username'),
            'password': password,
            'email': request.form.get('email'),
            'phone': None,  # We don't collect phone in the new form
            'age': int(request.form.get('age')) if request.form.get('age') else None,
            'gender': request.form.get('gender') or None,
            'educational_level': request.form.get('educational_level') or None,
            'cultural_background': request.form.get('cultural_background') or None,
            'medical_conditions': request.form.get('medical_conditions') or None,
            'medications': request.form.get('medications') or None,
            'emergency_contact': request.form.get('emergency_contact') or None
        }

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
        
        # If this was a form submission, show success message and redirect
        if not request.is_json:
            flash('Pendaftaran berhasil! Silakan masuk dengan akun Anda.', 'success')
            return redirect(url_for('auth.login'))
        
        # If this was an API request, return JSON
        return {"message": "Pendaftaran berhasil!"}
    except ValueError as e:
        # If this was a form submission, show error message
        if not request.is_json:
            flash(str(e), 'error')
            return render_template('auth/register.html'), 400
        
        # If this was an API request, return JSON error
        return {"error": str(e)}, 400


@auth_bp.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    """User logout."""
    logout_user()
    
    # For GET requests (link clicks), redirect to auth page
    if request.method == 'GET':
        return redirect(url_for('main.auth_page'))
    
    # For POST requests (API calls), return JSON
    return jsonify({"message": "Logout berhasil"})


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
