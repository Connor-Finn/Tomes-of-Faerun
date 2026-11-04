from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, UniqueConstraint
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
    characters: Mapped[list[Character]] = relationship(back_populates="user", cascade="all, delete-orphan")
    monster_collections: Mapped[list[MonsterCollection]] = relationship(cascade="all, delete-orphan")
    environments: Mapped[list[Environment]] = relationship(cascade="all, delete-orphan")
    favourite_spells: Mapped[list[FavouriteSpell]] = relationship(cascade="all, delete-orphan")

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


class Character(db.Model):
    """A player's base character: the build as they made it, untouched by any campaign.

    Only the player's decisions are stored (see characters/engine.py). The sheet is worked out
    from them on every read, so a rules fix updates every character at once.
    """
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    build: Mapped[dict] = mapped_column(db.JSON)
    build_mode: Mapped[str] = mapped_column(String(10), default="standard")
    is_complete: Mapped[bool] = mapped_column(default=False)
    template: Mapped[str | None] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="characters")

    def to_dict(self) -> dict:
        from .characters.engine import name_of
        b = self.build
        return {
            "id": self.id,
            "name": self.name or "Unnamed adventurer",
            "level": b.get("level", 1),
            "race": name_of("races", b.get("race")),
            "subrace": name_of("subraces", b.get("subrace")),
            "class": name_of("classes", b.get("class")),
            "class_index": b.get("class"),
            "subclass": name_of("subclasses", b.get("subclass")),
            "background": name_of("backgrounds", b.get("background")),
            "build_mode": self.build_mode,
            "status": "complete" if self.is_complete else "draft",
            "template": self.template,
            "created_at": self.created_at.isoformat() + "Z",
            "updated_at": self.updated_at.isoformat() + "Z",
        }


class MonsterCollection(db.Model):
    """A Dungeon Master's named group of monsters, such as "Warlock boss dungeon".

    Monsters are stored by their rules `index` (e.g. "goblin"), so the stat block always comes
    from the SRD data and a collection only keeps the DM's own choices: role, count and a note.
    """
    __tablename__ = "monster_collections"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    notes: Mapped[str] = mapped_column(String(2000), default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    entries: Mapped[list[CollectionEntry]] = relationship(
        back_populates="collection", cascade="all, delete-orphan", order_by="CollectionEntry.id")


class CollectionEntry(db.Model):
    """One monster in a collection: how many of it, and the part it plays (minion, boss...)."""
    __tablename__ = "collection_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey("monster_collections.id", ondelete="CASCADE"), index=True)
    monster: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(20), default="none")
    count: Mapped[int] = mapped_column(default=1)
    note: Mapped[str] = mapped_column(String(300), default="")

    collection: Mapped[MonsterCollection] = relationship(back_populates="entries")


class Environment(db.Model):
    """A DM's own environment group, such as "Underdark" or "Haunted swamp".

    The SRD doesn't say where monsters live, so each DM sorts them into environments themselves.
    """
    __tablename__ = "environments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(40))
    monsters: Mapped[list] = mapped_column(db.JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class FavouriteSpell(db.Model):
    """A spell a user has starred in the spell catalogue, stored by its rules `index` ("fireball")."""
    __tablename__ = "favourite_spells"
    __table_args__ = (UniqueConstraint("user_id", "spell"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    spell: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
