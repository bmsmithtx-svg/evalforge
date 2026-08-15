"""Ports for identity and tenancy persistence.

Application services depend on these protocols, never on a concrete
database client. Concrete PostgreSQL implementations live under
``evalforge_api.adapters``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from evalforge_api.domain.enums import (
    MembershipStatus,
    TenantRole,
    TenantStatus,
    UserKind,
    UserStatus,
)


@dataclass(frozen=True, slots=True)
class UserRecord:
    id: UUID
    email: str
    password_hash: str
    kind: UserKind
    status: UserStatus
    created_at: datetime


@dataclass(frozen=True, slots=True)
class TenantRecord:
    id: UUID
    slug: str
    name: str
    status: TenantStatus
    created_at: datetime


@dataclass(frozen=True, slots=True)
class MembershipRecord:
    id: UUID
    user_id: UUID
    tenant_id: UUID
    role: TenantRole
    status: MembershipStatus
    created_at: datetime


class UserRepository(Protocol):
    async def create(self, *, email: str, password_hash: str, kind: UserKind) -> UserRecord: ...

    async def get_by_id(self, user_id: UUID) -> UserRecord | None: ...

    async def get_by_email(self, email: str) -> UserRecord | None: ...


class TenantRepository(Protocol):
    async def get_by_id(self, tenant_id: UUID) -> TenantRecord | None: ...


class MembershipRepository(Protocol):
    async def create(
        self, *, user_id: UUID, tenant_id: UUID, role: TenantRole
    ) -> MembershipRecord: ...

    async def get_membership(
        self, *, user_id: UUID, tenant_id: UUID
    ) -> MembershipRecord | None: ...

    async def list_for_user(self, user_id: UUID) -> tuple[MembershipRecord, ...]: ...

    async def list_for_tenant(
        self, *, tenant_id: UUID, requesting_user_id: UUID
    ) -> tuple[MembershipRecord, ...]: ...


@dataclass(frozen=True, slots=True)
class IdentityRepositories:
    """Bundle of identity/tenancy ports handed to request dependencies."""

    users: UserRepository
    tenants: TenantRepository
    memberships: MembershipRepository
