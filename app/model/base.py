# app/model/base.py
from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Boolean, DateTime, func


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    # DB-side timestamps, timezone-aware (works great on Postgres; on SQLite it's naive text)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[str]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class IdMixin:
    id: Mapped[int] = mapped_column(primary_key=True)


class BaseModel(Base, IdMixin, TimestampMixin):
    __abstract__ = True


class NamedModel(BaseModel):
    __abstract__ = True
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(String(255))

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.name}>"


class StatusMixin:
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
