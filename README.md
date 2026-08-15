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

EvalForge is not yet a product with evaluation functionality. This repository currently contains the Milestone 0 workspace skeleton, the Milestone 1 product/architecture/governance contracts, and the Milestone 2 engineering and infrastructure foundation: a FastAPI control/API service, a Next.js web application shell, and a local PostgreSQL/Redis/S3-compatible development stack. No product-domain functionality (datasets, experiments, evaluators, dashboards, authentication, tenant isolation) exists yet — that begins in Milestone 3 and later.

## Current Status

- Milestone 0 — Repository and Local Workspace Setup: approved.
- Milestone 1 — Product Charter, Architecture, Governance, and Threat Model: approved.
- Milestone 2 — Engineering and Infrastructure Foundation: approved.
- Milestones 3–15: not started.

Later milestones must follow the locked roadmap sequentially. No later-milestone functionality may be preimplemented before that milestone is authorized.

The Milestone 1 documentation records the locked Phase 1 engineering foundation: one canonical monorepo using the existing `apps/`, `packages/`, `services/`, `infrastructure/`, `scripts/`, and `tests/` boundaries; modular-monolith architecture; Python 3.13 with FastAPI and OpenAPI for backend APIs; Next.js with TypeScript for the web application; PostgreSQL, Redis, S3-compatible private object storage, OpenTelemetry-compatible telemetry, Docker Compose, GitHub Actions, and a root `make validate` entry point. Milestone 2 implements that foundation: `services/api` (FastAPI, typed settings, structured logging with redaction, standardized error handling, request-size and rate-limit foundations, health/readiness endpoints, PostgreSQL/Redis/object-storage connectivity checks, an Alembic migration baseline), `apps/web` (Next.js/TypeScript shell with a typed API client and environment validation), `infrastructure/docker-compose.yml` (local PostgreSQL, Redis, MinIO, API, and web services), and `scripts/` plus `Makefile`/`make validate`/`.github/workflows/ci.yml` for modularity, dependency-boundary, circular-import, forbidden-filename, markdown-link, and secret-pattern validation. See [Milestone 2 Completion Report](docs/MILESTONE_2_COMPLETION_REPORT.md) for verification evidence.

## Local Development

Requires Python 3.13, Node.js 20+, and Docker with Compose.

```bash
make up        # start PostgreSQL, Redis, MinIO, API, and web via Docker Compose
make validate  # lint, type-check, test, and run foundation checks
make down      # stop and remove the local stack
```

The API serves `http://localhost:8000` (`/healthz`, `/readyz`, `/docs`) and the web app serves `http://localhost:3000`. Copy `services/api/.env.example` and `apps/web/.env.example` to `.env` files if running either service outside Docker Compose.

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
- [Architecture Decision Records](docs/adr/README.md)
