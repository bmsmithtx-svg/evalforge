# Tenancy And Authorization

## Status

This document defines the conceptual security model. Milestone 3 implements the initial authentication boundary, tenant-membership model, centralized authorization, and database-level tenant isolation described below; see [Implementation Notes (Milestone 3)](#implementation-notes-milestone-3) for how each concept maps to running code. Workspace-scoped authorization, service-identity provisioning workflows, and administrative/emergency access paths remain conceptual until a later milestone implements them.

## Tenant And Workspace Boundaries

Tenant is the primary isolation and ownership boundary. A workspace or project belongs to exactly one tenant. Datasets, experiments, runs, traces, results, artifacts, reviews, gates, imports, exports, audit events, and background work must be tenant-scoped.

Workspace boundaries may further restrict access inside a tenant, but workspace membership cannot grant cross-tenant access.

## User Membership

Users gain access through tenant membership and optional workspace membership. A user identity alone is not enough to authorize resource access. Membership changes must be audited with actor, target user, tenant, workspace when applicable, role change, timestamp, and outcome.

## Role-Based Authorization

Initial role categories for later implementation:

- Tenant administrator: manages tenant settings, membership, and high-risk administrative actions.
- Workspace administrator: manages workspace settings, members, datasets, experiments, and gates within a workspace.
- Evaluation engineer: creates and manages datasets, evaluators, experiments, comparisons, and reports.
- Developer: submits runs and traces, views authorized evidence, and manages target configurations.
- Reviewer: performs assigned human reviews and sees required evidence.
- Read-only observer: views authorized reports and evidence without mutation authority.
- Service identity: performs scoped automated work with explicit permissions.

Permissions must be enforced server-side for every protected command and read.

## Resource Ownership

Datasets, experiments, runs, traces, results, artifacts, reviews, and gates are owned by the tenant and, where applicable, the workspace. The human or service actor that creates a resource is recorded for audit but does not own the data outside the tenant policy.

## Cross-Tenant Access Prohibition

Cross-tenant reads, writes, exports, deletions, reviews, comparisons, gate decisions, and background processing are prohibited unless a future owner-approved policy explicitly creates a controlled administrative support path. UI filtering alone is never authorization.

## Service Identities And Workers

Service identities must have explicit tenant-scoped permissions. Background workers must execute under a service identity and verify that queued work belongs to the tenant and resource scope specified in the command. Queue messages must not be trusted as authorization proof.

## Administrative Access

Administrative access must be least-privilege, audited, and separated from normal user workflows. Administrative operators must not bypass tenant access rules silently. Emergency or support access, if later authorized, must record reason, actor, scope, time, and affected resources.

## Import, Export, And Deletion Authorization

Imports require permission to create or update the target resource. Exports require permission to read every included resource. Deletion requires explicit deletion permission and must respect retention, immutable evidence, audit, legal, and tenant-scoped deletion rules.

## Tenant-Scoped Storage And Persistence

Persistence must make tenant scope explicit in records, indexes, storage paths, object metadata, queue payloads, audit events, and authorization checks. Storage design must prevent accidental resource lookup by global ID without tenant verification.

## Audit Requirements

Authorization denials, membership changes, role changes, imports, exports, deletion requests, administrative actions, gate decisions, gate overrides, reviewer decisions, and service-identity actions must emit audit events.

## Implementation Notes (Milestone 3)

- **Authentication**: `services/api/src/evalforge_api/security/tokens.py` issues and verifies HS256 JWTs signed with a required, fail-closed, minimum-32-character `EVALFORGE_JWT_SIGNING_KEY`. Verification always checks signature, issuer, audience, and expiry (`services/api/src/evalforge_api/security/dependencies.py:get_current_principal`), and re-reads the user's live status from the database on every request rather than trusting a claim, so a disabled account loses access immediately instead of at token expiry. `services/api/src/evalforge_api/routes/auth.py` exposes `POST /auth/register`, `POST /auth/login`, and `GET /auth/me`.
- **Identity**: the `users` table (migration `20260815_0002_identity_and_tenancy.py`) keys on an application-generated UUID, independent of the `auth_provider` / `provider_subject` columns that will carry external-identity mappings when a later milestone adds a non-local provider — no tenant-owned data needs to be re-keyed when that happens. A `kind` column (`human` / `service`) is the foundation for the service-identity concept above; provisioning workflows for service identities remain a later milestone.
- **Tenant and membership model**: `tenants` and `tenant_memberships` tables implement the tenant and membership contracts above. `tenant_memberships` enforces `UNIQUE (user_id, tenant_id)` and foreign keys to both parents, so a membership can only reference a real user and a real tenant and a user cannot hold two roles in the same tenant.
- **Roles**: `services/api/src/evalforge_api/domain/enums.py:TenantRole` implements the tenant-level role set fixed above (workspace administrator and service identity are excluded because no workspace entity exists yet and service identities are not tenant-membership roles).
- **Authorization**: `services/api/src/evalforge_api/domain/actions.py` is the single, deny-by-default permission table every route consults (via `TenantContext.can()`) instead of comparing role strings inline.
- **Tenant context**: `services/api/src/evalforge_api/security/dependencies.py:get_tenant_context` independently verifies an active membership for the path's tenant ID before constructing a `TenantContext`; a client-supplied tenant ID is only ever a request, never a grant.
- **Database isolation**: `tenant_memberships` carries PostgreSQL row-level security (`ENABLE`/`FORCE ROW LEVEL SECURITY`), and the running API connects as a separate, non-superuser `evalforge_app` role with only `SELECT`/`INSERT` grants — the migration/admin role is never used for request-serving queries — so RLS policies actually apply rather than being bypassed by table ownership. See `services/api/src/evalforge_api/adapters/membership_repository.py`.
- **Frontend**: `apps/web` stores the access token only in an httpOnly cookie (`apps/web/src/lib/actions/auth-actions.ts`), never in browser-readable storage; server-rendered pages revalidate the session against `GET /auth/me` on every request rather than trusting the cookie's presence.

Related documents: [Domain Model](DOMAIN_MODEL.md), [Trust Boundaries](TRUST_BOUNDARIES.md), [Security Baseline](SECURITY_BASELINE.md), ADR [0004](adr/0004-tenant-isolation-and-data-ownership.md), and the [Milestone 3 Completion Report](MILESTONE_3_COMPLETION_REPORT.md).
