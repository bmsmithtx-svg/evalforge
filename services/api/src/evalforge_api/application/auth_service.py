"""Registration and login orchestration.

Routes call only these two functions; they never touch password
hashing, token issuance, or the user repository directly. Both
functions return the same generic failure for every distinct rejection
reason (unknown email, wrong password, inactive account) so a caller
cannot use response content to enumerate registered accounts.
"""

from __future__ import annotations

from dataclasses import dataclass

from evalforge_api.adapters.user_repository import EmailAlreadyRegisteredError
from evalforge_api.audit import emit_audit_event
from evalforge_api.domain.enums import UserKind, UserStatus
from evalforge_api.ports.identity import IdentityRepositories, UserRecord
from evalforge_api.security.passwords import MIN_PASSWORD_LENGTH, hash_password, verify_password
from evalforge_api.security.tokens import issue_access_token
from evalforge_api.settings import Settings

_TIMING_NORMALIZATION_HASH = hash_password("evalforge-timing-normalization-placeholder")


class RegistrationError(Exception):
    pass


class AuthenticationError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class AuthenticatedSession:
    access_token: str
    token_type: str
    expires_in: int
    user: UserRecord


async def register_user(
    *, email: str, password: str, repositories: IdentityRepositories
) -> UserRecord:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise RegistrationError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")

    password_hash = hash_password(password)
    try:
        user = await repositories.users.create(
            email=email, password_hash=password_hash, kind=UserKind.HUMAN
        )
    except EmailAlreadyRegisteredError as exc:
        emit_audit_event(event="user_registration", outcome="denied_conflict")
        raise RegistrationError("An account with this email already exists.") from exc

    emit_audit_event(event="user_registration", outcome="success", actor_user_id=str(user.id))
    return user


async def authenticate_user(
    *, email: str, password: str, repositories: IdentityRepositories, settings: Settings
) -> AuthenticatedSession:
    user = await repositories.users.get_by_email(email)

    if user is None:
        verify_password(password, _TIMING_NORMALIZATION_HASH)
        emit_audit_event(event="user_login", outcome="denied")
        raise AuthenticationError("Invalid email or password.")

    if not verify_password(password, user.password_hash) or user.status != UserStatus.ACTIVE:
        emit_audit_event(event="user_login", outcome="denied", actor_user_id=str(user.id))
        raise AuthenticationError("Invalid email or password.")

    access_token = issue_access_token(user_id=user.id, email=user.email, settings=settings)
    emit_audit_event(event="user_login", outcome="success", actor_user_id=str(user.id))
    return AuthenticatedSession(
        access_token=access_token,
        token_type="bearer",  # noqa: S106 -- OAuth2 scheme label, not a credential
        expires_in=settings.jwt_access_token_ttl_seconds,
        user=user,
    )
