from functools import wraps
from flask import abort, jsonify
from flask_login import login_required, current_user
import traceback


def admin_required(f):
    """Decorator to require admin access."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def user_required(f):
    """Decorator to require user access (admin or regular user)."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not (current_user.is_admin() or current_user.is_user()):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def regular_user_only(f):
    """Decorator to allow only regular users (exclude admin)."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_user():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def api_response(f):
    """Wrapper that returns [OLKORECT] on success or [SNAFU]: error on failure."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            result = f(*args, **kwargs)
            
            # Handle tuple responses with status codes (e.g., return data, 401)
            if isinstance(result, tuple) and len(result) == 2:
                data, status_code = result
                if status_code >= 400:  # Error status codes
                    return jsonify({"status": "SNAFU", "error": data.get("message", "Unknown error")}), status_code
                else:
                    return jsonify({"status": "OLKORECT", "data": data}), status_code
            
            # Regular response
            return jsonify({"status": "OLKORECT", "data": result})
        except Exception as e:
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            return jsonify({"status": "SNAFU", "error": error_msg}), 500
    return decorated_function


def raw_response(f):
    """Wrapper that returns raw response on success or [SNAFU]: error on failure."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)  # Return raw response (HTML, redirect, etc)
        except Exception as e:
            error_msg = f"[SNAFU]: {str(e)}\n{traceback.format_exc()}"
            return error_msg, 500
    return decorated_function