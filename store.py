"""Persistent storage for the exam site: accounts and exam results.

Uses SQLAlchemy Core, so the same code runs on a local SQLite file and on a
hosted Postgres database (set DATABASE_URL). Datetimes are stored as naive UTC.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    delete,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

metadata = MetaData()

users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("username", String(32), unique=True, nullable=False),
    Column("password_hash", String(255), nullable=False),
    Column("created_at", DateTime, nullable=False),
    Column("last_login_at", DateTime),
)

attempts = Table(
    "attempts",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id"), index=True),
    Column("guest_id", String(36), index=True),
    Column("filename", String(255), nullable=False),
    Column("exam_title", String(255), nullable=False),
    Column("lang", String(8), nullable=False),
    Column("score", Integer, nullable=False),
    Column("total", Integer, nullable=False),
    Column("answers", Text, nullable=False),
    Column("elapsed_seconds", Integer),
    Column("created_at", DateTime, nullable=False, index=True),
)

app_settings = Table(
    "app_settings",
    metadata,
    Column("key", String(64), primary_key=True),
    Column("value", Text, nullable=False),
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_url(url: str) -> str:
    """Accept the postgres:// URLs hosting providers hand out."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url.removeprefix(prefix)
    return url


class Store:
    def __init__(self, url: str):
        url = normalize_url(url)
        kwargs: dict = {}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
            if url in ("sqlite://", "sqlite:///:memory:"):
                kwargs["poolclass"] = StaticPool
            else:
                Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        else:
            kwargs["pool_pre_ping"] = True
        self.engine = create_engine(url, **kwargs)
        metadata.create_all(self.engine)

    # ── Settings ──

    def get_or_create_setting(self, key: str, make_value) -> str:
        with self.engine.begin() as conn:
            row = conn.execute(select(app_settings.c.value).where(app_settings.c.key == key)).first()
            if row:
                return row.value
        try:
            with self.engine.begin() as conn:
                conn.execute(insert(app_settings).values(key=key, value=make_value()))
        except IntegrityError:
            pass  # another worker created it first
        with self.engine.begin() as conn:
            return conn.execute(select(app_settings.c.value).where(app_settings.c.key == key)).scalar_one()

    # ── Users ──

    def get_user(self, user_id: int) -> dict | None:
        with self.engine.begin() as conn:
            row = conn.execute(select(users).where(users.c.id == user_id)).first()
        return dict(row._mapping) if row else None

    def get_user_by_username(self, username: str) -> dict | None:
        with self.engine.begin() as conn:
            row = conn.execute(select(users).where(users.c.username == username)).first()
        return dict(row._mapping) if row else None

    def create_user(self, username: str, password_hash: str) -> dict | None:
        """Create an account, or return None if the username is taken."""
        try:
            with self.engine.begin() as conn:
                conn.execute(insert(users).values(username=username, password_hash=password_hash, created_at=utcnow()))
        except IntegrityError:
            return None
        return self.get_user_by_username(username)

    def touch_login(self, user_id: int) -> None:
        with self.engine.begin() as conn:
            conn.execute(update(users).where(users.c.id == user_id).values(last_login_at=utcnow()))

    def delete_user(self, user_id: int) -> None:
        with self.engine.begin() as conn:
            conn.execute(delete(attempts).where(attempts.c.user_id == user_id))
            conn.execute(delete(users).where(users.c.id == user_id))

    # ── Attempts ──

    def save_attempt(
        self,
        *,
        filename: str,
        exam_title: str,
        lang: str,
        score: int,
        total: int,
        answers: dict[str, str],
        elapsed_seconds: int | None,
        user_id: int | None,
        guest_id: str | None,
    ) -> str:
        attempt_id = str(uuid.uuid4())
        with self.engine.begin() as conn:
            conn.execute(
                insert(attempts).values(
                    id=attempt_id,
                    user_id=user_id,
                    guest_id=None if user_id else guest_id,
                    filename=filename,
                    exam_title=exam_title,
                    lang=lang,
                    score=score,
                    total=total,
                    answers=json.dumps(answers),
                    elapsed_seconds=elapsed_seconds,
                    created_at=utcnow(),
                )
            )
        return attempt_id

    def get_attempt(self, attempt_id: str) -> dict | None:
        with self.engine.begin() as conn:
            row = conn.execute(select(attempts).where(attempts.c.id == attempt_id)).first()
        if not row:
            return None
        data = dict(row._mapping)
        data["answers"] = json.loads(data["answers"])
        return data

    def _owner_clause(self, user_id: int | None, guest_id: str | None):
        if user_id:
            return attempts.c.user_id == user_id
        if guest_id:
            return (attempts.c.guest_id == guest_id) & attempts.c.user_id.is_(None)
        return None

    def list_attempts(
        self, *, user_id: int | None = None, guest_id: str | None = None, limit: int | None = None
    ) -> list[dict]:
        """Attempts by one owner, newest first, without their answers."""
        clause = self._owner_clause(user_id, guest_id)
        if clause is None:
            return []
        cols = [c for c in attempts.c if c.name != "answers"]
        query = select(*cols).where(clause).order_by(attempts.c.created_at.desc())
        if limit:
            query = query.limit(limit)
        with self.engine.begin() as conn:
            return [dict(r._mapping) for r in conn.execute(query)]

    def count_attempts(self, *, user_id: int | None = None, guest_id: str | None = None) -> int:
        clause = self._owner_clause(user_id, guest_id)
        if clause is None:
            return 0
        with self.engine.begin() as conn:
            return conn.execute(select(func.count()).select_from(attempts).where(clause)).scalar_one()

    def claim_guest_attempts(self, guest_id: str, user_id: int) -> int:
        with self.engine.begin() as conn:
            result = conn.execute(
                update(attempts)
                .where(attempts.c.guest_id == guest_id)
                .where(attempts.c.user_id.is_(None))
                .values(user_id=user_id, guest_id=None)
            )
        return result.rowcount
