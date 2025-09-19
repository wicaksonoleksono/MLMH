import click
from flask import current_app
from .model.shared.users import User
from .model.shared.enums import UserType
from .model.shared.auto_login_tokens import AutoLoginToken
from .model.assessment.sessions import (
    EmailNotification, AssessmentSession, PHQResponse, 
    LLMConversation, LLMAnalysisResult, CameraCapture, 
    SessionExport
)
from .db import get_session, create_all_tables, get_engine
from .services.SMTP.emailNotificationService import EmailNotificationService
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text


def register_commands(app):
    """Register all custom CLI commands with the Flask app."""

    @app.cli.command("seed-db")
    @click.option('-d', '--dev', is_flag=True, help='Create additional test user for development')
    @click.confirmation_option(prompt="This will drop all tables and recreate them. Are you sure?")
    def seed_db_combined(dev):
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
        _seed_database(dev_mode=dev)
        
        click.echo("[OLKORECT] Database reset and seeding completed successfully!")

    @app.cli.command("init-db")
    def init_db():
        """Initialize database with essential data (no reset)."""
        _seed_database()

    def _seed_database(dev_mode=False):
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
                        user_type_id=admin_type.id,
                        email="admin@example.com"  # Give admin an email too
                    )
                    # For testing purposes, mark email as verified
                    admin_user.email_verified = True
                    db.add(admin_user)
                    click.echo("  - Default admin user created (admin/admin) with verified email")

        # Create test user if dev mode is enabled
        if dev_mode:
            with get_session() as db:
                user_type = db.query(UserType).filter_by(name="user").first()
                if user_type:
                    existing_test_user = db.query(User).filter_by(uname="testuser").first()
                    if not existing_test_user:
                        test_user = User.create_user(
                            uname="testuser",
                            password="testpass",
                            user_type_id=user_type.id,
                            email="test@example.com"
                        )
                        test_user.email_verified = True
                        db.add(test_user)
                        click.echo("  - Test user created (testuser/testpass) with verified email")

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
                import os 
                default_llm_settings = LLMSettings(
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
                # Set encrypted API key from environment or empty string
                api_key = os.getenv("OPENAI_API_KEY")
                if api_key:
                    default_llm_settings.set_api_key(api_key)
                else:
                    # Set empty encrypted key to satisfy NOT NULL constraint
                    default_llm_settings.set_api_key("")
                db.add(default_llm_settings)
                click.echo("    ✓ Default LLM settings created")

        # Create default Camera settings 
        from .model.admin.camera import CameraSettings
        with get_session() as db:
            existing_camera_settings = db.query(CameraSettings).filter_by(is_default=True).first()
            if not existing_camera_settings:
                # Compute media save path for production deployment
                if os.path.exists('/var/www/MLMH'):
                    # Production path
                    media_save_path = '/var/www/MLMH/app/static/uploads'
                else:
                    # Development path
                    media_save_path = os.path.join(current_app.root_path, 'static', 'uploads')
                
                os.makedirs(media_save_path, exist_ok=True)
                
                default_camera_settings = CameraSettings(
                    recording_mode="INTERVAL",
                    interval_seconds=1,
                    resolution="640x480",
                    storage_path=media_save_path,
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
                # Admin users created via server commands are automatically verified
                admin_user.email_verified = True
                db.add(admin_user)
                click.echo(f"[OLKORECT] Admin user '{username}' created successfully with verified email!")
            except Exception as e:
                click.echo(f"[SNAFU] Error creating admin user: {str(e)}")
    @app.cli.command("create-admin-random")
    @click.argument("username")
    def create_admin_random(username):
        """Create a new admin user with a randomly generated 13-character password."""
        import secrets
        import string
        
        # Generate a random 13-character password
        alphabet = string.ascii_letters + string.digits
        password = ''.join(secrets.choice(alphabet) for _ in range(13))
        
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
                    user_type_id=admin_type.id
                )
                # Admin users created via server commands are automatically verified
                admin_user.email_verified = True
                db.add(admin_user)
                click.echo(f"[OLKORECT] Admin user '{username}' created successfully with verified email!")
                click.echo(f"[OLKORECT] Generated password: {password}")
            except Exception as e:
                click.echo(f"[SNAFU] Error creating admin user: {str(e)}")

    @app.cli.command("create-bulk-admins")
    def create_bulk_admins():
        """Create predefined admin users with random passwords and print credentials."""
        import secrets
        import string
        
        # Predefined usernames
        usernames = [
            "samudera",
            "rangga",
            "fadhil",
            "baqi",
            "oriza",
            "wicak",
            "waffiq"
        ]
        
        # Generate a random 13-character password
        def generate_password():
            alphabet = string.ascii_letters + string.digits
            return ''.join(secrets.choice(alphabet) for _ in range(13))
        
        created_users = []
        
        with get_session() as db:
            admin_type = db.query(UserType).filter_by(name="admin").first()
            if not admin_type:
                click.echo("[SNAFU] Admin user type not found. Run 'seed-db' first.")
                return

            for username in usernames:
                existing = db.query(User).filter_by(uname=username).first()
                if existing:
                    click.echo(f"[SNAFU] User '{username}' already exists, skipping...")
                    continue

                try:
                    password = generate_password()
                    admin_user = User.create_user(
                        uname=username,
                        password=password,
                        user_type_id=admin_type.id
                    )
                    # Admin users created via server commands are automatically verified
                    admin_user.email_verified = True
                    db.add(admin_user)
                    created_users.append((username, password))
                    click.echo(f"[OLKORECT] Admin user '{username}' created successfully with verified email!")
                except Exception as e:
                    click.echo(f"[SNAFU] Error creating admin user '{username}': {str(e)}")
            
            db.commit()
            
        if created_users:
            click.echo("\n[OLKORECT] All admin users created successfully!")
            click.echo("\nGenerated credentials:")
            click.echo("-" * 40)
            for username, password in created_users:
                click.echo(f"Username: {username}")
                click.echo(f"Password: {password}")
                click.echo("-" * 40)
        else:
            click.echo("[SNAFU] No new admin users were created.")

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

    @app.cli.command("send-emails")
    def send_scheduled_emails():
        """Send scheduled email notifications (run via cron)"""
        click.echo("[OLKORECT] Processing scheduled email notifications...")
        
        try:
            processed_count = EmailNotificationService.process_scheduled_notifications()
            click.echo(f"[OLKORECT] Processed {processed_count} scheduled notifications")
            
            # Also retry failed notifications
            retried_count = EmailNotificationService.retry_failed_notifications()
            if retried_count > 0:
                click.echo(f"[OLKORECT] Retried {retried_count} failed notifications")
                
        except Exception as e:
            click.echo(f"[SNAFU] Error processing notifications: {str(e)}")

    @app.cli.command("list-pending-emails")
    def list_pending_emails():
        """List pending email notifications"""
        try:
            pending = EmailNotificationService.get_pending_notifications(50)
            
            if not pending:
                click.echo("No pending notifications")
                return
            
            click.echo(f"[OLKORECT] {len(pending)} pending notifications:")
            click.echo("-" * 50)
            
            for notification in pending:
                status_text = "PENDING" if notification.status == "PENDING" else "FAILED"
                scheduled_time = notification.scheduled_send_at.strftime("%Y-%m-%d %H:%M UTC")
                
                click.echo(f"{status_text} {notification.notification_type}")
                click.echo(f"   To: {notification.email_address}")
                click.echo(f"   Scheduled: {scheduled_time}")
                click.echo(f"   Subject: {notification.subject}")
                click.echo()
                
        except Exception as e:
            click.echo(f"[SNAFU] Error listing pending notifications: {str(e)}")

    @app.cli.command("test-smtp")
    def test_smtp_connection():
        """Test SMTP connection"""
        click.echo("[OLKORECT] Testing SMTP connection...")
        
        try:
            if EmailNotificationService.test_smtp_connection():
                click.echo("[OLKORECT] SMTP connection successful!")
            else:
                click.echo("[SNAFU] SMTP connection failed!")
        except Exception as e:
            click.echo(f"[SNAFU] SMTP connection test error: {str(e)}")

    @app.cli.command("send-completion-notification")
    @click.argument('session_id')
    def send_completion_notification(session_id):
        """Manually trigger completion notification for a session"""
        click.echo(f"[OLKORECT] Sending completion notification for session {session_id}...")
        
        try:
            success = EmailNotificationService.create_session_completion_notifications(session_id)
            
            if success:
                click.echo("[OLKORECT] Completion notification created and sent!")
            else:
                click.echo("[SNAFU] Failed to create/send completion notification")
        except Exception as e:
            click.echo(f"[SNAFU] Error sending completion notification: {str(e)}")

   
    @app.cli.command("test-session2-email")
    @click.option('--email', default='wicaksonolxn@gmail.com', help='Test email recipient')
    def test_session2_email(email):
        """Test Session 2 continuation email template and send to test email"""
        click.echo(f"[OLKORECT] Testing Session 2 email to {email}...")
        
        try:
            from flask import current_app
            from app.services.SMTP.smtpService import SMTPService
            import os
            
            # Template data - ONLY session_2_url, no cancel/reschedule
            template_data = {
                'username': 'Airlangga',
                'session_1_completion_date': '15 Januari 2025',
                'days_since_session_1': '14',
                'session_2_url': current_app.config['BASE_URL'],  # NO FALLBACK
                'support_email': current_app.config['EMAIL_FROM_ADDRESS'],  # NO FALLBACK
                'brand_name': 'Assessment Kesehatan Mental',
                'current_year': '2025'
            }
            
            template_path = os.path.join(
                os.path.dirname(__file__), 
                'services', 'SMTP', 'session2_template.html'
            )
            
            success = SMTPService.send_template_email(
                to_email=email,
                subject='🌟 Waktunya Melanjutkan Perjalanan Anda - Sesi 2 Menanti!',
                template_path=template_path,
                template_data=template_data
            )
            
            if success:
                click.echo(f"[OLKORECT] Session 2 test email sent successfully to {email}!")
            else:
                click.echo(f"[SNAFU] Failed to send Session 2 test email!")
                
        except Exception as e:
            click.echo(f"[SNAFU] Error sending Session 2 test email: {str(e)}")
    @app.cli.command("process-session2-notifications")
    def process_session2_notifications():
        """Automatically process Session 2 notifications (for cron job)"""
        click.echo("[OLKORECT] Processing Session 2 notifications...")
        
        try:
            from app.services.SMTP.session2NotificationService import Session2NotificationService
            
            # Step 1: Create automatic notifications for eligible users (14+ days)
            click.echo("  - Creating automatic notifications for eligible users...")
            created_count = Session2NotificationService.create_automatic_notifications()
            click.echo(f"  ✓ Created {created_count} new notifications")
            
            # Step 2: Send pending notifications that are due
            click.echo("  - Sending pending notifications...")
            sent_count = Session2NotificationService.send_pending_notifications()
            click.echo(f"  ✓ Sent {sent_count} notifications")
            
            # Step 3: Get stats for summary
            pending_count = Session2NotificationService.get_pending_notifications_count()
            all_users = Session2NotificationService.get_all_users_with_eligibility()
            eligible_users = [user for user in all_users if user['is_eligible']]
            total_eligible = len(eligible_users)
            
            click.echo(f"[OLKORECT] Session 2 notification processing completed!")
            click.echo(f"  - Created: {created_count} notifications")
            click.echo(f"  - Sent: {sent_count} emails")
            click.echo(f"  - Pending: {pending_count} notifications")
            click.echo(f"  - Eligible users: {total_eligible} total")
                
        except Exception as e:
            click.echo(f"[SNAFU] Error processing Session 2 notifications: {str(e)}")

    @app.cli.command("session2-stats")
    def get_session2_stats():
        """Get Session 2 notification statistics"""
        click.echo("[OLKORECT] Session 2 Notification Statistics:")
        
        try:
            from app.services.SMTP.session2NotificationService import Session2NotificationService
            
            all_users = Session2NotificationService.get_all_users_with_eligibility()
            eligible_users = [user for user in all_users if user['is_eligible']]
            pending_count = Session2NotificationService.get_pending_notifications_count()
            
            # Calculate stats
            total_eligible = len(eligible_users)
            ready_to_send = len([u for u in eligible_users if u["days_since_session_1"] >= 14])
            pending_reminders = len([u for u in eligible_users if u["days_since_session_1"] > 14])
            
            click.echo("-" * 50)
            click.echo(f"Total eligible users (Session 1 completed, no Session 2): {total_eligible}")
            click.echo(f"Ready to send (14+ days): {ready_to_send}")
            click.echo(f"Pending scheduled notifications: {pending_count}")
            click.echo(f"Overdue reminders (14+ days): {pending_reminders}")
            click.echo("-" * 50)
            if eligible_users:
                click.echo("Recent eligible users:")
                for user in eligible_users[:5]:  # Show first 5
                    click.echo(
                        f"  - {user['username']} ({user['email']}) "
                        f"- {user['days_since_session_1']} days ago"
                    )
                if len(eligible_users) > 5:
                    click.echo(f"  ... and {len(eligible_users) - 5} more users")

        except Exception as e:
            click.echo(f"[SNAFU] Error getting Session 2 stats: {str(e)}")

    # OTP/EMAIL TESTING PIPELINE COMMANDS
    @app.cli.command("test-otp-pipeline")
    @click.option('--email', default='wicaksonolxn@gmail.com', help='Test email address')
    @click.option('--username', default=None, help='Test username (auto-generated if not provided)')
    def test_otp_pipeline(email, username):
        """Test complete OTP pipeline: create user -> send OTP -> verify -> cleanup"""
        import random
        from datetime import datetime, timedelta
        from ..services.shared.usManService import UserManagerService
        from ..services.shared.emailOTPService import EmailOTPService
        
        if not username:
            username = f"test_otp_{random.randint(1000, 9999)}"
        
        click.echo(f"[OLKORECT] Starting OTP pipeline test for {username} ({email})...")
        
        try:
            # Step 1: Create test user
            click.echo("  Step 1: Creating test user...")
            user = UserManagerService.create_user(
                uname=username,
                password="testpass123",
                user_type_name='user',
                email=email,
                age=25,
                gender="other"
            )
            
            # Schedule deletion for testing
            with get_session() as db:
                user = db.merge(user)
                user.deletion_scheduled_at = datetime.utcnow() + timedelta(hours=12)
                db.commit()
            
            click.echo(f"  ✓ Test user created: {username} (ID: {user.id})")
            
            # Step 2: Send OTP email
            click.echo("  Step 2: Sending OTP email...")
            otp_result = EmailOTPService.send_otp_email(user.id)
            
            if otp_result["status"] == "success":
                click.echo(f"  ✓ OTP email sent to {email}")
                
                # Get the actual OTP from database for testing
                with get_session() as db:
                    fresh_user = db.query(User).filter_by(id=user.id).first()
                    actual_otp = fresh_user.email_otp_code
                    otp_expiry = fresh_user.email_otp_expires_at
                
                click.echo(f"  📧 OTP Code: {actual_otp}")
                click.echo(f"  ⏰ Expires: {otp_expiry}")
                
                # Step 3: Test OTP verification
                click.echo("  Step 3: Testing OTP verification...")
                verify_result = EmailOTPService.verify_otp(user.id, actual_otp)
                
                if verify_result["status"] == "success":
                    click.echo(f"  ✓ OTP verified successfully!")
                    click.echo(f"  ✓ User email verified: {verify_result.get('username')}")
                    
                    # Check deletion was cancelled
                    with get_session() as db:
                        verified_user = db.query(User).filter_by(id=user.id).first()
                        if not verified_user.deletion_scheduled_at:
                            click.echo("  ✓ Deletion schedule cancelled after verification")
                        else:
                            click.echo("  ❗ Warning: Deletion still scheduled")
                    
                else:
                    click.echo(f"  ❌ OTP verification failed: {verify_result['message']}")
                    
            else:
                click.echo(f"  ❌ Failed to send OTP: {otp_result['message']}")
                
            click.echo(f"[OLKORECT] OTP pipeline test completed!")
            click.echo(f"Test user '{username}' can be cleaned up manually if needed")
                
        except Exception as e:
            click.echo(f"[SNAFU] OTP pipeline test failed: {str(e)}")

    @app.cli.command("test-scheduler-cleanup")
    def test_scheduler_cleanup():
        """Test scheduler OTP cleanup functionality"""
        click.echo("[OLKORECT] Testing scheduler OTP cleanup...")
        
        try:
            from app.services.schedulerService import SchedulerService
            
            scheduler_service = SchedulerService()
            result = scheduler_service._execute_otp_cleanup(current_app._get_current_object())
            
            click.echo(f"[OLKORECT] Cleanup executed:")
            click.echo(f"  - Users deleted: {result.get('deleted_users', 0)}")
            click.echo(f"  - OTPs cleaned: {result.get('cleaned_otps', 0)}")
            
        except Exception as e:
            click.echo(f"[SNAFU] Scheduler cleanup test failed: {str(e)}")

    @app.cli.command("test-scheduler-sesman")  
    def test_scheduler_sesman():
        """Test scheduler SESMAN notifications functionality"""
        click.echo("[OLKORECT] Testing scheduler SESMAN notifications...")
        
        try:
            from app.services.schedulerService import SchedulerService
            
            scheduler_service = SchedulerService()
            result = scheduler_service._execute_sesman_notifications(current_app._get_current_object())
            
            click.echo(f"[OLKORECT] SESMAN notifications executed:")
            click.echo(f"  - Notifications sent: {result.get('notifications_sent', 0)}")
            click.echo(f"  - Sessions processed: {result.get('sessions_processed', 0)}")
            
        except Exception as e:
            click.echo(f"[SNAFU] Scheduler SESMAN test failed: {str(e)}")

    @app.cli.command("create-expired-test-user")
    @click.option('--hours-ago', default=1, help='Hours ago to set deletion time')
    @click.option('--seconds-ago', default=None, help='Seconds ago to set deletion time (overrides hours)')
    @click.option('--email', default=None, help='Specific email address to use')
    def create_expired_test_user(hours_ago, seconds_ago, email):
        """Create test user with past deletion time for cleanup testing"""
        import random
        from datetime import datetime, timedelta
        
        username = f"expired_test_{random.randint(1000, 9999)}"
        
        if not email:
            email = f"expired_{random.randint(1000, 9999)}@example.com"
        
        # Use seconds if provided, otherwise hours
        if seconds_ago is not None:
            time_delta = timedelta(seconds=int(seconds_ago))
            time_desc = f"{seconds_ago} seconds ago"
        else:
            time_delta = timedelta(hours=int(hours_ago))
            time_desc = f"{hours_ago} hours ago"
        
        click.echo(f"[OLKORECT] Creating expired test user: {username}")
        
        try:
            from app.services.shared.usManService import UserManagerService
            
            user = UserManagerService.create_user(
                uname=username,
                password="expired123",
                user_type_name='user',
                email=email
            )
            
            # Set deletion time in the past
            with get_session() as db:
                user = db.merge(user)
                user.deletion_scheduled_at = datetime.utcnow() - time_delta
                user.email_otp_code = "999999"  # Fake expired OTP
                user.email_otp_expires_at = datetime.utcnow() - time_delta
                user.email_verified = False
                db.commit()
            
            click.echo(f"  ✓ Expired test user created:")
            click.echo(f"  - Username: {username}")
            click.echo(f"  - Email: {email}")
            click.echo(f"  - Deletion scheduled: {time_desc}")
            click.echo(f"  - Should be cleaned up by: flask test-scheduler-cleanup")
            
        except Exception as e:
            click.echo(f"[SNAFU] Failed to create expired test user: {str(e)}")

    @app.cli.command("quick-test-cleanup")
    @click.option('--email', default='wicaksonolxn@gmail.com', help='Email for test user')
    def quick_test_cleanup(email):
        """Quick test: create expired user (1 sec ago) -> cleanup -> verify deletion"""
        import random
        from datetime import datetime, timedelta
        
        click.echo(f"[OLKORECT] Quick cleanup test with {email}...")
        
        try:
            # Step 1: Create expired user
            click.echo("  Step 1: Creating expired user (1 second ago)...")
            from app.services.shared.usManService import UserManagerService
            
            username = f"quick_test_{random.randint(1000, 9999)}"
            
            user = UserManagerService.create_user(
                uname=username,
                password="quick123",
                user_type_name='user',
                email=email
            )
            
            # Set deletion 1 second ago
            with get_session() as db:
                user = db.merge(user)
                user.deletion_scheduled_at = datetime.utcnow() - timedelta(seconds=1)
                user.email_otp_code = "111111"
                user.email_otp_expires_at = datetime.utcnow() - timedelta(seconds=1)
                user.email_verified = False
                db.commit()
                user_id = user.id
            
            click.echo(f"  ✓ Created user: {username} (ID: {user_id}) - scheduled for deletion 1 sec ago")
            
            # Step 2: Run cleanup
            click.echo("  Step 2: Running scheduler cleanup...")
            from app.services.schedulerService import SchedulerService
            
            scheduler_service = SchedulerService()
            result = scheduler_service._execute_otp_cleanup(current_app._get_current_object())
            
            click.echo(f"  ✓ Cleanup result: {result.get('deleted_users', 0)} deleted, {result.get('cleaned_otps', 0)} cleaned")
            
            # Step 3: Verify user was deleted
            click.echo("  Step 3: Verifying user deletion...")
            with get_session() as db:
                deleted_user = db.query(User).filter_by(id=user_id).first()
                if deleted_user:
                    click.echo(f"  ❌ User still exists! Something went wrong.")
                else:
                    click.echo(f"  ✓ User successfully deleted from database")
            
            click.echo("[OLKORECT] Quick cleanup test completed!")
            
        except Exception as e:
            click.echo(f"[SNAFU] Quick cleanup test failed: {str(e)}")

    @app.cli.command("test-otp-no-email")
    @click.option('--username', default=None, help='Test username (auto-generated if not provided)')
    def test_otp_no_email(username):
        """Test OTP generation without sending email - just get OTP from database"""
        import random
        from datetime import datetime, timedelta
        
        if not username:
            username = f"test_noemail_{random.randint(1000, 9999)}"
            
        click.echo(f"[OLKORECT] Testing OTP generation (no email) for {username}...")
        
        try:
            # Step 1: Create user without sending OTP email
            click.echo("  Step 1: Creating test user...")
            from app.services.shared.usManService import UserManagerService
            from app.services.shared.emailOTPService import EmailOTPService
            
            user = UserManagerService.create_user(
                uname=username,
                password="testpass123",
                user_type_name='user',
                email="fake@example.com",  # Won't actually send to this
                age=25,
                gender="other"
            )
            
            click.echo(f"  ✓ User created: {username} (ID: {user.id})")
            
            # Step 2: Generate OTP but capture the code before it tries to send
            click.echo("  Step 2: Generating OTP code...")
            
            # Manually generate and save OTP without sending email
            otp_code = EmailOTPService.generate_otp_code()
            with get_session() as db:
                user = db.merge(user)
                user.email_otp_code = otp_code
                user.email_otp_expires_at = datetime.utcnow() + timedelta(hours=12)
                user.deletion_scheduled_at = datetime.utcnow() + timedelta(hours=12)
                db.commit()
            
            click.echo(f"  📧 Generated OTP Code: {otp_code}")
            click.echo(f"  ⏰ Expires: {user.email_otp_expires_at}")
            
            # Step 3: Test verification with the generated OTP
            click.echo("  Step 3: Testing OTP verification...")
            verify_result = EmailOTPService.verify_otp(user.id, otp_code)
            
            if verify_result["status"] == "success":
                click.echo(f"  ✓ OTP verified successfully!")
                click.echo(f"  ✓ Username: {verify_result.get('username')}")
                
                # Check deletion was cancelled
                with get_session() as db:
                    verified_user = db.query(User).filter_by(id=user.id).first()
                    if not verified_user.deletion_scheduled_at:
                        click.echo("  ✓ Deletion schedule cancelled after verification")
                    else:
                        click.echo("  ❗ Warning: Deletion still scheduled")
            else:
                click.echo(f"  ❌ OTP verification failed: {verify_result['message']}")
            
            click.echo("[OLKORECT] OTP no-email test completed!")
            click.echo(f"Test user '{username}' created and verified")
            
        except Exception as e:
            click.echo(f"[SNAFU] OTP no-email test failed: {str(e)}")

    @app.cli.command("test-smtp-direct")
    @click.option('--email', default='wicaksonolxn@gmail.com', help='Test email recipient')
    def test_smtp_direct(email):
        """Test SMTP service directly with simple email"""
        click.echo(f"[OLKORECT] Testing direct SMTP to {email}...")
        
        try:
            from app.services.SMTP.smtpService import SMTPService
            import os
            
            # Test simple email
            template_path = os.path.join(
                os.path.dirname(__file__), 
                'services', 'SMTP', 'otp_template.html'
            )
            
            template_data = {
                'user_name': 'Test User',
                'otp_code': '123456',
                'expiry_hours': '12'
            }
            
            success = SMTPService.send_template_email(
                to_email=email,
                subject="TEST - SMTP Direct Test Email",
                template_path=template_path,
                template_data=template_data
            )
            
            if success:
                click.echo(f"[OLKORECT] Direct SMTP test successful! Check {email}")
            else:
                click.echo("[SNAFU] Direct SMTP test failed")
                
        except Exception as e:
            click.echo(f"[SNAFU] SMTP direct test error: {str(e)}")

    @app.cli.command("test-full-pipeline")
    @click.option('--email', default='wicaksonolxn@gmail.com', help='Test email address')
    def test_full_pipeline(email):
        """Complete end-to-end test: user -> OTP -> cleanup -> scheduler"""
        click.echo(f"[OLKORECT] Starting FULL pipeline test with {email}...")
        
        try:
            # Test 1: OTP Pipeline
            click.echo("\n=== TEST 1: OTP PIPELINE ===")
            from flask.cli import with_appcontext
            ctx = app.app_context()
            ctx.push()
            try:
                test_otp_pipeline.callback(email=email, username=None)
            finally:
                ctx.pop()
            
            # Test 2: Create expired user
            click.echo("\n=== TEST 2: EXPIRED USER ===")
            ctx = app.app_context()
            ctx.push()
            try:
                create_expired_test_user.callback(hours_ago=2)
            finally:
                ctx.pop()
            
            # Test 3: Cleanup
            click.echo("\n=== TEST 3: SCHEDULER CLEANUP ===")
            ctx = app.app_context()
            ctx.push()
            try:
                test_scheduler_cleanup.callback()
            finally:
                ctx.pop()
            
            # Test 4: SMTP Direct
            click.echo("\n=== TEST 4: DIRECT SMTP ===")
            ctx = app.app_context()
            ctx.push()
            try:
                test_smtp_direct.callback(email=email)
            finally:
                ctx.pop()
            
            click.echo("\n[OLKORECT] FULL PIPELINE TEST COMPLETED!")
            click.echo("Check your email and console output above for results")
            
        except Exception as e:
            click.echo(f"[SNAFU] Full pipeline test failed: {str(e)}")

    @app.cli.command("test-pagination")
    @click.option('--count', default=100, help='Number of dummy users to create')
    def create_test_pagination_users(count):
        """Create verified dummy users for testing pagination"""
        import random
        from datetime import datetime
        
        click.echo(f"[OLKORECT] Creating {count} verified dummy users for pagination testing...")
        
        try:
            from app.services.shared.usManService import UserManagerService
            
            # Sample data for realistic test users
            first_names = [
                "Ahmad", "Budi", "Citra", "Dewi", "Eko", "Fitri", "Gilang", "Hana", "Indra", "Jasmin",
                "Kurnia", "Lestari", "Maya", "Nina", "Oscar", "Putri", "Qori", "Rika", "Sari", "Tari",
                "Ulfa", "Vina", "Wawan", "Xenia", "Yanto", "Zara", "Agus", "Bella", "Chandra", "Dian"
            ]
            
            last_names = [
                "Pratama", "Sari", "Wijaya", "Putri", "Santoso", "Rahayu", "Kusuma", "Dewi", "Putra", "Lestari",
                "Handoko", "Maharani", "Setiawan", "Anggraini", "Hidayat", "Permatasari", "Nugroho", "Wulandari",
                "Saputra", "Fitria", "Rahman", "Safitri", "Gunawan", "Nuraini", "Utomo", "Kartika", "Susanto", "Indira"
            ]
            genders = ["male", "female", "other"]
            education_levels = [
                "SD", "SMP", "SMA", "D3", "S1", "S2", "S3", "Tidak Sekolah"
            ]
            created_count = 0
            skipped_count = 0
            
            with get_session() as db:
                user_type = db.query(UserType).filter_by(name="user").first()
                if not user_type:
                    click.echo("[SNAFU] User type 'user' not found. Run 'seed-db' first.")
                    return
                
                for i in range(count):
                    # Generate realistic username and email
                    first_name = random.choice(first_names)
                    last_name = random.choice(last_names)
                    username = f"{first_name.lower()}_{last_name.lower()}_{random.randint(100, 999)}"
                    email = f"{username}@test.example.com"
                    
                    # Check if user already exists
                    existing = db.query(User).filter_by(uname=username).first()
                    if existing:
                        skipped_count += 1
                        continue
                    
                    try:
                        # Create user with realistic profile data
                        user = UserManagerService.create_user(
                            uname=username,
                            password="testuser123",  # Standard test password
                            user_type_name='user',
                            email=email,
                            phone=f"08{random.randint(10000000, 99999999)}",  # Indonesian phone format
                            age=random.randint(18, 65),
                            gender=random.choice(genders),
                            educational_level=random.choice(education_levels),
                            cultural_background="Indonesia",
                            medical_conditions="None" if random.random() > 0.3 else "Mild anxiety",
                            medications="None" if random.random() > 0.2 else "Multivitamin",
                            emergency_contact=f"Emergency contact for {first_name} {last_name}"
                        )
                        # Mark email as verified for testing purposes
                        with get_session() as update_db:
                            user = update_db.merge(user)
                            user.email_verified = True
                            update_db.commit()
                        created_count += 1
                        if created_count % 10 == 0:
                            click.echo(f"  ✓ Created {created_count} users...")
                    except Exception as e:
                        click.echo(f"  ❌ Failed to create user {username}: {str(e)}")
                        skipped_count += 1
                        continue
            
            click.echo(f"[OLKORECT] Pagination test users created successfully!")
            click.echo(f"  - Created: {created_count} new users")
            click.echo(f"  - Skipped: {skipped_count} (already existed or errors)")
            click.echo(f"  - Total users now available for pagination testing")
            click.echo(f"  - All users have verified emails and realistic profiles")
            click.echo(f"  - Standard password: testuser123")
            
        except Exception as e:
            click.echo(f"[SNAFU] Failed to create pagination test users: {str(e)}")

    @app.cli.command("delete-user")
    @click.argument('username')
    @click.option('--dry-run', is_flag=True, help='Show what would be deleted without actually deleting')
    @click.confirmation_option(prompt='Are you sure you want to delete this user and ALL related data?')
    def delete_user(username, dry_run):
        """
        Delete a user by username with complete cascade deletion.
        
        This will delete:
        - User record
        - All assessment sessions for this user
        - All PHQ responses, LLM conversations, analysis results
        - All camera captures and email notifications
        - All auto login tokens
        - All session exports requested by this user
        
        USERNAME: The uname field of the user to delete
        """
        
        with get_session() as db:
            try:
                # Find the user
                user = db.query(User).filter(User.uname == username).first()
                
                if not user:
                    click.echo(f"❌ User '{username}' not found.", err=True)
                    return
                
                click.echo(f"🔍 Found user: {user.uname} (ID: {user.id})")
                
                # Count related records for confirmation
                auto_login_tokens = db.query(AutoLoginToken).filter(AutoLoginToken.user_id == user.id).count()
                assessment_sessions = db.query(AssessmentSession).filter(AssessmentSession.user_id == user.id).count()
                session_exports = db.query(SessionExport).filter(SessionExport.requested_by_user == user.id).count()
                direct_email_notifications = db.query(EmailNotification).filter(EmailNotification.user_id == user.id).count()
                
                # Count cascading records from assessment sessions
                session_ids = db.query(AssessmentSession.id).filter(AssessmentSession.user_id == user.id).subquery()
                phq_responses = db.query(PHQResponse).filter(PHQResponse.session_id.in_(session_ids)).count()
                llm_conversations = db.query(LLMConversation).filter(LLMConversation.session_id.in_(session_ids)).count()
                llm_analysis = db.query(LLMAnalysisResult).filter(LLMAnalysisResult.session_id.in_(session_ids)).count()
                camera_captures = db.query(CameraCapture).filter(CameraCapture.session_id.in_(session_ids)).count()
                session_email_notifications = db.query(EmailNotification).filter(EmailNotification.session_id.in_(session_ids)).count()
                
                # Count camera files
                camera_files_count = 0
                if camera_captures > 0:
                    camera_capture_records = db.query(CameraCapture).filter(CameraCapture.session_id.in_(session_ids)).all()
                    for capture in camera_capture_records:
                        if capture.filenames:
                            camera_files_count += len(capture.filenames)
                
                # Display what will be deleted
                click.echo("\n📊 Records to be deleted:")
                click.echo(f"   👤 User: 1")
                click.echo(f"   🔑 Auto Login Tokens: {auto_login_tokens}")
                click.echo(f"   📋 Assessment Sessions: {assessment_sessions}")
                click.echo(f"   📝 PHQ Responses: {phq_responses}")
                click.echo(f"   💬 LLM Conversations: {llm_conversations}")
                click.echo(f"   🔬 LLM Analysis Results: {llm_analysis}")
                click.echo(f"   📸 Camera Captures: {camera_captures}")
                click.echo(f"   🗂️  Camera Files: {camera_files_count}")
                click.echo(f"   📧 Email Notifications (direct): {direct_email_notifications}")
                click.echo(f"   📧 Email Notifications (session): {session_email_notifications}")
                click.echo(f"   📤 Session Exports: {session_exports}")
                
                total_records = (1 + auto_login_tokens + assessment_sessions + phq_responses + 
                               llm_conversations + llm_analysis + camera_captures + 
                               direct_email_notifications + session_email_notifications + session_exports)
                click.echo(f"\n🗑️  Total records to delete: {total_records}")
                click.echo(f"🗂️  Total files to delete: {camera_files_count}")
                
                if dry_run:
                    click.echo("\n🧪 DRY RUN - No data was actually deleted")
                    return
                
                # Perform cascade deletion
                click.echo("\n🗑️  Starting cascade deletion...")
                
                # Delete auto login tokens
                if auto_login_tokens > 0:
                    deleted = db.query(AutoLoginToken).filter(AutoLoginToken.user_id == user.id).delete()
                    click.echo(f"   ✅ Deleted {deleted} auto login tokens")
                
                # Delete session exports
                if session_exports > 0:
                    deleted = db.query(SessionExport).filter(SessionExport.requested_by_user == user.id).delete()
                    click.echo(f"   ✅ Deleted {deleted} session exports")
                
                # Delete direct email notifications
                if direct_email_notifications > 0:
                    deleted = db.query(EmailNotification).filter(EmailNotification.user_id == user.id).delete()
                    click.echo(f"   ✅ Deleted {deleted} direct email notifications")
                
                # Delete camera capture files before deleting session records
                camera_files_deleted = 0
                if camera_captures > 0:
                    import os
                    # Get all camera captures for this user
                    user_session_ids = [s.id for s in db.query(AssessmentSession).filter(AssessmentSession.user_id == user.id).all()]
                    camera_capture_records = db.query(CameraCapture).filter(CameraCapture.session_id.in_(user_session_ids)).all()
                    
                    # Delete physical files
                    for capture in camera_capture_records:
                        if capture.filenames:
                            for filename in capture.filenames:
                                try:
                                    # Use current_app.media_save path
                                    file_path = os.path.join(current_app.config.get('UPLOAD_FOLDER', current_app.root_path + '/static/uploads'), filename)
                                    # Also try media_save attribute
                                    if hasattr(current_app, 'media_save'):
                                        file_path = os.path.join(current_app.media_save, filename)
                                    
                                    if os.path.exists(file_path):
                                        os.remove(file_path)
                                        camera_files_deleted += 1
                                except Exception as file_error:
                                    click.echo(f"   ⚠️  Could not delete file {filename}: {str(file_error)}")
                    
                    if camera_files_deleted > 0:
                        click.echo(f"   ✅ Deleted {camera_files_deleted} camera capture files")

                # Delete assessment sessions (this will cascade to related records via SQLAlchemy)
                if assessment_sessions > 0:
                    # Get the sessions to delete
                    sessions_to_delete = db.query(AssessmentSession).filter(AssessmentSession.user_id == user.id).all()
                    
                    for session in sessions_to_delete:
                        db.delete(session)  # This will cascade via SQLAlchemy relationships
                    
                    click.echo(f"   ✅ Deleted {len(sessions_to_delete)} assessment sessions with cascaded data")
                
                # Finally delete the user
                db.delete(user)
                
                # Commit all changes
                db.commit()
                
                click.echo(f"\n✅ Successfully deleted user '{username}' and all related data!")
                
            except Exception as e:
                db.rollback()
                click.echo(f"\n❌ Error during deletion: {str(e)}", err=True)
                raise

    @app.cli.command("cleanup-unlinked-images")
    @click.option('--dry-run', is_flag=True, help='Show what would be deleted without actually deleting')
    @click.option('--older-than-hours', default=24, help='Only delete unlinked images older than X hours (default: 24)')
    def cleanup_unlinked_images(dry_run, older_than_hours):
        """
        Delete unlinked camera images and their database records.
        
        Unlinked images are camera captures where assessment_id is NULL,
        meaning they were uploaded but never associated with a completed assessment.
        """
        from datetime import datetime, timedelta
        import os
        
        click.echo(f"[OLKORECT] Cleaning up unlinked camera images (older than {older_than_hours} hours)...")
        
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=older_than_hours)
            
            with get_session() as db:
                # Find unlinked camera captures older than the cutoff time
                unlinked_captures = db.query(CameraCapture).filter(
                    CameraCapture.assessment_id.is_(None),
                    CameraCapture.created_at < cutoff_time
                ).all()
                
                if not unlinked_captures:
                    click.echo("✅ No unlinked camera images found to clean up")
                    return
                
                total_files = 0
                total_captures = len(unlinked_captures)
                
                # Count total files
                for capture in unlinked_captures:
                    if capture.filenames and isinstance(capture.filenames, list):
                        total_files += len(capture.filenames)
                
                click.echo(f"🔍 Found {total_captures} unlinked camera captures")
                click.echo(f"🗂️  Total files to delete: {total_files}")
                
                # Show detailed breakdown
                if total_captures > 0:
                    click.echo("\n📊 Breakdown by session:")
                    session_summary = {}
                    for capture in unlinked_captures:
                        session_id = capture.session_id
                        file_count = len(capture.filenames) if capture.filenames else 0
                        created = capture.created_at.strftime('%Y-%m-%d %H:%M')
                        
                        if session_id not in session_summary:
                            session_summary[session_id] = {'files': 0, 'captures': 0, 'created': created}
                        session_summary[session_id]['files'] += file_count
                        session_summary[session_id]['captures'] += 1
                    
                    for session_id, info in session_summary.items():
                        click.echo(f"   📋 Session {session_id[:8]}: {info['captures']} captures, {info['files']} files ({info['created']})")
                
                if dry_run:
                    click.echo("\n🧪 DRY RUN - No files or database records were actually deleted")
                    return
                
                # Perform cleanup
                click.echo("\n🗑️  Starting cleanup...")
                
                files_deleted = 0
                files_not_found = 0
                captures_deleted = 0
                
                # Get media path
                media_path = current_app.media_save if hasattr(current_app, 'media_save') else os.path.join(current_app.root_path, 'static', 'uploads')
                
                for capture in unlinked_captures:
                    if capture.filenames and isinstance(capture.filenames, list):
                        # Delete physical files
                        for filename in capture.filenames:
                            if not filename:  # Skip empty filenames
                                continue
                            
                            file_path = os.path.join(media_path, filename)
                            try:
                                if os.path.exists(file_path):
                                    os.remove(file_path)
                                    files_deleted += 1
                                else:
                                    files_not_found += 1
                            except Exception as e:
                                click.echo(f"   ⚠️  Could not delete file {filename}: {str(e)}")
                    
                    # Delete database record
                    db.delete(capture)
                    captures_deleted += 1
                
                # Commit all changes
                db.commit()
                
                # Summary
                click.echo(f"\n✅ Cleanup completed:")
                click.echo(f"   🗂️  Files deleted: {files_deleted}")
                click.echo(f"   📂 Files not found: {files_not_found}")
                click.echo(f"   🗃️  Database records deleted: {captures_deleted}")
                
                if files_not_found > 0:
                    click.echo(f"\n📝 Note: {files_not_found} files were already missing from filesystem")
                
        except Exception as e:
            click.echo(f"\n❌ Error during cleanup: {str(e)}", err=True)
            raise

    @app.cli.command("check-user-data")
    @click.argument('username')
    def check_user_data(username):
        """
        Check what data exists for a user without deleting anything.
        
        USERNAME: The uname field of the user to check
        """
        
        with get_session() as db:
            try:
                # Find the user
                user = db.query(User).filter(User.uname == username).first()
                
                if not user:
                    click.echo(f"❌ User '{username}' not found.", err=True)
                    return
                
                click.echo(f"🔍 User: {user.uname} (ID: {user.id})")
                click.echo(f"   Email: {user.email}")
                click.echo(f"   Phone: {user.phone}")
                click.echo(f"   Created: {user.created_at}")
                click.echo(f"   User Type ID: {user.user_type_id}")
                
                # Count related records
                auto_login_tokens = db.query(AutoLoginToken).filter(AutoLoginToken.user_id == user.id).count()
                assessment_sessions = db.query(AssessmentSession).filter(AssessmentSession.user_id == user.id).count()
                session_exports = db.query(SessionExport).filter(SessionExport.requested_by_user == user.id).count()
                direct_email_notifications = db.query(EmailNotification).filter(EmailNotification.user_id == user.id).count()
                
                # Count cascading records from assessment sessions
                if assessment_sessions > 0:
                    session_ids = db.query(AssessmentSession.id).filter(AssessmentSession.user_id == user.id).subquery()
                    phq_responses = db.query(PHQResponse).filter(PHQResponse.session_id.in_(session_ids)).count()
                    llm_conversations = db.query(LLMConversation).filter(LLMConversation.session_id.in_(session_ids)).count()
                    llm_analysis = db.query(LLMAnalysisResult).filter(LLMAnalysisResult.session_id.in_(session_ids)).count()
                    camera_captures = db.query(CameraCapture).filter(CameraCapture.session_id.in_(session_ids)).count()
                    session_email_notifications = db.query(EmailNotification).filter(EmailNotification.session_id.in_(session_ids)).count()
                else:
                    phq_responses = llm_conversations = llm_analysis = camera_captures = session_email_notifications = 0
                
                # Display data summary
                click.echo(f"\n📊 Related data:")
                click.echo(f"   🔑 Auto Login Tokens: {auto_login_tokens}")
                click.echo(f"   📋 Assessment Sessions: {assessment_sessions}")
                click.echo(f"   📝 PHQ Responses: {phq_responses}")
                click.echo(f"   💬 LLM Conversations: {llm_conversations}")
                click.echo(f"   🔬 LLM Analysis Results: {llm_analysis}")
                click.echo(f"   📸 Camera Captures: {camera_captures}")
                click.echo(f"   📧 Email Notifications (direct): {direct_email_notifications}")
                click.echo(f"   📧 Email Notifications (session): {session_email_notifications}")
                click.echo(f"   📤 Session Exports: {session_exports}")
                
                total_records = (1 + auto_login_tokens + assessment_sessions + phq_responses + 
                               llm_conversations + llm_analysis + camera_captures + 
                               direct_email_notifications + session_email_notifications + session_exports)
                click.echo(f"\n📊 Total records: {total_records}")
                
                if assessment_sessions > 0:
                    click.echo(f"\n📋 Assessment sessions:")
                    sessions = db.query(AssessmentSession).filter(AssessmentSession.user_id == user.id).all()
                    for session in sessions:
                        click.echo(f"   - {session.id[:8]}: {session.status} ({session.created_at.strftime('%Y-%m-%d %H:%M')})")
                        
            except Exception as e:
                click.echo(f"\n❌ Error checking user data: {str(e)}", err=True)
                raise

