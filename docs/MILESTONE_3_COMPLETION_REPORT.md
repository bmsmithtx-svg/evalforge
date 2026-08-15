# Milestone 3 Completion Report

Date: 2026-08-15.

## Repository Identity

- Remote: `https://github.com/bmsmithtx-svg/evalforge.git`
- Branch: `main`
- Starting commit: `2495212` (Milestone 2 owner approval)

## Roadmap Status

- Milestone 0: Approved.
- Milestone 1: Approved.
- Milestone 2: Approved.
- Milestone 3: Implemented and validated; owner review pending.
- Milestones 4-15: Not started.

## Owner Approval

Milestone 3 (Authentication, Authorization, and Tenant Isolation) was authorized and implemented in this session. It is not yet owner-approved; this report is submitted for owner review. Milestone 4 has not been started.

## Architecture Implemented

- **Authentication**: self-issued HS256 JWT bearer tokens (`services/api/src/evalforge_api/security/tokens.py`, `passwords.py`, `dependencies.py`). Tokens are verified for signature, issuer, audience, and expiry on every request; the signing key is a required, fail-closed, minimum-32-character setting (`EVALFORGE_JWT_SIGNING_KEY`) with no default and no local-dev bypass. Tokens carry only `sub`/`email`; the requesting user's live status is re-read from PostgreSQL on every request, so a disabled account loses access immediately rather than at token expiry. Passwords are hashed with bcrypt (12 rounds); login uses a fixed dummy-hash comparison for unknown emails and one generic error message for every rejection reason (unknown email, wrong password, inactive account) to resist account enumeration.
- **Identity model**: a `users` table keyed on an application-generated UUID, decoupled from `auth_provider` / `provider_subject` columns reserved for future external identity providers, so tenant-owned data never needs to be re-keyed when one is added. A `kind` column (`human` / `service`) is the schema-level hook for the service-identity concept; provisioning workflows for service identities remain a later milestone.
- **Tenant model**: a `tenants` table with an immutable UUID primary key and a unique `slug`.
- **Membership model**: a `tenant_memberships` table binding a user, a tenant, and a role, with `UNIQUE (user_id, tenant_id)` and foreign keys to both parents.
- **Role model**: `TenantRole` (`tenant_admin`, `evaluation_engineer`, `developer`, `reviewer`, `read_only_observer`) — the tenant-scoped subset of the role categories fixed in [Tenancy and Authorization](TENANCY_AND_AUTHORIZATION.md) (workspace administrator excluded because no workspace entity exists yet; service identity excluded because it is not a membership role).
- **Authorization mechanism**: a single, deny-by-default permission table (`domain/actions.py:role_can`) that every route consults through `TenantContext.can()` — no route compares role strings inline. `services/api/src/evalforge_api/application/tenant_service.py` enforces this before returning other members' data and emits an audit event on every denial.
- **Tenant-context mechanism**: `security/dependencies.py:get_tenant_context` takes the path's tenant ID only as a request; it independently looks up an active membership row for the authenticated principal before constructing a `TenantContext`, and denies with an identical 403 whether the tenant exists, is inactive, or the caller simply isn't a member — so cross-tenant probing cannot distinguish those cases.
- **Database-isolation strategy**: PostgreSQL row-level security on `tenant_memberships` (`ENABLE`/`FORCE ROW LEVEL SECURITY`), keyed on transaction-local `app.current_user_id` / `app.current_tenant_id` session settings that the repository layer sets from server-verified identity on every query — never from client input. Because table owners and superusers bypass RLS regardless of policy, the running API connects through a separate, non-superuser `evalforge_app` role with only `SELECT`/`INSERT` grants; the administrative/migration role is never used to serve requests. This was verified, not assumed: `test_row_level_security_denies_reads_with_no_session_context` connects as `evalforge_app` with no session context and confirms zero rows are visible despite matching data existing.

## Files Changed

- **Backend** (`services/api/src/evalforge_api/`): new `domain/` (enums, actions/permission table, principal, tenant context), `security/` (passwords, tokens, FastAPI dependencies), `application/` (auth_service, tenant_service), `audit.py`, `ports/identity.py`, `adapters/{user,tenant,membership}_repository.py` and `postgres_pool.py`, `routes/{auth,tenants}.py`, `dev_seed.py`; modified `settings.py` (JWT + `app_database_url` settings), `app.py` (DB pool lifecycle, dependency override for testable settings, new routers), `dependency_wiring.py`, `error_handling.py` (fixed a latent bug where a custom Pydantic validator's `ValueError` made the 422 response body non-JSON-serializable).
- **Migration**: `services/api/alembic/versions/20260815_0002_identity_and_tenancy.py`.
- **Backend tests** (`services/api/tests/`): `test_password_hashing.py`, `test_tokens.py`, `test_authorization.py`, `test_auth_routes.py`, `test_membership_repository.py`, `test_tenant_isolation.py`; extended `conftest.py` (migrated test database, least-privilege test role, `api_client`/`identity_repositories`/`create_tenant` fixtures) and `test_error_handling.py` (regression test).
- **Frontend** (`apps/web/src/`): `lib/auth-client.ts`, `lib/session.ts`, `lib/actions/auth-actions.ts`, `app/login/`; extended `lib/api-client.ts` (generalized `requestJson`); rewrote `app/page.tsx` to show authenticated/unauthenticated state and tenant memberships; `tests/auth-client.test.ts`.
- **Infrastructure/config**: `infrastructure/docker-compose.yml` (`migrate` one-shot service, `evalforge_app` credentials), `infrastructure/docker-compose.test.yml` (new, ephemeral test-only PostgreSQL), `Makefile` (`test-services-up`/`down`, `test` now depends on the test database), `.github/workflows/ci.yml` (Postgres service container for the `api` job), `services/api/.env.example`, `services/api/pyproject.toml` (PyJWT, bcrypt, bugbear FastAPI allowlist).
- **Docs**: this report; `README.md`, `docs/ROADMAP.md`, `docs/TENANCY_AND_AUTHORIZATION.md`.

## Database

- **Tables added**: `users`, `tenants`, `tenant_memberships`.
- **Types added**: `user_kind`, `user_status`, `tenant_status`, `tenant_role`, `membership_status` (Postgres enums).
- **Constraints**: `users.email` unique; `(users.auth_provider, users.provider_subject)` unique; `tenants.slug` unique; `tenant_memberships (user_id, tenant_id)` unique; `tenant_memberships.user_id` / `.tenant_id` foreign keys with `ON DELETE CASCADE`.
- **Indexes**: `ix_tenant_memberships_tenant_id`, `ix_tenant_memberships_user_id`.
- **Least-privilege role**: the migration creates/updates `evalforge_app` (`LOGIN`, no superuser, no `BYPASSRLS`) from a required `EVALFORGE_APP_DB_PASSWORD` environment value and grants it exactly `USAGE` on schema `public`, `SELECT`/`INSERT` on `users` and `tenant_memberships`, and `SELECT` on `tenants` — it cannot create tenants, update, or delete anything. `downgrade()` revokes the grants and drops the role.
- **RLS**: `tenant_memberships` has `ENABLE`/`FORCE ROW LEVEL SECURITY` with a `SELECT` policy (`user_id = app.current_user_id OR tenant_id = app.current_tenant_id`) and an `INSERT` policy (`WITH CHECK (tenant_id = app.current_tenant_id)`), both keyed on transaction-local settings populated only from server-verified identity.
- **Migrations**: `0001_foundation_baseline` (Milestone 2, empty) → `0002_identity_and_tenancy` (this milestone). Verified against a clean database in every test run (`test_migration_head_revision_is_applied`) and against the Milestone 2 baseline via the live Docker Compose `migrate` service, which ran both migrations in sequence.

## API

| Endpoint | Method | Protection |
| --- | --- | --- |
| `/auth/register` | POST | Public; creates a `human` user. |
| `/auth/login` | POST | Public; returns a bearer token on valid, active-account credentials. |
| `/auth/me` | GET | Requires a valid bearer token (`get_current_principal`). |
| `/tenants` | GET | Requires a valid bearer token; returns only the caller's own memberships. |
| `/tenants/{tenant_id}/context` | GET | Requires a valid bearer token and an active membership in `tenant_id` (`get_tenant_context`). |
| `/tenants/{tenant_id}/members` | GET | Same as above, plus `tenant_admin` role (`TenantAction.LIST_TENANT_MEMBERS`). |

`/healthz` and `/readyz` are unchanged and remain unauthenticated, matching their existing infrastructure-health contract. OpenAPI (`/docs`, `/openapi.json`) reflects the `HTTPBearer` security scheme on every protected route.

## Web

`apps/web` gained a `/login` page (email/password form, `useActionState`) and a server action that calls `POST /auth/login` and stores the resulting token only in an httpOnly, `sameSite=lax` cookie (`secure` in production) — page JavaScript cannot read it (`document.cookie` is empty on a signed-in page; verified in the browser). The home page is a Server Component that revalidates the session against `GET /auth/me` on every render and shows the caller's own tenant memberships (`GET /tenants`) or a sign-in prompt; a 401 from either call is treated as signed-out. No dashboards, membership-management UI, or other product functionality was added.

## Security Evidence

- **Unauthenticated access**: every protected route depends on `get_current_principal`; missing, malformed, forged (`alg: none`), wrong-signature, wrong-issuer, wrong-audience, and expired tokens are all rejected with 401 (`test_tokens.py`, `test_auth_routes.py`).
- **Unauthorized access**: `tenant_service.list_tenant_members` checks the central permission table before returning member data; a `developer` gets 403 listing members while still getting 200 for their own context (`test_tenant_isolation.py::test_role_in_one_tenant_does_not_confer_the_same_role_in_another`, verified again live via curl in Docker Compose).
- **Cross-tenant access**: `get_tenant_context` independently verifies membership in the path's tenant; a Tenant A-only user is denied for Tenant B's context and members with an identical 403 body regardless of whether Tenant B exists (`test_tenant_a_user_cannot_view_tenant_b_context`, `test_substituting_tenant_b_id_does_not_bypass_authorization`; live-verified with a random UUID producing the same 403 as a real other tenant). Repository-level cross-tenant leakage is separately verified (`test_list_for_tenant_never_returns_another_tenants_rows`) and RLS is verified as a second, independent barrier (`test_row_level_security_denies_reads_with_no_session_context`).
- **Role escalation**: a user with memberships in two tenants gets the correct, independent role in each (`test_role_in_one_tenant_does_not_confer_the_same_role_in_another`); role assignment is per-membership-row, not per-user.
- **Identity spoofing**: identity is derived only from a verified JWT `sub` claim resolved against the database; no route accepts a client-supplied user or tenant ID as authorization.
- **Accidental fail-open**: `Settings.jwt_signing_key` has no default and rejects placeholder values, so the process refuses to start rather than run with a weak or missing key; `get_tenant_context` denies whenever membership lookup returns anything other than an active row; RLS denies by default for any operation without an explicit policy (no `UPDATE`/`DELETE` policy exists yet, so those are currently blocked entirely rather than open).
- **Secret/token leakage**: Milestone 2's structured-log redaction processor (`redaction.py`) continues to run on every log event; passwords and tokens are never logged (verified by inspecting live Docker Compose `api` logs across a full login/authz/deny cycle — no matches for `password`, `secret`, `jwt_signing_key`, or `access_token`). Audit events (`audit.py`) record actor, tenant, event, and outcome without embedding credentials.

## Tests

- **Backend** (`services/api`, `pytest`): 60 passed, 0 failed. Coverage 87% (`--cov=evalforge_api`); uncovered lines are network-failure branches in the PostgreSQL/Redis/object-storage connectivity adapters (pre-existing from Milestone 2, exercised only against live-dependency failure) and `dev_seed.py`, which is a manually invoked local-only script exercised live in Docker Compose rather than under pytest.
  - `test_password_hashing.py` (4), `test_tokens.py` (7), `test_authorization.py` (5): pure unit tests, no database.
  - `test_auth_routes.py` (12): registration, login, `/auth/me`, including duplicate email, weak/malformed input, wrong password, unknown email, disabled account, malformed/expired token.
  - `test_membership_repository.py` (7): migration-head check, foreign-key violation, unique-violation, cross-tenant repository isolation, RLS default-deny.
  - `test_tenant_isolation.py` (6): two independent tenants, own-tenant access, cross-tenant denial, ID substitution, multi-tenant role independence, members-list exclusion, 20-request concurrent cross-tenant access with no context leakage.
  - `test_error_handling.py` (4, 1 new): Milestone 2 regression coverage plus the custom-validator serialization fix.
  - All Milestone 2 tests (`test_health.py`, `test_readiness.py`, `test_rate_limit_middleware.py`, `test_request_size_limit_middleware.py`, `test_redaction.py`, `test_settings.py`) pass unchanged.
- **Frontend** (`apps/web`, `vitest`): 13 passed, 0 failed, across 3 files (`api-client.test.ts`, `auth-client.test.ts`, `env.test.ts`).

## Static Analysis

- `ruff check` (`services/api/src tests alembic`): passed.
- `ruff format --check`: passed (58 files).
- `mypy --strict` (`services/api/src`, 41 source files): passed, no issues.
- `eslint .` (`apps/web`): passed.
- `prettier --check .` (`apps/web`): passed.
- `tsc --noEmit` (`apps/web`): passed.
- `next build` (`apps/web`): passed.

## Docker / End-to-End Verification

`docker compose up --build -d` (`infrastructure/docker-compose.yml`) built and started `postgres`, `redis`, `object-storage`, `object-storage-init`, a new one-shot `migrate` service, `api`, and `web`; `migrate` applied both Alembic migrations and exited successfully before `api` started, and `api`/`postgres`/`redis`/`object-storage` all reached healthy. Verified against the running stack:

- `GET /healthz` → `200 {"status":"ok"}`; `GET /readyz` → `200`, all three dependencies `ok: true`.
- `python3 -m evalforge_api.dev_seed` (run inside the `api` container) created two tenants (`acme`, `globex`) and three users.
- `POST /auth/login` with valid credentials → `200` with a bearer token; `GET /auth/me` with that token → `200` with the correct principal; without a token → `401`.
- `GET /tenants/{acme_id}/context` and `/members` as the Acme admin → `200`; as the Acme developer, `/context` → `200` but `/members` → `403` (role-gated).
- `GET /tenants/{globex_id}/context` and `/members` as the Acme admin (cross-tenant) → `403` for both, and a random nonexistent tenant ID → the identical `403`, confirming no tenant-existence leak.
- Browser-driven verification of `apps/web`: `http://localhost:3000/login` → submitting valid credentials redirects to `/` showing "Signed in as admin@acme.example" and the caller's tenant list; `document.cookie` is empty on that page (the session cookie is httpOnly); "Sign out" returns to the signed-out view; submitting wrong credentials shows "Invalid email or password." without navigating away.
- API container logs across this entire session were inspected for `password`/`secret`/`jwt_signing_key`/`access_token` — no matches.

## Validation

`make validate` (lint, format-check, typecheck, `pytest`, `vitest`, modularity, forbidden-filenames, markdown-link, dependency-boundary, circular-import, secret-scan) passed in full, including the new `test-services-up` dependency that starts an ephemeral, isolated test-only PostgreSQL (`infrastructure/docker-compose.test.yml`) separate from the `make up` development stack.

## Git

- Commit message: `feat: implement authentication authorization and tenant isolation`
- The commit remains local only; it has not been pushed to `origin/main`. The owner will review this report and authorize the push.

## Scope Confirmation

- Only Milestone 3 (Authentication, Authorization, and Tenant Isolation) was implemented.
- No Milestone 4-or-later product functionality (evaluation-domain persistence, dataset/experiment/evaluator/dashboard workflows) was introduced.
- No secrets were committed; `scripts/validate_no_secrets.py` passed, and every credential used locally or in CI is a synthetic, documented, local/CI-only value (matching the existing Milestone 2 convention in `infrastructure/docker-compose.yml`).
- The repository is ready for owner review.

Related documents: [Roadmap](ROADMAP.md), [Tenancy and Authorization](TENANCY_AND_AUTHORIZATION.md), [Milestone Acceptance](MILESTONE_ACCEPTANCE.md), [Threat Model](THREAT_MODEL.md).
