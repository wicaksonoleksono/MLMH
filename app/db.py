from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def make_engine(url: str):
    return create_engine(url, future=True, pool_pre_ping=True)


def make_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def make_get_session(SessionLocal):
    @contextmanager
    def get_session():
        s = SessionLocal()
        try:
            yield s
            s.commit()
        except:
            s.rollback()
            raise
        finally:
            s.close()
    return get_session


# Singleton pattern globals
_engine = None
_SessionLocal = None
_get_session = None


def init_database(database_uri: str):
    """Initialize database with singleton pattern."""
    global _engine, _SessionLocal, _get_session

    _engine = make_engine(database_uri)
    _SessionLocal = make_session_factory(_engine)
    _get_session = make_get_session(_SessionLocal)


def get_engine():
    """Get the database engine."""
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _engine


def get_session():
    """Get database session context manager."""
    if _get_session is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _get_session()


def create_all_tables():
    """Create all tables if they don't exist."""
    from .model.base import Base
    from .model.shared.users import User
    from .model.shared.enums import UserType, AssessmentStatus
    from .model.admin.phq import PHQQuestion, PHQScale, PHQSettings
    from .model.admin.camera import CameraSettings
    from .model.admin.llm import LLMSettings
    from .model.admin.consent import ConsentSettings
    from .model.assessment.sessions import AssessmentSession, PHQResponse, LLMConversation, LLMAnalysisResult, CameraCapture, SessionExport
    from .model.assessment.facial_analysis import SessionFacialAnalysis
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
