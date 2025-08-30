import click
from flask import current_app
from .model.shared.users import User
from .model.shared.enums import UserType
from .db import get_session, create_all_tables, get_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text


def register_commands(app):
    """Register all custom CLI commands with the Flask app."""

    @app.cli.command("seed-db")
    @click.confirmation_option(prompt="This will drop all tables and recreate them. Are you sure?")
    def seed_db_combined():
        """Reset database and seed with fresh data."""
        click.echo("[OLKORECT] Resetting and seeding database...")
        
        # First reset the database (drop and recreate)
        click.echo("  - Dropping all tables...")
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
            conn.commit()
        click.echo("  ✓ Database reset completed")
        
        # Then initialize with fresh data
        click.echo("  - Seeding with fresh data...")
        _seed_database()
        
        click.echo("[OLKORECT] Database reset and seeding completed successfully!")

    @app.cli.command("init-db")
    def init_db():
        """Initialize database with essential data (no reset)."""
        _seed_database()

    def _seed_database():
        """Internal function to seed database with essential data."""
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

        # Seed default admin settings
        click.echo("  - Creating default admin settings...")
        
        # Create default PHQ settings
        from .model.admin.phq import PHQSettings, PHQScale, PHQQuestion, PHQCategoryType
        with get_session() as db:
            # Create default PHQ scale
            existing_scale = db.query(PHQScale).filter_by(is_default=True).first()
            if not existing_scale:
                default_scale = PHQScale(
                    scale_name="PHQ-9 Standard Scale",
                    min_value=0,
                    max_value=3,
                    scale_labels={
                        0: "Tidak sama sekali",
                        1: "Beberapa hari", 
                        2: "Lebih dari setengah hari",
                        3: "Hampir setiap hari"
                    },
                    is_default=True,
                    # is_active=True
                )
                db.add(default_scale)
                db.flush()
                scale_id = default_scale.id
            else:
                scale_id = existing_scale.id
            
            # Create default PHQ settings
            existing_phq_settings = db.query(PHQSettings).filter_by(is_default=True).first()
            if not existing_phq_settings:
                default_phq_settings = PHQSettings(
                    questions_per_category=1,
                    scale_id=scale_id,
                    randomize_categories=False,
                    instructions="Dalam 2 minggu terakhir, seberapa sering Anda terganggu oleh masalah-masalah berikut?",
                    is_default=True,
                    is_active=True
                )
                db.add(default_phq_settings)
                click.echo("    ✓ Default PHQ settings created")
            
            # Create sample PHQ questions if none exist
            existing_questions = db.query(PHQQuestion).first()
            if not existing_questions:
                sample_questions = [
                    {
                        "category_name_id": "ANHEDONIA",
                        "question_text_en": "Little interest or pleasure in doing things",
                        "question_text_id": "Kurang tertarik atau bergairah dalam melakukan apapun",
                        "order_index": 1
                    },
                    {
                        "category_name_id": "DEPRESSED_MOOD", 
                        "question_text_en": "Feeling down, depressed, or hopeless",
                        "question_text_id": "Merasa murung, muram, atau putus asa",
                        "order_index": 2
                    },
                    {
                        "category_name_id": "SLEEP_DISTURBANCE",
                        "question_text_en": "Trouble falling or staying asleep, or sleeping too much", 
                        "question_text_id": "Sulit tidur atau mudah terbangun, atau terlalu banyak tidur",
                        "order_index": 3
                    },
                    {
                        "category_name_id": "APPETITE_CHANGES",
                        "question_text_en": "Poor appetite or overeating",
                        "question_text_id": "Nafsu makan berkurang atau makan berlebihan", 
                        "order_index": 4
                    },
                    {
                        "category_name_id": "WORTHLESSNESS",
                        "question_text_en": "Feeling bad about yourself or that you are a failure",
                        "question_text_id": "Merasa tidak berharga atau merasa gagal",
                        "order_index": 5
                    },
                    {
                        "category_name_id": "CONCENTRATION", 
                        "question_text_en": "Trouble concentrating on things",
                        "question_text_id": "Sulit berkonsentrasi pada sesuatu",
                        "order_index": 6
                    },
                    {
                        "category_name_id": "PSYCHOMOTOR",
                        "question_text_en": "Moving or speaking slowly, or being fidgety/restless",
                        "question_text_id": "Bergerak atau berbicara lambat, atau gelisah/tidak bisa diam",
                        "order_index": 7
                    },
                    {
                        "category_name_id": "SUICIDAL_IDEATION",
                        "question_text_en": "Thoughts that you would be better off dead",
                        "question_text_id": "Pikiran bahwa Anda lebih baik mati",
                        "order_index": 8
                    }
                ]
                
                for q_data in sample_questions:
                    question = PHQQuestion(**q_data, is_active=True)
                    db.add(question)
                click.echo("    ✓ Sample PHQ questions created")

        # Create default LLM settings
        from .model.admin.llm import LLMSettings
        with get_session() as db:
            existing_llm_settings = db.query(LLMSettings).filter_by(is_default=True).first()
            if not existing_llm_settings:
                default_llm_settings = LLMSettings(
                    openai_api_key="set-it dude",  # Must be set by admin
                    chat_model="gpt-4o",
                    analysis_model="gpt-4o-mini", 
                    depression_aspects={
                        "aspects": [
                            {"name": "Anhedonia", "description": "Loss of interest or pleasure"},
                            {"name": "Depressed Mood", "description": "Feeling sad or hopeless"},
                            {"name": "Sleep Disturbance", "description": "Sleep problems"}
                        ]
                    },
                    instructions="Masukan instruksi.",
                    is_default=True,
                    is_active=True
                )
                db.add(default_llm_settings)
                click.echo("    ✓ Default LLM settings created")

        # Create default Camera settings 
        from .model.admin.camera import CameraSettings
        with get_session() as db:
            existing_camera_settings = db.query(CameraSettings).filter_by(is_default=True).first()
            if not existing_camera_settings:
                default_camera_settings = CameraSettings(
                    recording_mode="INTERVAL",
                    interval_seconds=1,
                    resolution="640x480",
                    storage_path=current_app.media_save,
                    capture_on_button_click=True,
                    capture_on_message_send=False,
                    capture_on_question_start=False,
                    is_default=True,
                    is_active=True
                )
                db.add(default_camera_settings)
                click.echo("    ✓ Default camera settings created")

        # Create default Consent settings
        from .model.admin.consent import ConsentSettings
        with get_session() as db:
            existing_consent_settings = db.query(ConsentSettings).filter_by(is_default=True).first()
            if not existing_consent_settings:
                default_consent_settings = ConsentSettings(
                    title="Informed Consent Form",  # Default title
                    content="Please configure the informed consent content in the admin panel.",  # Must be set by admin
                    is_default=True,
                    is_active=True
                )
                db.add(default_consent_settings)
                click.echo("    ✓ Default consent settings created")

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
        from .model.admin.phq import PHQQuestion, PHQScale, PHQSettings
        from .model.admin.camera import CameraSettings
        from .model.admin.llm import LLMSettings
        from .model.admin.consent import ConsentSettings
        from .model.assessment.sessions import AssessmentSession, PHQResponse, LLMConversation, LLMAnalysisResult, CameraCapture, SessionExport

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
