"""Identity, tenancy, and membership lifecycle enums.

These mirror the Postgres enum types created by the identity-and-tenancy
migration. Keeping them as plain ``str`` enums lets domain and
application code compare and serialize values without importing a
database driver.
"""

from __future__ import annotations

from enum import StrEnum


class UserKind(StrEnum):
    HUMAN = "human"
    SERVICE = "service"


class UserStatus(StrEnum):
    INVITED = "invited"
    ACTIVE = "active"
    DISABLED = "disabled"
    REMOVED = "removed"


class TenantStatus(StrEnum):
    PROVISIONED = "provisioned"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class MembershipStatus(StrEnum):
    INVITED = "invited"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REMOVED = "removed"


class TenantRole(StrEnum):
    """Tenant-scoped roles, matching the categories fixed in Milestone 1.

    Workspace administrator is excluded: no workspace entity exists
    until a later milestone. Service identity is not a membership role;
    it is represented by ``UserKind.SERVICE`` on the member's user row.
    """

    TENANT_ADMIN = "tenant_admin"
    EVALUATION_ENGINEER = "evaluation_engineer"
    DEVELOPER = "developer"
    REVIEWER = "reviewer"
    READ_ONLY_OBSERVER = "read_only_observer"
