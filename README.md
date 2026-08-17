# EvalForge

EvalForge is an evaluation, observability, and regression-testing platform for LLM, RAG, tool-using, and agent applications.

EvalForge is intended for AI engineers, evaluation engineers, ML platform engineers, application developers, security reviewers, and technical product teams that need reproducible evidence about model and application quality.

## Planned Phase 1 Capabilities

Phase 1 is planned to establish:

- Versioned datasets, test cases, prompts, models, retrieval configurations, tool definitions, workflows, evaluators, and pricing definitions.
- Immutable dataset snapshots and completed run snapshots for reproducibility.
- Repeated experiment runs across model, prompt, retrieval, tool, workflow, evaluator, and cost variants.
- Canonical traces and spans for LLM, RAG, tool-use, and agent workflows.
- Deterministic, model-based, and human evaluation results.
- Comparison, regression, quality-gate, review, import, export, and failure-analysis workflows.
- Authentication, tenant isolation, audit history, and security controls in later milestones.

EvalForge is not yet a product with evaluation functionality. This repository currently contains the Milestone 0 workspace skeleton, the Milestone 1 product/architecture/governance contracts, the Milestone 2 engineering and infrastructure foundation, the Milestone 3 authentication, authorization, and tenant-isolation security boundary, the Milestone 4 versioned evaluation domain and persistence layer, the Milestone 5 SDK, API, trace, and run ingestion boundary, and the Milestone 6 dataset and test-case management API. No experiment execution, evaluators, or dashboards exist yet — that begins in Milestone 7 and later.

## Current Status

- Milestone 0 — Repository and Local Workspace Setup: approved.
- Milestone 1 — Product Charter, Architecture, Governance, and Threat Model: approved.
- Milestone 2 — Engineering and Infrastructure Foundation: approved.
- Milestone 3 — Authentication, Authorization, and Tenant Isolation: approved.
- Milestone 4 — Versioned Evaluation Domain and Persistence: approved.
- Milestone 5 — SDK, API, Trace, and Run Ingestion: approved.
- Milestone 6 — Dataset and Test-Case Management: implemented and validated, pending owner review.
- Milestones 7–15: not started.

Later milestones must follow the locked roadmap sequentially. No later-milestone functionality may be preimplemented before that milestone is authorized.

The Milestone 1 documentation records the locked Phase 1 engineering foundation: one canonical monorepo using the existing `apps/`, `packages/`, `services/`, `infrastructure/`, `scripts/`, and `tests/` boundaries; modular-monolith architecture; Python 3.13 with FastAPI and OpenAPI for backend APIs; Next.js with TypeScript for the web application; PostgreSQL, Redis, S3-compatible private object storage, OpenTelemetry-compatible telemetry, Docker Compose, GitHub Actions, and a root `make validate` entry point. Milestone 2 implements that foundation: `services/api` (FastAPI, typed settings, structured logging with redaction, standardized error handling, request-size and rate-limit foundations, health/readiness endpoints, PostgreSQL/Redis/object-storage connectivity checks, an Alembic migration baseline), `apps/web` (Next.js/TypeScript shell with a typed API client and environment validation), `infrastructure/docker-compose.yml` (local PostgreSQL, Redis, MinIO, API, and web services), and `scripts/` plus `Makefile`/`make validate`/`.github/workflows/ci.yml` for modularity, dependency-boundary, circular-import, forbidden-filename, markdown-link, and secret-pattern validation. See [Milestone 2 Completion Report](docs/MILESTONE_2_COMPLETION_REPORT.md) for verification evidence.

Milestone 3 implements the security boundary described in [Tenancy and Authorization](docs/TENANCY_AND_AUTHORIZATION.md): self-issued, server-verified JWT bearer authentication (`services/api/src/evalforge_api/security/`); a `users` / `tenants` / `tenant_memberships` identity and tenancy schema with a least-privilege `evalforge_app` database role and PostgreSQL row-level security on `tenant_memberships` (`services/api/alembic/versions/20260815_0002_identity_and_tenancy.py`); a centralized, deny-by-default authorization policy keyed on the fixed Milestone 1 tenant-role set (`services/api/src/evalforge_api/domain/`); `/auth/register`, `/auth/login`, `/auth/me`, `/tenants`, `/tenants/{tenant_id}/context`, and `/tenants/{tenant_id}/members` endpoints; and a minimal Next.js login flow that stores the access token only in an httpOnly cookie and never exposes it to browser JavaScript. See [Milestone 3 Completion Report](docs/MILESTONE_3_COMPLETION_REPORT.md) for verification evidence.

Milestone 4 implements the persistence substrate described in [Domain Model](docs/DOMAIN_MODEL.md) and [Reproducibility Contract](docs/REPRODUCIBILITY_CONTRACT.md): tenant-scoped workspaces and evaluation targets; a unified versioned-resource mechanism covering model, prompt, retrieval, tool, workflow, evaluator, and pricing versions; versioned test cases and immutable, hash-verified dataset snapshots; artifact metadata with tenant-scoped S3-compatible object storage; and explicit relational lineage throughout (`services/api/src/evalforge_api/domain/`, `ports/`, `adapters/`, `application/`; migrations `services/api/alembic/versions/20260815_0003_*` through `0005_*`). Every new table carries PostgreSQL row-level security and composite tenant-consistent foreign keys, and finalized snapshots and version rows are immutable by database trigger and privilege grant, not application convention alone. No new public API routes were added — Milestone 4 is proved through internal application services and tests, per the milestone's own scope guidance. See [Milestone 4 Completion Report](docs/MILESTONE_4_COMPLETION_REPORT.md) for verification evidence.

Milestone 5 implements the controlled ingestion boundary described in this document's roadmap entry: authenticated, tenant-isolated public APIs for runs, canonical traces and spans, and artifact evidence (`services/api/src/evalforge_api/routes/ingestion_*.py`, `application/{run,trace,span,evidence_artifact,artifact_ingestion}_service.py`; migrations `services/api/alembic/versions/20260815_0006_*` through `0008_*`), a Python SDK (`packages/evalforge-sdk`), and durable, database-enforced idempotency for every ingestion write. Runs and traces are immutable once finalized, spans may only be appended while their trace is still accepting evidence, and every optional lineage or artifact reference is independently re-verified against the requesting tenant before being persisted. See [Milestone 5 Completion Report](docs/MILESTONE_5_COMPLETION_REPORT.md) for verification evidence.

Milestone 6 turns the Milestone 4 dataset/test-case/snapshot persistence into a managed, auditable, tenant-isolated public API (`services/api/src/evalforge_api/routes/{datasets,test_cases,dataset_snapshots,dataset_import_export,dataset_operations}.py`; migration `services/api/alembic/versions/20260817_0009_*`): dataset and test-case lifecycle management, a typed and validated test-case content schema, CSV/JSONL import with atomic all-or-nothing semantics, JSONL/CSV export, deterministic structural duplicate detection, dataset cloning with provenance, and deterministic sampling/splitting over finalized snapshots — reusing Milestone 4's versioning and immutable-snapshot mechanism unchanged. See [Milestone 6 Completion Report](docs/MILESTONE_6_COMPLETION_REPORT.md) for verification evidence.

## Local Development

Requires Python 3.13, Node.js 20+, and Docker with Compose.

```bash
make up        # start PostgreSQL, Redis, MinIO, API, and web via Docker Compose
                # (a one-shot "migrate" service applies Alembic migrations first)
make validate  # lint, type-check, test, and run foundation checks
make down      # stop and remove the local stack
```

The API serves `http://localhost:8000` (`/healthz`, `/readyz`, `/docs`) and the web app serves `http://localhost:3000`. Copy `services/api/.env.example` and `apps/web/.env.example` to `.env` files if running either service outside Docker Compose.

To exercise authentication and tenant isolation locally, seed two example tenants and three example users (never valid outside the local stack):

```bash
cd infrastructure && docker compose exec api python3 -m evalforge_api.dev_seed
```

Then sign in at `http://localhost:3000/login` with one of the printed accounts, or call the API directly: `POST /auth/register`, `POST /auth/login`, `GET /auth/me`, `GET /tenants`, `GET /tenants/{tenant_id}/context`, `GET /tenants/{tenant_id}/members`. See [Tenancy and Authorization](docs/TENANCY_AND_AUTHORIZATION.md) for the identity, role, and isolation model, and `services/api/tests/test_tenant_isolation.py` for cross-tenant-denial examples.

With that bearer token, ingest execution evidence: `POST /tenants/{tenant_id}/runs`, `POST /tenants/{tenant_id}/traces`, `POST /tenants/{tenant_id}/traces/{trace_id}/spans`, and `POST /tenants/{tenant_id}/artifacts` (multipart upload) each require an `Idempotency-Key` header. The Python SDK (`packages/evalforge-sdk`) wraps these calls — see [Milestone 5 Completion Report](docs/MILESTONE_5_COMPLETION_REPORT.md) for the full endpoint list, idempotency semantics, and SDK usage.

`make test` (part of `make validate`) starts a separate, ephemeral test-only PostgreSQL and MinIO via `infrastructure/docker-compose.test.yml` (`make test-services-up` / `make test-services-down` to manage them directly); it never touches the `make up` development database or object storage.

## Authoritative Documents

- [Project Charter](docs/PROJECT_CHARTER.md)
- [Phase 1 Scope](docs/PHASE_1_SCOPE.md)
- [Product Requirements](docs/PRODUCT_REQUIREMENTS.md)
- [Roadmap](docs/ROADMAP.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Domain Model](docs/DOMAIN_MODEL.md)
- [Evaluation Taxonomy](docs/EVALUATION_TAXONOMY.md)
- [Metric Definitions](docs/METRIC_DEFINITIONS.md)
- [Reproducibility Contract](docs/REPRODUCIBILITY_CONTRACT.md)
- [Tenancy and Authorization](docs/TENANCY_AND_AUTHORIZATION.md)
- [Data Governance](docs/DATA_GOVERNANCE.md)
- [Human Review Policy](docs/HUMAN_REVIEW_POLICY.md)
- [Security Baseline](docs/SECURITY_BASELINE.md)
- [Trust Boundaries](docs/TRUST_BOUNDARIES.md)
- [Threat Model](docs/THREAT_MODEL.md)
- [Modularity Standard](docs/MODULARITY_STANDARD.md)
- [Milestone Acceptance](docs/MILESTONE_ACCEPTANCE.md)
- [Milestone 1 Completion Report](docs/MILESTONE_1_COMPLETION_REPORT.md)
- [Milestone 2 Completion Report](docs/MILESTONE_2_COMPLETION_REPORT.md)
- [Milestone 3 Completion Report](docs/MILESTONE_3_COMPLETION_REPORT.md)
- [Milestone 4 Completion Report](docs/MILESTONE_4_COMPLETION_REPORT.md)
- [Milestone 5 Completion Report](docs/MILESTONE_5_COMPLETION_REPORT.md)
- [Milestone 6 Completion Report](docs/MILESTONE_6_COMPLETION_REPORT.md)
- [Architecture Decision Records](docs/adr/README.md)
