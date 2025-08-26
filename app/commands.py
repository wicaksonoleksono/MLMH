import click
from flask import current_app
from . import db
from .model.shared.users import User
from .model.shared.enums import UserType
from sqlalchemy.exc import IntegrityError


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
        """Seeds the database with minimal essential data."""
        with app.app_context():
            click.echo("[OLKORECT] Seeding database with essential data...")

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

            # Seed default admin and user accounts
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

            try:
                db.session.commit()
                click.echo("[OLKORECT] Database seeding completed successfully!")
                click.echo("  - Admin can configure settings, assessments, and media via web UI")
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
