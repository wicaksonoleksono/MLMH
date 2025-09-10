import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuration factory class for application settings."""
    FLASK_PORT: int = int(os.getenv('FLASK_PORT', '5000'))
    API_PORT: int = int(os.getenv('API_PORT', '5000'))
    DEBUG: bool = os.getenv('DEBUG', 'False').lower() in ('true', '1', 'yes')
    SECRET_KEY: str = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    OPENAI_API_KEY: Optional[str] = os.getenv('OPENAI_API_KEY')
    UPLOAD_FOLDER: str = os.getenv('UPLOAD_FOLDER', 'uploads')
    MAX_CONTENT_LENGTH: int = int(os.getenv('MAX_CONTENT_LENGTH', '52428800'))
    DEFAULT_SESSION_TIMEOUT: int = int(os.getenv('DEFAULT_SESSION_TIMEOUT', '3600'))
    CAMERA_MAX_PHOTOS: int = int(os.getenv('CAMERA_MAX_PHOTOS', '10'))
    OPENAI_MODEL: str = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_ECHO: bool = DEBUG
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    # SMTP Configuration - NO FALLBACKS
    SMTP_USERNAME: str = os.getenv('SMTP_USERNAME')
    SMTP_PASSWORD: str = os.getenv('SMTP_PASSWORD')
    EMAIL_FROM_ADDRESS: str = os.getenv('EMAIL_FROM_ADDRESS')
    EMAIL_FROM_NAME: str = os.getenv('EMAIL_FROM_NAME', 'Mental Health App')
    
    # Base URL for magic links and external URLs - NO FALLBACKS
    BASE_URL: str = os.getenv('BASE_URL')
    
    # Everything routes to BASE_URL - NO specific paths
    LANDING_PAGE_URL: str = BASE_URL if BASE_URL else '/'
    RESCHEDULE_URL: str = BASE_URL if BASE_URL else '/'
    CANCEL_URL: str = BASE_URL if BASE_URL else '/'
    SESSION_2_URL: str = BASE_URL if BASE_URL else '/'
    
    # APScheduler Configuration
    OTP_CLEANUP_INTERVAL_HOURS: int = int(os.getenv('OTP_CLEANUP_INTERVAL_HOURS', '1'))
    SESMAN_ELI_DAYS: int = int(os.getenv('SESMAN_ELI_DAYS', '14'))
    SESMAN_NOTIFICATION_HOUR: int = int(os.getenv('SESMAN_NOTIFICATION_HOUR', '9'))
    SCHEDULER_TIMEZONE: str = os.getenv('SCHEDULER_TIMEZONE', 'Asia/Jakarta')
    SQLALCHEMY_DATABASE_URI = (
        os.getenv('SQLALCHEMY_DATABASE_URI') or
        f"postgresql://{os.getenv('DB_USERNAME') or os.getenv('POSTGRES_USER')}:"
        f"{os.getenv('DB_PASSWORD') or os.getenv('POSTGRES_PASSWORD')}@"
        f"{os.getenv('DB_HOST') or os.getenv('POSTGRES_HOST') or 'localhost'}:"
        f"{os.getenv('DB_PORT') or os.getenv('POSTGRES_PORT') or '5432'}/"
        f"{os.getenv('DB_DATABASE') or os.getenv('POSTGRES_DB')}"
        if all([
            os.getenv('DB_USERNAME') or os.getenv('POSTGRES_USER'),
            os.getenv('DB_PASSWORD') or os.getenv('POSTGRES_PASSWORD'),
            os.getenv('DB_DATABASE') or os.getenv('POSTGRES_DB')
        ]) else "sqlite:///instance/mental_health.db"
    )
