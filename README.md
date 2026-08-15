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

EvalForge is not yet an operational application. This repository currently contains the Milestone 0 skeleton and Milestone 1 product, architecture, governance, and security contracts only.

## Current Status

- Milestone 0 — Repository and Local Workspace Setup: approved.
- Milestone 1 — Product Charter, Architecture, Governance, and Threat Model: approved.
- Milestone 2 — Engineering and Infrastructure Foundation: in progress.
- Milestones 3–15: not started.

Later milestones must follow the locked roadmap sequentially. No later-milestone functionality may be preimplemented before that milestone is authorized.

The Milestone 1 documentation records the locked Phase 1 engineering foundation: one canonical monorepo using the existing `apps/`, `packages/`, `services/`, `infrastructure/`, `scripts/`, and `tests/` boundaries; modular-monolith architecture; Python 3.13 with FastAPI and OpenAPI for backend APIs; Next.js with TypeScript for the web application; PostgreSQL, Redis, S3-compatible private object storage, OpenTelemetry-compatible telemetry, Docker Compose, GitHub Actions, and a future root `make validate` entry point beginning in Milestone 2. These are documented implementation contracts, not currently implemented runtime components.

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
- [Architecture Decision Records](docs/adr/README.md)
