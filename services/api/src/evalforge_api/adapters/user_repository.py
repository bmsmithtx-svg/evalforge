"""PostgreSQL-backed user repository."""

from __future__ import annotations

from uuid import UUID

import asyncpg

from evalforge_api.domain.enums import UserKind, UserStatus
from evalforge_api.ports.identity import UserRecord

_SELECT_COLUMNS = "id, email, password_hash, kind, status, created_at"


class EmailAlreadyRegisteredError(Exception):
    pass


def _row_to_user(row: asyncpg.Record) -> UserRecord:
    return UserRecord(
        id=row["id"],
        email=row["email"],
        password_hash=row["password_hash"],
        kind=UserKind(row["kind"]),
        status=UserStatus(row["status"]),
        created_at=row["created_at"],
    )


class PostgresUserRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(self, *, email: str, password_hash: str, kind: UserKind) -> UserRecord:
        normalized_email = email.strip().lower()
        async with self._pool.acquire() as connection:
            try:
                row = await connection.fetchrow(
                    f"""
                    INSERT INTO users (email, password_hash, kind)
                    VALUES ($1, $2, $3)
                    RETURNING {_SELECT_COLUMNS}
                    """,  # noqa: S608
                    normalized_email,
                    password_hash,
                    kind.value,
                )
            except asyncpg.UniqueViolationError as exc:
                raise EmailAlreadyRegisteredError from exc
        assert row is not None
        return _row_to_user(row)

    async def get_by_id(self, user_id: UUID) -> UserRecord | None:
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(
                f"SELECT {_SELECT_COLUMNS} FROM users WHERE id = $1",  # noqa: S608
                user_id,
            )
        return _row_to_user(row) if row is not None else None

    async def get_by_email(self, email: str) -> UserRecord | None:
        normalized_email = email.strip().lower()
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(
                f"SELECT {_SELECT_COLUMNS} FROM users WHERE email = $1",  # noqa: S608
                normalized_email,
            )
        return _row_to_user(row) if row is not None else None
