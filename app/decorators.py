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
    """
    Wrapper that returns [OLKORECT] on success or [SNAFU]: error on failure.
    
    WHEN TO USE:
    - For API endpoints that return JSON responses
    - Methods that will be called via AJAX/fetch requests
    - Service methods that need standardized API response format
    - Methods that return data to be consumed by frontend JavaScript
    
    EXAMPLES:
    - UserManagerService.create_user() - returns structured data for API
    - UserManagerService.get_user_by_id() - returns user data as JSON
    - Any CRUD operation called from frontend
    
    DO NOT USE FOR:
    - Internal helper methods like authenticate_user() (no decorator needed)
    - Methods called by Flask-Login (like _get_user_data_by_id())
    - Service methods that are only used internally by other services
    """
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
    """
    Wrapper that returns raw response on success or [SNAFU]: error on failure.
    
    WHEN TO USE:
    - For route handlers that return HTML templates
    - Methods that return Flask responses (render_template, redirect, etc.)
    - Endpoints that serve files or non-JSON content
    - Traditional web page routes (not API endpoints)
    
    EXAMPLES:
    - Route handlers that render templates
    - File upload/download endpoints
    - Routes that return redirects
    - Any endpoint that serves HTML pages
    
    DO NOT USE FOR:
    - Service layer methods (use api_response or no decorator)
    - Methods that only return data (use api_response)
    - Internal business logic methods
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)  # Return raw response (HTML, redirect, etc)
        except Exception as e:
            error_msg = f"[SNAFU]: {str(e)}\n{traceback.format_exc()}"
            return error_msg, 500
    return decorated_function
