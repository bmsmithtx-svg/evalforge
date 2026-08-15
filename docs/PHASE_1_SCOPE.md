# Phase 1 Scope

## Purpose

Phase 1 defines the first complete EvalForge product increment across the locked roadmap from Milestone 0 through Milestone 15. It is intended to produce a demonstrable evaluation, observability, and regression-testing platform for LLM, RAG, tool-using, and agent applications.

Milestone 1 implements only the documentation and governance baseline for that Phase 1 plan.

## Eventually Supported In Phase 1

Phase 1 is planned to support:

- Direct LLM applications, RAG applications, tool-using applications, single-agent systems, and multi-step or multi-agent workflows.
- Model comparisons, prompt comparisons, retrieval comparisons, tool and tool-schema comparisons, workflow and agent-policy comparisons, evaluator comparisons, and pricing and cost comparisons.
- Versioned artifacts for datasets, test cases, prompts, models, retrieval configurations, tools, workflows, evaluators, and pricing.
- Immutable dataset snapshots and immutable completed run snapshots.
- Repeated experiment execution with trace and artifact capture.
- Deterministic, model-based, and human evaluation.
- RAG, grounding, citation, tool-use, agent-trajectory, safety, latency, token, and cost evaluation.
- Comparison, regression detection, and quality gates.
- Dashboards, trace inspection, failure analysis, import, export, APIs, SDKs, background execution, tenant isolation, audit history, and deployment integration.

## Authorized In Milestone 1

Milestone 1 was authorized to create and update only product, architecture, domain, evaluation, governance, security, threat-model, modularity, roadmap, acceptance, and ADR documentation. Milestone 1 is approved; see [Roadmap](ROADMAP.md) and [Milestone 1 Completion Report](MILESTONE_1_COMPLETION_REPORT.md).

## Explicit Milestone 1 Exclusions

Milestone 1 did not authorize:

- Application or library source code.
- Package-manager, workspace, framework, dependency, lockfile, pre-commit, or CI/CD configuration.
- APIs, SDKs, workers, CLIs, dashboards, authentication, tenant isolation, databases, migrations, queues, Docker services, infrastructure, evaluators, trace ingestion, experiments, test data, model integrations, human-review UI, or deployment gates.

## Authorized In Milestone 2

Milestone 2 is authorized, per the Milestone 2 definition in [Roadmap](ROADMAP.md), to create backend, frontend, and infrastructure foundation code and configuration: Python/FastAPI application skeleton, Next.js/TypeScript application shell, package-manager and workspace configuration, local Docker services for PostgreSQL, Redis, and S3-compatible object storage, a foundation-only migration baseline, OpenTelemetry-compatible instrumentation foundation, and engineering-quality tooling (formatting, linting, type checking, tests, CI, modularity and secret-scanning checks, and `make validate`).

## Explicit Milestone 2 Exclusions

Milestone 2 does not authorize authentication implementation, authorization or tenant-isolation implementation, evaluation-domain persistence models, functional experiment execution, ingestion APIs or SDK product behavior, dataset or test-case workflows, evaluator implementations, model judges or human-review workflows, RAG/tool-use/agent/safety/comparison/regression/gate engines, product dashboards, deployment integrations, or any Milestone 3 or later functionality.

## Phase 1 Non-Goals

The Phase 1 product scope excludes:

- General-purpose observability unrelated to AI application evaluation.
- Training-data management or fine-tuning lifecycle management.
- Fully managed SaaS operations, billing, invoicing, and procurement.
- Universal provider coverage.
- Automatic correctness guarantees from model judges.
- Replacing human judgment for high-risk review decisions.
- Cross-tenant data sharing by default.
- Use of production private data in demonstration artifacts.

## Sequential Delivery Requirement

All milestones must be completed and owner-approved in order. Milestone 2 or later work may not begin until Milestone 1 is approved. No later-milestone functionality may be introduced early to prepare the architecture.

## Assumptions And Limitations

- Phase 1 contracts favor replaceable providers and infrastructure without leaving the selected Phase 1 foundation undecided.
- The locked Phase 1 foundation is Python 3.13, FastAPI, OpenAPI, Next.js, TypeScript, PostgreSQL, Redis, S3-compatible private object storage, OpenTelemetry-compatible telemetry, Docker Compose, GitHub Actions, and a root `make validate` entry point beginning in Milestone 2.
- Milestone 1 may document these technology and architecture choices, but implementation work remains prohibited until its assigned milestone is authorized.
- Public repository status requires synthetic or redacted examples and strict avoidance of committed secrets or private evaluation data.

Related documents: [Project Charter](PROJECT_CHARTER.md), [Roadmap](ROADMAP.md), [Architecture](ARCHITECTURE.md), and [Security Baseline](SECURITY_BASELINE.md).
