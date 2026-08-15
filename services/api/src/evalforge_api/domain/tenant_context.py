"""The verified tenant-scoped security context.

A ``TenantContext`` may only be constructed after independently
verifying an active membership row for the requesting principal. It is
never built from a client-supplied tenant ID alone, and downstream
application code should depend on this type instead of re-deriving
tenant access from raw membership rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from evalforge_api.domain.actions import TenantAction, role_can
from evalforge_api.domain.enums import MembershipStatus, TenantRole


@dataclass(frozen=True, slots=True)
class TenantContext:
    tenant_id: UUID
    tenant_slug: str
    user_id: UUID
    role: TenantRole
    membership_status: MembershipStatus

    @property
    def is_active_member(self) -> bool:
        return self.membership_status == MembershipStatus.ACTIVE

    def can(self, action: TenantAction) -> bool:
        return self.is_active_member and role_can(self.role, action)
