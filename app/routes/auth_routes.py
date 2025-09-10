from flask import Blueprint, request, redirect, url_for, jsonify, render_template, flash
from flask_login import login_user, logout_user, login_required, current_user
from ..services.shared.usManService import UserManagerService
from ..services.shared.emailOTPService import EmailOTPService
from ..services.shared.passwordResetService import PasswordResetService
from ..services.shared.autoLoginService import AutoLoginService
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
        # Check if user's email is verified
        if user_data.get('email') and not user_data.get('email_verified', False):
            # User exists but email not verified - show OTP modal on login page
            if not request.is_json:
                flash('Email Anda belum diverifikasi. Silakan masukkan kode OTP yang telah dikirim.', 'warning')
                return redirect(url_for('auth.login', otp_user_id=user_data['id']))
            else:
                return {"status": "SNAFU", "error": "Email belum diverifikasi", "requires_otp": True, "user_id": user_data['id']}, 403
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
            'phone': request.form.get('phone') or None,
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
        
        # Schedule user for deletion in 12 hours if email not verified
        if user.email:
            from datetime import datetime, timedelta
            from ..db import get_session
            with get_session() as db:
                # Refresh user object in current session
                user = db.merge(user)
                user.deletion_scheduled_at = datetime.utcnow() + timedelta(hours=12)
                db.commit()
        
        # Send OTP email if user provided email
        if user.email:
            try:
                otp_result = EmailOTPService.send_otp_email(user.id)
                if otp_result["status"] == "success":
                    success_message = 'Pendaftaran berhasil! Kode OTP telah dikirim ke email Anda. Silakan cek inbox dan masukkan kode 6 digit untuk verifikasi.'
                else:
                    success_message = f'Pendaftaran berhasil! Namun gagal mengirim OTP: {otp_result["message"]}'
            except Exception as e:
                print(f"Failed to send OTP email: {e}")
                success_message = 'Pendaftaran berhasil! Namun OTP gagal dikirim. Anda dapat meminta pengiriman ulang setelah login.'
        else:
            success_message = 'Pendaftaran berhasil! Silakan masuk dengan akun Anda.'
        
        # If this was a form submission, redirect to register page with OTP modal
        if not request.is_json:
            flash(success_message, 'success')
            return redirect(url_for('auth.register', otp_user_id=user.id))
        
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


@auth_bp.route('/verify-email/<token>', methods=['GET'])
@raw_response
def verify_email(token):
    """Verify email address using verification token."""
    result = EmailVerificationService.verify_email_token(token)
    
    if result["status"] == "success":
        flash('Email berhasil diverifikasi! Sekarang Anda dapat menggunakan semua fitur platform.', 'success')
        return redirect(url_for('auth.login'))
    else:
        flash(f'Verifikasi email gagal: {result["message"]}', 'error')
        return redirect(url_for('auth.login'))


@auth_bp.route('/send-otp', methods=['POST'])
@api_response
def send_otp():
    """Send OTP to user's email."""
    data = request.get_json()
    user_id = data.get('user_id')
    
    if not user_id:
        return {"message": "User ID diperlukan"}, 400
    
    result = EmailOTPService.send_otp_email(user_id)
    
    if result["status"] == "success":
        return {"message": "Kode OTP telah dikirim ke email Anda"}
    else:
        return {"message": result["message"]}, 400


@auth_bp.route('/verify-otp', methods=['POST'])
@api_response
def verify_otp():
    """Verify OTP code."""
    data = request.get_json()
    user_id = data.get('user_id')
    otp_code = data.get('otp_code', '').strip()
    
    if not user_id or not otp_code:
        return {"message": "User ID dan kode OTP diperlukan"}, 400
    
    if len(otp_code) != 6 or not otp_code.isdigit():
        return {"message": "Kode OTP harus 6 digit angka"}, 400
    
    result = EmailOTPService.verify_otp(user_id, otp_code)
    
    if result["status"] == "success":
        return {"message": "Email berhasil diverifikasi!", "username": result.get("username")}
    else:
        return {"message": result["message"]}, 400


@auth_bp.route('/resend-otp', methods=['POST'])
@api_response
def resend_otp():
    """Resend OTP code."""
    data = request.get_json()
    user_id = data.get('user_id')
    
    if not user_id:
        return {"message": "User ID diperlukan"}, 400
    
    if not EmailOTPService.can_resend_otp(user_id):
        return {"message": "Silakan tunggu 5 menit sebelum mengirim ulang kode OTP"}, 429
    
    result = EmailOTPService.send_otp_email(user_id)
    
    if result["status"] == "success":
        return {"message": "Kode OTP baru telah dikirim ke email Anda"}
    else:
        return {"message": result["message"]}, 400


@auth_bp.route('/check-username', methods=['POST'])
@api_response
def check_username_availability():
    """Check if username is available for registration."""
    data = request.get_json()
    username = data.get('username', '').strip()
    
    if not username:
        return {"available": False, "message": "Username tidak boleh kosong"}
    
    if len(username) < 3 or len(username) > 50:
        return {"available": False, "message": "Username harus 3-50 karakter"}
    
    import re
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return {"available": False, "message": "Username hanya boleh huruf, angka, dan underscore"}
    
    # Check if username exists
    try:
        existing_user = UserManagerService.get_user_by_username(username)
        if existing_user:
            return {"available": False, "message": "Username sudah digunakan"}
        
        return {"available": True, "message": "Username tersedia"}
    except Exception as e:
        print(f"Username check error: {e}")
        return {"available": False, "message": "Gagal mengecek username"}


@auth_bp.route('/verification-status', methods=['GET'])
@login_required
@api_response
def verification_status():
    """Get verification status for current user."""
    return {
        "email_verified": current_user.email_verified if hasattr(current_user, 'email_verified') else False,
        "can_resend_otp": EmailOTPService.can_resend_otp(current_user.id) if hasattr(current_user, 'email_verified') and not current_user.email_verified else False
    }


@auth_bp.route('/cleanup-expired-users', methods=['POST'])
@api_response  
def cleanup_expired_users():
    """Manual cleanup of expired OTP users - DANGER ZONE."""
    # This could be protected with admin auth if needed
    result = EmailOTPService.force_cleanup_expired_users()
    return {
        "message": f"Cleanup complete: {result['deleted_users']} users deleted, {result['cleaned_otps']} OTPs cleaned",
        "deleted_users": result['deleted_users'],
        "cleaned_otps": result['cleaned_otps']
    }


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
@raw_response
def forgot_password():
    """Request password reset magic link."""
    if request.method == 'GET':
        if current_user.is_authenticated:
            return redirect(url_for('main.serve_index'))
        return render_template('auth/forgot_password.html')
    
    # Handle POST request
    if request.is_json:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
    else:
        email = request.form.get('email', '').strip().lower()
    
    if not email:
        message = "Email harus diisi."
        if request.is_json:
            return {"status": "error", "message": message}, 400
        flash(message, 'error')
        return render_template('auth/forgot_password.html'), 400
    
    # Check rate limiting
    if not PasswordResetService.can_request_reset(email):
        message = "Silakan tunggu 5 menit sebelum meminta reset password lagi."
        if request.is_json:
            return {"status": "error", "message": message}, 429
        flash(message, 'error')
        return render_template('auth/forgot_password.html'), 429
    
    # Send reset email (always returns success for security)
    result = PasswordResetService.send_password_reset_email(email)
    
    success_message = "Jika email terdaftar, link reset password telah dikirim. Silakan cek inbox Anda."
    
    if request.is_json:
        return {"status": "success", "message": success_message}
    
    flash(success_message, 'success')
    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password', methods=['GET', 'POST'])
@raw_response
def reset_password():
    """Reset password using magic link token."""
    token = request.args.get('token') or request.form.get('token')
    
    if not token:
        flash('Invalid atau missing reset token.', 'error')
        return redirect(url_for('auth.forgot_password'))
    
    if request.method == 'GET':
        # Validate token and show reset form
        result = PasswordResetService.validate_reset_token(token)
        
        if result['status'] == 'error':
            flash(result['message'], 'error')
            return redirect(url_for('auth.forgot_password'))
        
        return render_template('auth/reset_password.html', 
                             token=token, 
                             username=result['username'])
    
    # Handle POST request
    if request.is_json:
        data = request.get_json()
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')
    else:
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
    
    if not new_password or not confirm_password:
        message = "Semua field harus diisi."
        if request.is_json:
            return {"status": "error", "message": message}, 400
        flash(message, 'error')
        return render_template('auth/reset_password.html', token=token), 400
    
    if new_password != confirm_password:
        message = "Password dan konfirmasi password tidak cocok."
        if request.is_json:
            return {"status": "error", "message": message}, 400
        flash(message, 'error')
        return render_template('auth/reset_password.html', token=token), 400
    
    if len(new_password) < 6:
        message = "Password harus minimal 6 karakter."
        if request.is_json:
            return {"status": "error", "message": message}, 400
        flash(message, 'error')
        return render_template('auth/reset_password.html', token=token), 400
    
    # Reset password
    result = PasswordResetService.reset_password(token, new_password)
    
    if result['status'] == 'success':
        # Check if auto-login URL was generated
        auto_login_url = result.get('auto_login_url')
        
        if request.is_json:
            return {
                "status": "success", 
                "message": "Password berhasil direset!",
                "auto_login_url": auto_login_url
            }
        
        # For web requests, show success page with auto-login option
        if auto_login_url:
            return render_template('auth/password_reset_success.html', 
                                 username=result['username'],
                                 auto_login_url=auto_login_url)
        else:
            flash("Password berhasil direset! Silakan login dengan password baru Anda.", 'success')
            return redirect(url_for('auth.login'))
    else:
        if request.is_json:
            return {"status": "error", "message": result['message']}, 400
        flash(result['message'], 'error')
        return redirect(url_for('auth.forgot_password'))


@auth_bp.route('/auto-login')
@raw_response
def auto_login():
    """Auto-login using JWT token from email links."""
    token = request.args.get('token')
    custom_redirect = request.args.get('redirect')
    
    if not token:
        flash('Link auto-login tidak valid atau sudah expired.', 'error')
        return redirect(url_for('auth.login'))
    
    # Validate auto-login token
    validation_result = AutoLoginService.validate_auto_login_token(token)
    
    if not validation_result['valid']:
        flash(f'Auto-login gagal: {validation_result["error"]}', 'error')
        return redirect(url_for('auth.login'))
    
    user_data = validation_result['user_data']
    
    # Create SimpleUser for Flask-Login session support
    from ..utils.auth_models import SimpleUser
    simple_user = SimpleUser(user_data)
    login_user(simple_user)
    
    # Determine redirect URL
    redirect_to = custom_redirect or validation_result['redirect_to']
    if not redirect_to:
        redirect_to = AutoLoginService.get_redirect_url_for_user(user_data)
    
    # Add success flash message based on purpose
    purpose = validation_result.get('purpose', '')
    if 'session2' in purpose:
        flash(f'Selamat datang kembali, {user_data["uname"]}! Anda siap untuk melanjutkan Sesi 2.', 'success')
    elif 'password_reset' in purpose:
        flash(f'Login berhasil, {user_data["uname"]}! Password Anda telah berhasil direset.', 'success')
    else:
        flash(f'Selamat datang, {user_data["uname"]}!', 'success')
    
    # Invalidate single-use token after successful login
    if validation_result.get('single_use') and validation_result.get('jti'):
        AutoLoginService.invalidate_auto_login_token(validation_result['jti'])
    
    return redirect(redirect_to)
