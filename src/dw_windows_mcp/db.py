"""SQLAlchemy models: users, roles, OAuth tokens/clients, audit log."""
from __future__ import annotations

import datetime as dt
import enum
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


def utcnow() -> dt.datetime:
    """Naive UTC timestamp (SQLite's DateTime column strips tzinfo on
    round-trip, so every comparison in this codebase must stay naive too)."""
    return dt.datetime.now(dt.UTC).replace(tzinfo=None)


class Role(str, enum.Enum):
    ADMIN = "admin"
    STANDARD = "standard"
    READONLY = "readonly"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.READONLY)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Admin-only opt-out: when True, this user's destructive-tool calls skip the
    # confirm-token step. Ignored/forced-False for non-admin roles.
    skip_confirmation: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)

    tokens: Mapped[list[OAuthToken]] = relationship(back_populates="user", cascade="all, delete-orphan")


class OAuthClient(Base):
    __tablename__ = "oauth_clients"

    client_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_secret_hash: Mapped[str] = mapped_column(String(255))
    client_name: Mapped[str] = mapped_column(String(200))
    redirect_uris: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    client_id: Mapped[str] = mapped_column(String(64))
    access_token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    refresh_token: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=True)
    scope: Mapped[str] = mapped_column(String(255), default="")
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="tokens")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)
    username: Mapped[str] = mapped_column(String(100), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(150))
    arguments: Mapped[str] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(String(20))  # success | denied | error | confirm_required
    detail: Mapped[str] = mapped_column(Text, default="")
    client_addr: Mapped[str] = mapped_column(String(100), nullable=True)


engine = create_engine(settings.db_url, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_session() -> Session:
    return SessionLocal()
