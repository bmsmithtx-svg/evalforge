"""FastAPI dependency boundary for authentication and tenant context.

Every protected route depends on ``get_current_principal`` or
``get_tenant_context`` instead of reading headers or path parameters
itself. This is the single place identity claims are verified and
turned into typed, trustworthy objects.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
import structlog
from fastapi import Depends, HTTPException, Path, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from evalforge_api.domain.enums import MembershipStatus, TenantStatus, UserStatus
from evalforge_api.domain.principal import AuthenticatedPrincipal
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories
from evalforge_api.ports.identity import IdentityRepositories
from evalforge_api.ports.ingestion_repositories import IngestionRepositories
from evalforge_api.security.tokens import TokenValidationError, verify_access_token
from evalforge_api.settings import Settings, get_settings

logger = structlog.get_logger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Missing, invalid, or expired credentials.",
    headers={"WWW-Authenticate": "Bearer"},
)
_FORBIDDEN_TENANT = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Not authorized for this tenant.",
)


def get_identity_repositories(request: Request) -> IdentityRepositories:
    repositories: IdentityRepositories = request.app.state.identity_repositories
    return repositories


def get_evaluation_repositories(request: Request) -> EvaluationRepositories:
    repositories: EvaluationRepositories = request.app.state.evaluation_repositories
    return repositories


def get_ingestion_repositories(request: Request) -> IngestionRepositories:
    repositories: IngestionRepositories = request.app.state.ingestion_repositories
    return repositories


def get_db_pool(request: Request) -> asyncpg.Pool:
    """The shared application-role pool, for the rare case (artifact
    ingestion) where an application service must coordinate a raw
    idempotency-record write around a non-transactional side effect
    (an S3 upload) that a repository's own connection cannot span."""
    pool: asyncpg.Pool = request.app.state.db_pool
    return pool


async def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
    repositories: IdentityRepositories = Depends(get_identity_repositories),
) -> AuthenticatedPrincipal:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise _UNAUTHENTICATED

    try:
        claims = verify_access_token(credentials.credentials, settings=settings)
    except TokenValidationError as exc:
        logger.info("authentication_failed", reason=exc.reason)
        raise _UNAUTHENTICATED from exc

    user = await repositories.users.get_by_id(claims.user_id)
    if user is None or user.status != UserStatus.ACTIVE:
        logger.info("authentication_rejected", reason="inactive_or_unknown_user")
        raise _UNAUTHENTICATED

    return AuthenticatedPrincipal(
        user_id=user.id, email=user.email, kind=user.kind, status=user.status
    )


async def get_tenant_context(
    tenant_id: UUID = Path(...),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    repositories: IdentityRepositories = Depends(get_identity_repositories),
) -> TenantContext:
    membership = await repositories.memberships.get_membership(
        user_id=principal.user_id, tenant_id=tenant_id
    )
    if membership is None or membership.status != MembershipStatus.ACTIVE:
        logger.info(
            "tenant_context_denied",
            user_id=str(principal.user_id),
            tenant_id=str(tenant_id),
        )
        raise _FORBIDDEN_TENANT

    tenant = await repositories.tenants.get_by_id(tenant_id)
    if tenant is None or tenant.status != TenantStatus.ACTIVE:
        logger.info(
            "tenant_context_denied",
            user_id=str(principal.user_id),
            tenant_id=str(tenant_id),
        )
        raise _FORBIDDEN_TENANT

    return TenantContext(
        tenant_id=tenant.id,
        tenant_slug=tenant.slug,
        user_id=principal.user_id,
        role=membership.role,
        membership_status=membership.status,
    )
