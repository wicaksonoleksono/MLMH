from flask import Flask
from flask_login import LoginManager
from .config import Config
from .db import init_database, create_all_tables

import os       
login_manager = LoginManager()

def create_app():
    """Application factory pattern."""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    with app.app_context():
        init_database(app.config['SQLALCHEMY_DATABASE_URI'])
        create_all_tables()
    login_manager.init_app(app)
    login_manager.login_view = 'main.auth_page'
    login_manager.login_message = "Silakan login untuk mengakses halaman ini."
    login_manager.login_message_category = "info"

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
        # haha what the helly 
        app.media_save = os.path.join(app.root_path,'static','uploads')
        os.makedirs(app.media_save, exist_ok=True)
        public_routes = [
            'main.auth_page',
            'auth.login', 
            'auth.register',
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
    from app.routes.admin.consent_routes import consent_bp
    from app.routes.consent_routes import consent_bp as user_consent_bp
    from app.routes.assessment_routes import assessment_bp
    from app.routes.assessment.llm_routes import llm_assessment_bp
    from app.routes.assessment.phq_routes import phq_assessment_bp
    from app.routes.assessment.camera_routes import camera_assessment_bp
    from app.routes.admin.export_routes import export_bp
    app.register_blueprint(admin_bp)
    app.register_blueprint(phq_bp)
    app.register_blueprint(camera_bp)
    app.register_blueprint(llm_bp)
    app.register_blueprint(consent_bp)
    app.register_blueprint(user_consent_bp)
    app.register_blueprint(assessment_bp)
    app.register_blueprint(llm_assessment_bp)
    app.register_blueprint(phq_assessment_bp)
    app.register_blueprint(camera_assessment_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    register_commands(app)
    return app
