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

EvalForge is not yet a product with evaluation functionality. This repository currently contains the Milestone 0 workspace skeleton, the Milestone 1 product/architecture/governance contracts, the Milestone 2 engineering and infrastructure foundation, and the Milestone 3 authentication, authorization, and tenant-isolation security boundary. No evaluation-domain functionality (datasets, experiments, evaluators, dashboards) exists yet — that begins in Milestone 4 and later.

## Current Status

- Milestone 0 — Repository and Local Workspace Setup: approved.
- Milestone 1 — Product Charter, Architecture, Governance, and Threat Model: approved.
- Milestone 2 — Engineering and Infrastructure Foundation: approved.
- Milestone 3 — Authentication, Authorization, and Tenant Isolation: implemented, pending owner review.
- Milestones 4–15: not started.

Later milestones must follow the locked roadmap sequentially. No later-milestone functionality may be preimplemented before that milestone is authorized.

The Milestone 1 documentation records the locked Phase 1 engineering foundation: one canonical monorepo using the existing `apps/`, `packages/`, `services/`, `infrastructure/`, `scripts/`, and `tests/` boundaries; modular-monolith architecture; Python 3.13 with FastAPI and OpenAPI for backend APIs; Next.js with TypeScript for the web application; PostgreSQL, Redis, S3-compatible private object storage, OpenTelemetry-compatible telemetry, Docker Compose, GitHub Actions, and a root `make validate` entry point. Milestone 2 implements that foundation: `services/api` (FastAPI, typed settings, structured logging with redaction, standardized error handling, request-size and rate-limit foundations, health/readiness endpoints, PostgreSQL/Redis/object-storage connectivity checks, an Alembic migration baseline), `apps/web` (Next.js/TypeScript shell with a typed API client and environment validation), `infrastructure/docker-compose.yml` (local PostgreSQL, Redis, MinIO, API, and web services), and `scripts/` plus `Makefile`/`make validate`/`.github/workflows/ci.yml` for modularity, dependency-boundary, circular-import, forbidden-filename, markdown-link, and secret-pattern validation. See [Milestone 2 Completion Report](docs/MILESTONE_2_COMPLETION_REPORT.md) for verification evidence.

Milestone 3 implements the security boundary described in [Tenancy and Authorization](docs/TENANCY_AND_AUTHORIZATION.md): self-issued, server-verified JWT bearer authentication (`services/api/src/evalforge_api/security/`); a `users` / `tenants` / `tenant_memberships` identity and tenancy schema with a least-privilege `evalforge_app` database role and PostgreSQL row-level security on `tenant_memberships` (`services/api/alembic/versions/20260815_0002_identity_and_tenancy.py`); a centralized, deny-by-default authorization policy keyed on the fixed Milestone 1 tenant-role set (`services/api/src/evalforge_api/domain/`); `/auth/register`, `/auth/login`, `/auth/me`, `/tenants`, `/tenants/{tenant_id}/context`, and `/tenants/{tenant_id}/members` endpoints; and a minimal Next.js login flow that stores the access token only in an httpOnly cookie and never exposes it to browser JavaScript. See [Milestone 3 Completion Report](docs/MILESTONE_3_COMPLETION_REPORT.md) for verification evidence.

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

`make test` (part of `make validate`) starts a separate, ephemeral test-only PostgreSQL via `infrastructure/docker-compose.test.yml` (`make test-services-up` / `make test-services-down` to manage it directly); it never touches the `make up` development database.

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
- [Architecture Decision Records](docs/adr/README.md)
