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

Milestone 1 is authorized to create and update only product, architecture, domain, evaluation, governance, security, threat-model, modularity, roadmap, acceptance, and ADR documentation. The current milestone may describe future runtime behavior as requirements or contracts. It must not claim those capabilities currently exist.

## Explicit Milestone 1 Exclusions

Milestone 1 does not authorize:

- Application or library source code.
- Package-manager, workspace, framework, dependency, lockfile, pre-commit, or CI/CD configuration.
- APIs, SDKs, workers, CLIs, dashboards, authentication, tenant isolation, databases, migrations, queues, Docker services, infrastructure, evaluators, trace ingestion, experiments, test data, model integrations, human-review UI, or deployment gates.

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
