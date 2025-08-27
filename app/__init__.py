from flask import Flask
from flask_login import LoginManager
from .config import Config
from .db import init_database, create_all_tables

login_manager = LoginManager()


def create_app():
    """Application factory pattern."""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    # Initialize our custom database singleton
    with app.app_context():
        init_database(app.config['SQLALCHEMY_DATABASE_URI'])
        create_all_tables()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    @login_manager.user_loader
    def load_user(user_id):  # pylint: disable=unused-variable
        from .services.shared.usManService import UserManagerService
        from .utils.auth_models import SimpleUser
        user_data = UserManagerService._get_user_data_by_id(int(user_id))
        if user_data:
            return SimpleUser(user_data)
        return None
    from .routes.auth_routes import auth_bp
    from .routes.main_routes import main_bp
    from .commands import register_commands
    from app.routes.admin.phq_routes import phq_bp
    from app.routes.admin.camera_routes import camera_bp
    from app.routes.admin.llm_routes import llm_bp
    from app.routes.admin.consent_routes import consent_bp
    from app.routes.assessment.llm_routes import llm_assessment_bp
    from app.routes.assessment.phq_routes import phq_assessment_bp
    app.register_blueprint(phq_bp)
    app.register_blueprint(camera_bp)
    app.register_blueprint(llm_bp)
    app.register_blueprint(consent_bp)
    app.register_blueprint(llm_assessment_bp)
    app.register_blueprint(phq_assessment_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    register_commands(app)
    return app
