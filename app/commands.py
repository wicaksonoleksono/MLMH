import click
from flask import current_app
from .model.shared.users import User
from .model.shared.enums import UserType
from .db import get_session, create_all_tables, get_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text


def register_commands(app):
    """Register all custom CLI commands with the Flask app."""

    @app.cli.command("init-db")
    def seed_db():
        """Seeds the database with minimal essential data."""
        click.echo("[OLKORECT] Seeding database with essential data...")
        create_all_tables()
        with get_session() as db:
            user_types = [
                {"name": "admin", "description": "Administrator user"},
                {"name": "user", "description": "Regular user"}
            ]
            for ut_data in user_types:
                existing = db.query(UserType).filter_by(name=ut_data["name"]).first()
                if not existing:
                    user_type_obj = UserType(**ut_data)
                    db.add(user_type_obj)
                    click.echo(f"  - UserType '{ut_data['name']}' created")

        with get_session() as db:
            admin_type = db.query(UserType).filter_by(name="admin").first()
            if admin_type:
                existing_admin = db.query(User).filter_by(uname="admin").first()
                if not existing_admin:
                    admin_user = User.create_user(
                        uname="admin",
                        password="admin",
                        user_type_id=admin_type.id
                    )
                    db.add(admin_user)
                    click.echo("  - Default admin user created (admin/admin)")

        with get_session() as db:
            user_type = db.query(UserType).filter_by(name="user").first()
            if user_type:
                existing_user = db.query(User).filter_by(uname="user").first()
                if not existing_user:
                    regular_user = User.create_user(
                        uname="user",
                        password="user",
                        user_type_id=user_type.id
                    )
                    db.add(regular_user)
                    click.echo("  - Default regular user created (user/user)")

        click.echo("[OLKORECT] Database seeding completed successfully!")
        click.echo("  - Admin can configure settings, assessments, and media via web UI")

    @app.cli.command("create-admin")
    @click.argument("username")
    @click.argument("password")
    @click.option("--email", default=None, help="Admin email address")
    def create_admin(username, password, email):
        """Create a new admin user."""
        with get_session() as db:
            admin_type = db.query(UserType).filter_by(name="admin").first()
            if not admin_type:
                click.echo("[SNAFU] Admin user type not found. Run 'seed-db' first.")
                return

            existing = db.query(User).filter_by(uname=username).first()
            if existing:
                click.echo(f"[SNAFU] User '{username}' already exists.")
                return

            try:
                admin_user = User.create_user(
                    uname=username,
                    password=password,
                    user_type_id=admin_type.id,
                    email=email
                )
                db.add(admin_user)
                click.echo(f"[OLKORECT] Admin user '{username}' created successfully!")
            except Exception as e:
                click.echo(f"[SNAFU] Error creating admin user: {str(e)}")

    @app.cli.command("reset-db")
    @click.confirmation_option(prompt="Are you sure you want to drop all tables?")
    def reset_db():
        """Drop all tables and recreate them."""
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
            conn.commit()

        click.echo("[WATCHOUT] All tables dropped.")

        # Now import models and recreate
        from .model.base import Base
        from .model.shared.users import User
        from .model.shared.enums import UserType, AssessmentStatus
        from .model.admin.phq import PHQCategory, PHQQuestion, PHQScale, PHQSettings
        from .model.admin.camera import CameraSettings
        from .model.admin.llm import LLMSettings
        from .model.assessment.sessions import AssessmentSession, PHQResponse, OpenQuestionResponse, CameraCapture, SessionExport

        Base.metadata.create_all(bind=engine)
        click.echo("[OLKORECT] Database tables recreated.")

    @app.cli.command("list-users")
    def list_users():
        """List all users in the database."""
        with get_session() as db:
            users = db.query(User).all()
            if not users:
                click.echo("No users found in database.")
                return

            click.echo("Users in database:")
            click.echo("-" * 50)
            for user in users:
                click.echo(
                    f"ID: {user.id} | Username: {user.uname} | Type: {user.user_type.name} | Active: {user.is_active}")

    @app.cli.command("ping-db")
    def ping_db():
        """Test database connection and show connection info."""
        with app.app_context():
            try:
                from sqlalchemy import text

                # Show current database URI (without password)
                db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
                if db_uri:
                    # Hide password for security
                    safe_uri = db_uri.split('@')[0].split(':')[:-1]
                    safe_uri = ':'.join(safe_uri) + ':***@' + db_uri.split('@')[1] if '@' in db_uri else db_uri
                    click.echo(f"Database URI: {safe_uri}")
                else:
                    click.echo("No database URI configured")

                # Test connection
                with get_session() as db:
                    result = db.execute(text("SELECT 1"))
                    click.echo("[OLKORECT] Database connection successful!")

                    # Show database info
                    if 'postgresql' in db_uri:
                        version_result = db.execute(text("SELECT version()"))
                        version = version_result.scalar()
                        click.echo(f"Database: {version}")

                        # Show current database name
                        db_name_result = db.execute(text("SELECT current_database()"))
                        db_name = db_name_result.scalar()
                        click.echo(f"Connected to database: {db_name}")

                        # Show current user
                        user_result = db.execute(text("SELECT current_user"))
                        current_user_name = user_result.scalar()
                        click.echo(f"Connected as user: {current_user_name}")

                    elif 'sqlite' in db_uri:
                        version_result = db.execute(text("SELECT sqlite_version()"))
                        version = version_result.scalar()
                        click.echo(f"SQLite version: {version}")

            except Exception as e:
                click.echo(f"[SNAFU] Database connection failed: {str(e)}")
                click.echo("Check your database configuration and ensure the database server is running.")
