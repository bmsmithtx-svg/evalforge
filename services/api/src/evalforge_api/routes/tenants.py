"""Tenant-membership endpoints.

``GET /tenants`` lists the caller's own memberships and never accepts a
client-supplied tenant filter. ``GET /tenants/{tenant_id}/context`` and
``GET /tenants/{tenant_id}/members`` both require the path tenant ID to
resolve to a verified, active membership through
``evalforge_api.security.dependencies.get_tenant_context`` before any
tenant data is returned.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from evalforge_api.application.tenant_service import (
    AuthorizationDeniedError,
    list_my_tenants,
    list_tenant_members,
)
from evalforge_api.domain.principal import AuthenticatedPrincipal
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.ports.identity import IdentityRepositories
from evalforge_api.security.dependencies import (
    get_current_principal,
    get_identity_repositories,
    get_tenant_context,
)

router = APIRouter(prefix="/tenants", tags=["tenants"])


class TenantMembershipResponse(BaseModel):
    tenant_id: UUID
    tenant_slug: str
    tenant_name: str
    role: str
    membership_status: str


class TenantContextResponse(BaseModel):
    tenant_id: UUID
    tenant_slug: str
    role: str
    membership_status: str


class TenantMemberResponse(BaseModel):
    user_id: UUID
    role: str
    membership_status: str


@router.get("", response_model=list[TenantMembershipResponse])
async def get_my_tenants(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    repositories: IdentityRepositories = Depends(get_identity_repositories),
) -> list[TenantMembershipResponse]:
    summaries = await list_my_tenants(user_id=principal.user_id, repositories=repositories)
    return [
        TenantMembershipResponse(
            tenant_id=summary.tenant.id,
            tenant_slug=summary.tenant.slug,
            tenant_name=summary.tenant.name,
            role=summary.membership.role.value,
            membership_status=summary.membership.status.value,
        )
        for summary in summaries
    ]


@router.get("/{tenant_id}/context", response_model=TenantContextResponse)
async def get_tenant_context_route(
    context: TenantContext = Depends(get_tenant_context),
) -> TenantContextResponse:
    return TenantContextResponse(
        tenant_id=context.tenant_id,
        tenant_slug=context.tenant_slug,
        role=context.role.value,
        membership_status=context.membership_status.value,
    )


@router.get("/{tenant_id}/members", response_model=list[TenantMemberResponse])
async def get_tenant_members(
    context: TenantContext = Depends(get_tenant_context),
    repositories: IdentityRepositories = Depends(get_identity_repositories),
) -> list[TenantMemberResponse]:
    try:
        members = await list_tenant_members(context=context, repositories=repositories)
    except AuthorizationDeniedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    return [
        TenantMemberResponse(
            user_id=member.user_id,
            role=member.role.value,
            membership_status=member.status.value,
        )
        for member in members
    ]
