"""Authentication endpoints: register, login, and the current principal.

Delivery-only: request/response shape and status-code mapping live
here, while credential verification and token issuance stay in
``evalforge_api.application.auth_service``.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from evalforge_api.application.auth_service import (
    AuthenticationError,
    RegistrationError,
    authenticate_user,
    register_user,
)
from evalforge_api.domain.principal import AuthenticatedPrincipal
from evalforge_api.ports.identity import IdentityRepositories
from evalforge_api.security.dependencies import get_current_principal, get_identity_repositories
from evalforge_api.security.passwords import MIN_PASSWORD_LENGTH
from evalforge_api.settings import Settings, get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


def _validate_email_shape(value: str) -> str:
    if "@" not in value or value.startswith("@") or value.endswith("@") or " " in value:
        raise ValueError("email must be a valid address")
    return value.strip().lower()


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=256)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return _validate_email_shape(value)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return _validate_email_shape(value)


class UserPublic(BaseModel):
    id: UUID
    email: str
    status: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def post_register(
    body: RegisterRequest,
    repositories: IdentityRepositories = Depends(get_identity_repositories),
) -> UserPublic:
    try:
        user = await register_user(
            email=body.email, password=body.password, repositories=repositories
        )
    except RegistrationError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return UserPublic(id=user.id, email=user.email, status=user.status.value)


@router.post("/login", response_model=TokenResponse)
async def post_login(
    body: LoginRequest,
    repositories: IdentityRepositories = Depends(get_identity_repositories),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    try:
        session = await authenticate_user(
            email=body.email,
            password=body.password,
            repositories=repositories,
            settings=settings,
        )
    except AuthenticationError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    return TokenResponse(
        access_token=session.access_token,
        token_type=session.token_type,
        expires_in=session.expires_in,
    )


@router.get("/me", response_model=UserPublic)
async def get_me(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> UserPublic:
    return UserPublic(id=principal.user_id, email=principal.email, status=principal.status.value)
