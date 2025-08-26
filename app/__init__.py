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
    login_manager.login_view = 'user.login'

    @login_manager.user_loader
    def load_user(user_id):  # pylint: disable=unused-variable
        from .services.shared.usManService import UserManagerService
        return UserManagerService.get_user_by_id(int(user_id))
    from .route.user_routes import user_bp
    from .route.main_routes import main_bp
    from .route.admin_routes import admin_bp
    from .commands import register_commands
    app.register_blueprint(user_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    register_commands(app)
    return app
