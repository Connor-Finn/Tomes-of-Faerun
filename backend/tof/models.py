from __future__ import annotations

from datetime import date, datetime, timezone

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
    favourite_items: Mapped[list[FavouriteItem]] = relationship(cascade="all, delete-orphan")
    campaigns: Mapped[list[Campaign]] = relationship(back_populates="dm", cascade="all, delete-orphan")
    parties: Mapped[list[Party]] = relationship(back_populates="dm", cascade="all, delete-orphan")
    memberships: Mapped[list[PartyMember]] = relationship(back_populates="user", cascade="all, delete-orphan")
    instances: Mapped[list[CharacterInstance]] = relationship(back_populates="user", cascade="all, delete-orphan")
    published: Mapped[list[PublishedCharacter]] = relationship(back_populates="author", cascade="all, delete-orphan")
    chat_states: Mapped[list[PartyChatState]] = relationship(cascade="all, delete-orphan")
    sent_friend_requests: Mapped[list[Friendship]] = relationship(
        foreign_keys="Friendship.requester_id", cascade="all, delete-orphan", overlaps="requester")
    received_friend_requests: Mapped[list[Friendship]] = relationship(
        foreign_keys="Friendship.addressee_id", cascade="all, delete-orphan", overlaps="addressee")
    join_requests: Mapped[list[JoinRequest]] = relationship(
        foreign_keys="JoinRequest.user_id", cascade="all, delete-orphan", overlaps="user")

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
    # Deleting a character keeps its campaign instances: they just lose the link back here.
    instances: Mapped[list[CharacterInstance]] = relationship(back_populates="character")
    roadmaps: Mapped[list[Roadmap]] = relationship(
        back_populates="character", cascade="all, delete-orphan", order_by="Roadmap.id")

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
    campaign_links: Mapped[list[CampaignEncounter]] = relationship(
        back_populates="collection", cascade="all, delete-orphan")


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


class FavouriteItem(db.Model):
    """An item (equipment or magic item) a user has starred, stored by its rules `index` ("bag-of-holding")."""
    __tablename__ = "favourite_items"
    __table_args__ = (UniqueConstraint("user_id", "item"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    item: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Campaign(db.Model):
    """A campaign a Dungeon Master runs. It can exist without a party.

    Pages (see campaigns.py): overview, party, session log, encounters and the DM's private notes.
    """
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    dm_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(4000), default="")
    status: Mapped[str] = mapped_column(String(20), default="planning")
    dm_notes: Mapped[str] = mapped_column(String(10000), default="")
    party_id: Mapped[int | None] = mapped_column(ForeignKey("parties.id", ondelete="SET NULL"), index=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    dm: Mapped[User] = relationship(back_populates="campaigns")
    sessions: Mapped[list[SessionEntry]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan",
        order_by="(SessionEntry.played_on.desc(), SessionEntry.id.desc())")
    encounters: Mapped[list[CampaignEncounter]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan", order_by="CampaignEncounter.id")
    party: Mapped[Party | None] = relationship(back_populates="campaigns")
    instances: Mapped[list[CharacterInstance]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan", order_by="CharacterInstance.id")


class SessionEntry(db.Model):
    """One entry in a campaign's session log: what happened at the table on a given day."""
    __tablename__ = "campaign_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    played_on: Mapped[date]
    title: Mapped[str] = mapped_column(String(100))
    summary: Mapped[str] = mapped_column(String(5000), default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    campaign: Mapped[Campaign] = relationship(back_populates="sessions")


class CampaignEncounter(db.Model):
    """A bestiary collection the DM attached to a campaign, such as "Warlock boss dungeon"."""
    __tablename__ = "campaign_encounters"
    __table_args__ = (UniqueConstraint("campaign_id", "collection_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey("monster_collections.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    campaign: Mapped[Campaign] = relationship(back_populates="encounters")
    collection: Mapped[MonsterCollection] = relationship(back_populates="campaign_links")


class Party(db.Model):
    """A group of players a Dungeon Master leads. Only DMs create parties.

    The DM invites players by email; an invited player accepts or declines. The DM then attaches
    the party to one or more campaigns, and its members can bring a character to each.
    """
    __tablename__ = "parties"

    id: Mapped[int] = mapped_column(primary_key=True)
    dm_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    description: Mapped[str] = mapped_column(String(1000), default="")
    visibility: Mapped[str] = mapped_column(String(10), default="private")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    dm: Mapped[User] = relationship(back_populates="parties")
    members: Mapped[list[PartyMember]] = relationship(
        back_populates="party", cascade="all, delete-orphan", order_by="PartyMember.id")
    campaigns: Mapped[list[Campaign]] = relationship(back_populates="party", order_by="Campaign.name")
    messages: Mapped[list[PartyMessage]] = relationship(
        back_populates="party", cascade="all, delete-orphan", order_by="PartyMessage.id")
    chat_states: Mapped[list[PartyChatState]] = relationship(cascade="all, delete-orphan")
    join_requests: Mapped[list[JoinRequest]] = relationship(
        back_populates="party", cascade="all, delete-orphan", order_by="JoinRequest.id")


class PartyMember(db.Model):
    """A player in a party, or invited to one (status "invited" until they accept)."""
    __tablename__ = "party_members"
    __table_args__ = (UniqueConstraint("party_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    party_id: Mapped[int] = mapped_column(ForeignKey("parties.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(10), default="invited")
    invited_at: Mapped[datetime] = mapped_column(default=utcnow)
    joined_at: Mapped[datetime | None]

    party: Mapped[Party] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")


class CharacterInstance(db.Model):
    """A player's character as it stands in one campaign.

    Joining a campaign copies the base character's build. From then on the instance levels up,
    takes damage and picks up items on its own; the base character in the Character Manager never
    changes. The DM can read the sheet and leave a note the player sees.
    """
    __tablename__ = "character_instances"
    __table_args__ = (UniqueConstraint("campaign_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    character_id: Mapped[int | None] = mapped_column(ForeignKey("characters.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    build: Mapped[dict] = mapped_column(db.JSON)
    build_mode: Mapped[str] = mapped_column(String(10), default="standard")
    is_complete: Mapped[bool] = mapped_column(default=True)
    current_hp: Mapped[int | None]
    temp_hp: Mapped[int] = mapped_column(default=0)
    dm_note: Mapped[str] = mapped_column(String(2000), default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    campaign: Mapped[Campaign] = relationship(back_populates="instances")
    user: Mapped[User] = relationship(back_populates="instances")
    character: Mapped[Character | None] = relationship(back_populates="instances")
    following: Mapped[InstanceRoadmap | None] = relationship(
        back_populates="instance", cascade="all, delete-orphan", uselist=False)
    backup: Mapped[InstanceBackup | None] = relationship(cascade="all, delete-orphan", uselist=False)


class PublishedCharacter(db.Model):
    """A character its author shared as a template other players can copy.

    Publishing takes a snapshot of the build, so later edits to the author's character never change
    the template, and copies made from it are their new owners' own characters.
    """
    __tablename__ = "published_characters"

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    character_id: Mapped[int | None] = mapped_column(ForeignKey("characters.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    summary: Mapped[str] = mapped_column(String(300), default="")
    build: Mapped[dict] = mapped_column(db.JSON)
    build_mode: Mapped[str] = mapped_column(String(10), default="standard")
    copies: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    author: Mapped[User] = relationship(back_populates="published")
    roadmaps: Mapped[list[PublishedRoadmap]] = relationship(cascade="all, delete-orphan", order_by="PublishedRoadmap.id")


class PartyMessage(db.Model):
    """One message in a party's chat. The DM and the party's members can read and write it."""
    __tablename__ = "party_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    party_id: Mapped[int] = mapped_column(ForeignKey("parties.id", ondelete="CASCADE"), index=True)
    # Kept when the author deletes their account; the chat then says "a departed adventurer".
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    body: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    party: Mapped[Party] = relationship(back_populates="messages")
    author: Mapped[User | None] = relationship()


class PartyChatState(db.Model):
    """Where one person is in one party's chat: the last message they've read, and when they last
    wrote something (so the others see "Mira is writing…")."""
    __tablename__ = "party_chat_states"
    __table_args__ = (UniqueConstraint("party_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    party_id: Mapped[int] = mapped_column(ForeignKey("parties.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    last_read_id: Mapped[int] = mapped_column(default=0)
    writing_at: Mapped[datetime | None]


class Friendship(db.Model):
    """A friend request, or (once accepted) a friendship. One row per pair of people, whoever asked."""
    __tablename__ = "friendships"
    __table_args__ = (UniqueConstraint("requester_id", "addressee_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    addressee_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending | accepted
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    accepted_at: Mapped[datetime | None]

    requester: Mapped[User] = relationship(foreign_keys=[requester_id])
    addressee: Mapped[User] = relationship(foreign_keys=[addressee_id])

    def other(self, user: User) -> User:
        return self.addressee if self.requester_id == user.id else self.requester


class JoinRequest(db.Model):
    """Someone asking to join a party, waiting for the party's DM to say yes or no.

    Either the player asked themselves (a public party), or a party member suggested a friend
    (`suggested_by`), which works for private parties too. The DM always decides.
    """
    __tablename__ = "join_requests"
    __table_args__ = (UniqueConstraint("party_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    party_id: Mapped[int] = mapped_column(ForeignKey("parties.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    suggested_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    message: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    party: Mapped[Party] = relationship(back_populates="join_requests")
    user: Mapped[User] = relationship(foreign_keys=[user_id])
    suggested_by: Mapped[User | None] = relationship(foreign_keys=[suggested_by_id])


class Roadmap(db.Model):
    """A planned route of level-ups for one base character, up to level 20.

    `levels` holds the character's levelling choices at every planned level, keyed by level
    ("4": {"subclass": ..., "choices": {...}}). The first key is the level the character was at
    when the roadmap started, copied from the character; each later level is a complete snapshot,
    so following the roadmap at level 7 is just "take level 7's choices".
    """
    __tablename__ = "roadmaps"

    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    start_level: Mapped[int] = mapped_column(default=1)
    levels: Mapped[dict] = mapped_column(db.JSON)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    character: Mapped[Character] = relationship(back_populates="roadmaps")
    followers: Mapped[list[InstanceRoadmap]] = relationship(back_populates="roadmap", cascade="all, delete-orphan")

    @property
    def end_level(self) -> int:
        return max(int(k) for k in self.levels)


class InstanceRoadmap(db.Model):
    """A campaign instance following one of its base character's roadmaps.

    Its own table (rather than a column on character_instances) so existing databases pick it up
    without a migration.
    """
    __tablename__ = "instance_roadmaps"

    instance_id: Mapped[int] = mapped_column(ForeignKey("character_instances.id", ondelete="CASCADE"), primary_key=True)
    roadmap_id: Mapped[int] = mapped_column(ForeignKey("roadmaps.id", ondelete="CASCADE"), index=True)
    followed_at: Mapped[datetime] = mapped_column(default=utcnow)

    instance: Mapped[CharacterInstance] = relationship(back_populates="following")
    roadmap: Mapped[Roadmap] = relationship(back_populates="followers")


class InstanceBackup(db.Model):
    """The one backup copy a player may keep of their character in a campaign."""
    __tablename__ = "instance_backups"

    instance_id: Mapped[int] = mapped_column(ForeignKey("character_instances.id", ondelete="CASCADE"), primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    build: Mapped[dict] = mapped_column(db.JSON)
    build_mode: Mapped[str] = mapped_column(String(10), default="standard")
    current_hp: Mapped[int | None]
    temp_hp: Mapped[int] = mapped_column(default=0)
    # The roadmap the instance was following when the backup was made (no foreign key: the roadmap
    # may be deleted later, and restoring then just doesn't follow anything).
    roadmap_id: Mapped[int | None]
    reason: Mapped[str] = mapped_column(String(100), default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class PublishedRoadmap(db.Model):
    """A roadmap attached to a published character: a snapshot, like the character itself."""
    __tablename__ = "published_roadmaps"

    id: Mapped[int] = mapped_column(primary_key=True)
    published_id: Mapped[int] = mapped_column(ForeignKey("published_characters.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    start_level: Mapped[int] = mapped_column(default=1)
    levels: Mapped[dict] = mapped_column(db.JSON)
