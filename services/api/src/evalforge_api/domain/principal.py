"""The authenticated-principal representation.

Produced only by verifying a credential server-side (see
``evalforge_api.security.tokens``). Nothing in application or route
code may construct one from client-supplied identity claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from evalforge_api.domain.enums import UserKind, UserStatus


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    user_id: UUID
    email: str
    kind: UserKind
    status: UserStatus

    @property
    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE
