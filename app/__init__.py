from flask import Flask
from flask_login import LoginManager
from .config import Config
from .db import init_database, create_all_tables

import os       
login_manager = LoginManager()
from app.ext.cache_buster import init_cache_buster
def create_app():
    """Application factory pattern."""
    # Configure static folder for production deployment
    if os.path.exists('/var/www/MLMH'):
        # Production: explicit static folder path
        static_folder = '/var/www/MLMH/app/static'
        template_folder = '/var/www/MLMH/app/templates'
        app = Flask(__name__, 
                   static_folder=static_folder,
                   template_folder=template_folder,
                   instance_relative_config=True)
    else:
        # Development: default relative paths
        app = Flask(__name__, instance_relative_config=True)
    init_cache_buster(app)
    app.config.from_object(Config)
    with app.app_context():
        init_database(app.config['SQLALCHEMY_DATABASE_URI'])
        # create_all_tables()
    login_manager.init_app(app)
    login_manager.login_view = 'main.auth_page'
    login_manager.login_message = "Silakan login untuk mengakses halaman ini."
    login_manager.login_message_category = "info"
    
    # Initialize media_save path for production deployment
    if os.path.exists('/var/www/MLMH'):
        # Production path
        app.media_save = '/var/www/MLMH/app/static/uploads'
    else:
        # Development path
        app.media_save = os.path.join(app.root_path, 'static', 'uploads')
    
    os.makedirs(app.media_save, exist_ok=True)

    @login_manager.user_loader
    def load_user(user_id):  # pylint: disable=unused-variable
        from .services.shared.usManService import UserManagerService
        from .utils.auth_models import SimpleUser
        user_data = UserManagerService._get_user_data_by_id(int(user_id))
        if user_data:
            return SimpleUser(user_data)
        return None

    @app.before_request
    def require_login():
        from flask import request, redirect, url_for
        from flask_login import current_user
        public_routes = [
            'main.auth_page',
            'auth.login', 
            'auth.register',
            'auth.forgot_password',
            'auth.reset_password',
            'auth.auto_login',
            'auth.verify_email',
            'auth.check_username_availability',
            'auth.send_otp',
            'auth.verify_otp',
            'auth.resend_otp',
            'static'
        ]
        if request.endpoint in public_routes:
            return
        if request.endpoint and request.endpoint.startswith('static'):
            return
        if not current_user.is_authenticated:
            return redirect(url_for('main.auth_page'))
        admin_routes = [
            'admin', 'phq', 'camera', 'llm', 'consent'
        ]
        if request.endpoint:
            for admin_prefix in admin_routes:
                if request.endpoint.startswith(admin_prefix + '.'):
                    if not current_user.is_admin():
                        # Redirect non-admin users to their dashboard
                        from flask import flash
                        flash('Akses admin diperlukan untuk halaman ini.', 'error')
                        return redirect(url_for('main.serve_index'))
                    break
    from .routes.auth_routes import auth_bp
    from .routes.main_routes import main_bp
    from .routes.admin_routes import admin_bp
    from .commands import register_commands
    from app.routes.admin.phq_routes import phq_bp
    from app.routes.admin.camera_routes import camera_bp
    from app.routes.admin.llm_routes import llm_bp
    from app.routes.admin.llm_analysis_routes import llm_analysis_bp
    from app.routes.admin.consent_routes import consent_bp as admin_consent_bp
    from app.routes.admin.session_management_routes import session_management_bp
    from app.routes.admin.profile import bp as admin_profile_bp
    from app.routes.consent_routes import consent_bp as user_consent_bp
    from app.routes.assessment_routes import assessment_bp
    from app.routes.assessment.llm_routes import llm_assessment_bp
    from app.routes.assessment.phq_routes import phq_assessment_bp
    from app.routes.assessment.camera_routes import camera_assessment_bp
    from app.routes.admin.export_routes import export_bp
    from app.routes.admin.facial_analysis_routes import facial_analysis_bp
    app.register_blueprint(admin_bp)
    app.register_blueprint(phq_bp)
    app.register_blueprint(camera_bp)
    app.register_blueprint(llm_bp)
    app.register_blueprint(llm_analysis_bp)
    app.register_blueprint(admin_consent_bp)
    app.register_blueprint(session_management_bp)
    app.register_blueprint(admin_profile_bp)
    app.register_blueprint(user_consent_bp)
    app.register_blueprint(assessment_bp)
    app.register_blueprint(llm_assessment_bp)
    app.register_blueprint(phq_assessment_bp)
    app.register_blueprint(camera_assessment_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(facial_analysis_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    register_commands(app)
    
    # Static files handled by nginx in production
    
    # Initialize APScheduler for background tasks
    from .services.schedulerService import init_scheduler
    init_scheduler(app)
    
    # Error handlers
    @app.errorhandler(403)
    def forbidden_error(error):
        from flask import render_template
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(404)
    def not_found_error(error):
        from flask import render_template
        return render_template('errors/404.html'), 404
    
    return app
