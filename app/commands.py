import click
from flask import current_app
from .model.shared.users import User
from .model.shared.enums import UserType
from .model.assessment.sessions import EmailNotification
from .db import get_session, create_all_tables, get_engine
from .services.SMTP.emailNotificationService import EmailNotificationService
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
                        user_type_id=user_type.id,
                        email="wicaksonolxn@gmail.com"
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
                # Compute media save path same way as in __init__.py
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
                db.add(admin_user)
                click.echo(f"[OLKORECT] Admin user '{username}' created successfully!")
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
                db.add(admin_user)
                click.echo(f"[OLKORECT] Admin user '{username}' created successfully!")
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
                    db.add(admin_user)
                    created_users.append((username, password))
                    click.echo(f"[OLKORECT] Admin user '{username}' created successfully!")
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
                'session_2_url': current_app.config['SESSION_2_URL'],  # NO FALLBACK
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

