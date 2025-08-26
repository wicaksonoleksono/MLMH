import click
from flask import current_app
from . import db
from .model.shared.users import User
from .model.shared.enums import UserType
from .model.admin.admin import SystemSetting, AssessmentConfig, MediaSetting, QuestionPool
from .model.assessment.sessions import AssessmentSession
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import json


def register_commands(app):
    """Register all custom CLI commands with the Flask app."""

    @app.cli.command("init-db")
    def init_db():
        """Creates all database tables from the models."""
        with app.app_context():
            db.create_all()
            click.echo("[OLKORECT] Database tables created.")

    @app.cli.command("seed-db")
    def seed_db():
        """Seeds the database with initial data."""
        with app.app_context():
            click.echo("[OLKORECT] Seeding database with initial data...")

            # Seed UserTypes
            user_types = [
                {"name": "admin", "description": "Administrator user"},
                {"name": "user", "description": "Regular user"}
            ]

            for ut_data in user_types:
                existing = db.session.query(UserType).filter_by(name=ut_data["name"]).first()
                if not existing:
                    user_type_obj = UserType(**ut_data)
                    db.session.add(user_type_obj)
                    click.echo(f"  - UserType '{ut_data['name']}' created")

            # Seed default admin user
            admin_type = db.session.query(UserType).filter_by(name="admin").first()
            user_type = db.session.query(UserType).filter_by(name="user").first()
            
            if admin_type:
                existing_admin = db.session.query(User).filter_by(uname="admin").first()
                if not existing_admin:
                    admin_user = User.create_user(
                        uname="admin",
                        password="admin",
                        user_type_id=admin_type.id,
                        email="admin@localhost"
                    )
                    db.session.add(admin_user)
                    click.echo("  - Default admin user created (admin/admin)")
            
            if user_type:
                existing_user = db.session.query(User).filter_by(uname="user").first()
                if not existing_user:
                    regular_user = User.create_user(
                        uname="user",
                        password="user",
                        user_type_id=user_type.id,
                        email="user@localhost"
                    )
                    db.session.add(regular_user)
                    click.echo("  - Default regular user created (user/user)")

            # Seed system settings
            system_settings = [
                {
                    "key": "app_name",
                    "value": "Mental Health Assessment",
                    "category": "system",
                    "description": "Application name"
                },
                {
                    "key": "session_timeout",
                    "value": "3600",
                    "data_type": "integer",
                    "category": "system",
                    "description": "Session timeout in seconds"
                },
                {
                    "key": "max_file_size",
                    "value": "52428800",
                    "data_type": "integer",
                    "category": "system",
                    "description": "Maximum file upload size in bytes"
                },
                {
                    "key": "enable_registration",
                    "value": "true",
                    "data_type": "boolean",
                    "category": "security",
                    "description": "Allow new user registration"
                }
            ]

            for setting_data in system_settings:
                existing = db.session.query(SystemSetting).filter_by(key=setting_data["key"]).first()
                if not existing:
                    setting = SystemSetting(**setting_data)
                    db.session.add(setting)
                    click.echo(f"  - System setting '{setting_data['key']}' created")

            # Seed PHQ assessment config
            phq_config_data = {
                "config_name": "PHQ-9 Standard",
                "assessment_type": "PHQ",
                "config_data": {
                    "scoring_method": "standard",
                    "interpretation_levels": {
                        "minimal": {"range": [0, 4], "label": "Depresi minimal"},
                        "mild": {"range": [5, 9], "label": "Depresi ringan"},
                        "moderate": {"range": [10, 14], "label": "Depresi sedang"},
                        "moderately_severe": {"range": [15, 19], "label": "Depresi cukup berat"},
                        "severe": {"range": [20, 27], "label": "Depresi berat"}
                    },
                    "auto_scoring": True
                },
                "description": "Standard PHQ-9 configuration for depression screening",
                "is_default": True,
                "created_by_admin": "system"
            }

            existing_phq = db.session.query(AssessmentConfig).filter_by(config_name="PHQ-9 Standard").first()
            if not existing_phq:
                phq_config = AssessmentConfig(**phq_config_data)
                db.session.add(phq_config)
                click.echo("  - PHQ-9 assessment config created")

            # Seed media settings
            media_settings = [
                {
                    "setting_name": "Camera Default",
                    "media_type": "camera",
                    "max_file_size_mb": 10,
                    "allowed_formats": ["jpg", "jpeg", "png"],
                    "camera_settings": {
                        "resolution": "1920x1080",
                        "format": "JPEG",
                        "quality": 85
                    },
                    "auto_process": True,
                    "processing_timeout_seconds": 300,
                    "storage_path": "uploads/camera",
                    "retention_days": 90
                },
                {
                    "setting_name": "Audio Default",
                    "media_type": "audio",
                    "max_file_size_mb": 50,
                    "allowed_formats": ["mp3", "wav", "m4a"],
                    "auto_process": True,
                    "processing_timeout_seconds": 600,
                    "storage_path": "uploads/audio",
                    "retention_days": 90
                }
            ]

            for media_data in media_settings:
                existing = db.session.query(MediaSetting).filter_by(setting_name=media_data["setting_name"]).first()
                if not existing:
                    media_setting = MediaSetting(**media_data)
                    db.session.add(media_setting)
                    click.echo(f"  - Media setting '{media_data['setting_name']}' created")

            # Seed PHQ question pool
            phq_questions = [
                "Sedikit minat atau kesenangan dalam melakukan aktivitas",
                "Merasa sedih, tertekan, atau putus asa",
                "Kesulitan tidur atau tertidur, atau terlalu banyak tidur",
                "Merasa lelah atau kurang energi",
                "Nafsu makan yang buruk atau makan berlebihan",
                "Merasa buruk tentang diri sendiri atau merasa gagal atau mengecewakan keluarga",
                "Kesulitan berkonsentrasi pada hal-hal seperti membaca koran atau menonton televisi",
                "Bergerak atau berbicara sangat lambat sehingga orang lain bisa menyadarinya, atau sebaliknya menjadi gelisah atau resah",
                "Berpikir bahwa lebih baik mati atau menyakiti diri sendiri dengan cara tertentu"
            ]

            phq_pool_data = {
                "pool_name": "PHQ-9 Indonesian",
                "question_type": "PHQ",
                "language": "id",
                "questions": [
                    {"id": i, "text": q, "response_options": [
                        {"value": 0, "text": "Tidak pernah"},
                        {"value": 1, "text": "Beberapa hari"},
                        {"value": 2, "text": "Lebih dari setengah hari"},
                        {"value": 3, "text": "Hampir setiap hari"}
                    ]} for i, q in enumerate(phq_questions)
                ],
                "pool_metadata": {
                    "source": "PHQ-9 Patient Health Questionnaire",
                    "version": "1.0",
                    "language_code": "id-ID"
                },
                "is_default": True,
                "randomize_order": False
            }

            existing_pool = db.session.query(QuestionPool).filter_by(pool_name="PHQ-9 Indonesian").first()
            if not existing_pool:
                question_pool = QuestionPool(**phq_pool_data)
                db.session.add(question_pool)
                click.echo("  - PHQ-9 question pool created")

            try:
                db.session.commit()
                click.echo("[OLKORECT] Database seeding completed successfully!")
            except IntegrityError as e:
                db.session.rollback()
                click.echo(f"[SNAFU] Error seeding database: {str(e)}")

    @app.cli.command("create-admin")
    @click.argument("username")
    @click.argument("password")
    @click.option("--email", default=None, help="Admin email address")
    def create_admin(username, password, email):
        """Create a new admin user."""
        with app.app_context():
            admin_type = db.session.query(UserType).filter_by(name="admin").first()
            if not admin_type:
                click.echo("[SNAFU] Admin user type not found. Run 'seed-db' first.")
                return

            existing = db.session.query(User).filter_by(uname=username).first()
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
                db.session.add(admin_user)
                db.session.commit()
                click.echo(f"[OLKORECT] Admin user '{username}' created successfully!")
            except Exception as e:
                db.session.rollback()
                click.echo(f"[SNAFU] Error creating admin user: {str(e)}")

    @app.cli.command("reset-db")
    @click.confirmation_option(prompt="Are you sure you want to drop all tables?")
    def reset_db():
        """Drop all tables and recreate them."""
        with app.app_context():
            db.drop_all()
            click.echo("[WATCHOUT] All tables dropped.")
            db.create_all()
            click.echo("[OLKORECT] Database tables recreated.")

    @app.cli.command("list-users")
    def list_users():
        """List all users in the database."""
        with app.app_context():
            users = db.session.query(User).all()
            if not users:
                click.echo("No users found in database.")
                return

            click.echo("Users in database:")
            click.echo("-" * 50)
            for user in users:
                click.echo(
                    f"ID: {user.id} | Username: {user.uname} | Type: {user.user_type.name} | Active: {user.is_active}")

    @app.cli.command("cleanup-sessions")
    @click.option("--days", default=30, help="Delete sessions older than N days")
    def cleanup_sessions(days):
        """Clean up old assessment sessions."""
        with app.app_context():
            from datetime import datetime, timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            old_sessions = db.session.query(AssessmentSession).filter(
                AssessmentSession.created_at < cutoff_date
            ).all()

            if not old_sessions:
                click.echo(f"No sessions older than {days} days found.")
                return

            count = len(old_sessions)
            for session in old_sessions:
                db.session.delete(session)

            db.session.commit()
            click.echo(f"[OLKORECT] Cleaned up {count} old sessions.")
