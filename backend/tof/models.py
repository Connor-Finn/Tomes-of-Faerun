from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .extensions import db

EXPERIENCE_LEVELS = {
    "new": "New adventurer",
    "some": "Played a few sessions",
    "veteran": "Seasoned veteran",
}
TIMEZONES = [
    "UTC", "America/New_York", "America/Chicago", "America/Denver",
    "America/Los_Angeles", "Europe/London", "Europe/Berlin", "Asia/Tokyo",
    "Australia/Sydney",
]


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None)


class User(db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user")
    experience: Mapped[str] = mapped_column(String(20), default="new")
    is_verified: Mapped[bool] = mapped_column(default=False)
    is_banned: Mapped[bool] = mapped_column(default=False)
    bio: Mapped[str] = mapped_column(String(200), default="")
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    avatar: Mapped[str | None] = mapped_column(String(100))
    newsletter: Mapped[bool] = mapped_column(default=False)
    notify_email: Mapped[bool] = mapped_column(default=True)
    notify_party: Mapped[bool] = mapped_column(default=False)
    failed_logins: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[datetime | None]
    last_login: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    tokens: Mapped[list[Token]] = relationship(back_populates="user", cascade="all, delete-orphan")

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def to_dict(self) -> dict:
        """Public view of a user. Never includes the password hash."""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "experience": self.experience,
            "is_verified": self.is_verified,
            "is_banned": self.is_banned,
            "bio": self.bio,
            "timezone": self.timezone,
            "avatar_url": f"/uploads/{self.avatar}" if self.avatar else None,
            "notify_email": self.notify_email,
            "notify_party": self.notify_party,
            "created_at": self.created_at.isoformat() + "Z",
        }


class Token(db.Model):
    """One-time links sent by email (kind = verify | reset)."""
    __tablename__ = "tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime]
    used: Mapped[bool] = mapped_column(default=False)

    user: Mapped[User] = relationship(back_populates="tokens")


class Email(db.Model):
    """Outgoing email. Stored instead of sent, and shown in the dev mailbox."""
    __tablename__ = "emails"

    id: Mapped[int] = mapped_column(primary_key=True)
    to_addr: Mapped[str] = mapped_column(String(254), index=True)
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str]
    link: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "to": self.to_addr,
            "subject": self.subject,
            "body": self.body,
            "link": self.link,
            "created_at": self.created_at.isoformat() + "Z",
        }
