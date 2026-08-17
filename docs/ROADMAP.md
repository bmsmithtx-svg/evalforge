# EvalForge Roadmap

## Locked Order And Status

The EvalForge roadmap contains exactly Milestones 0 through 15 in the order below. Milestone order may change only through an explicit owner-approved formal roadmap amendment.

| Milestone | Title | Status |
| --- | --- | --- |
| 0 | Repository and Local Workspace Setup | Approved |
| 1 | Product Charter, Architecture, Governance, and Threat Model | Approved |
| 2 | Engineering and Infrastructure Foundation | Approved |
| 3 | Authentication, Authorization, and Tenant Isolation | Approved |
| 4 | Versioned Evaluation Domain and Persistence | Approved |
| 5 | SDK, API, Trace, and Run Ingestion | Approved |
| 6 | Dataset and Test-Case Management | Implemented and validated; pending owner review |
| 7 | Experiment Execution and Reproducibility Engine | Not started |
| 8 | Deterministic Evaluation Framework | Not started |
| 9 | Model-Based and Human Evaluation | Not started |
| 10 | RAG, Grounding, and Citation Evaluation | Not started |
| 11 | Tool-Use, Agent-Trajectory, and Safety Evaluation | Not started |
| 12 | Metrics, Comparison, Regression, and Quality-Gate Engine | Not started |
| 13 | Dashboard, Trace Inspection, and Failure Analysis | Not started |
| 14 | CI/CD, Integrations, and Deployment Gates | Not started |
| 15 | Production Hardening, Demonstration, Documentation, and Final Acceptance | Not started |

## Milestone 0 — Repository and Local Workspace Setup

Status: Approved.

Objective: Establish the public EvalForge repository and local workspace skeleton.

Major deliverables: Repository identity, branch and remote setup, README seed, directory skeleton, and placeholder files.

Explicit exclusions: Product implementation, dependencies, runtime configuration, application code, infrastructure, CI/CD, and detailed contracts.

Measurable acceptance criteria: Repository exists at the canonical remote, local workspace resolves to the canonical path, `main` is active, working tree is clean, and the approved commit is recorded.

Dependencies on prior milestones: None.

## Milestone 1 — Product Charter, Architecture, Governance, and Threat Model

Status: Approved. Owner approval recorded 2026-08-14; see [Milestone 1 Completion Report](MILESTONE_1_COMPLETION_REPORT.md).

Objective: Establish authoritative product, architecture, evaluation, security, governance, tenancy, reproducibility, and modularity contracts for later milestones.

Major deliverables: README update, product charter, Phase 1 scope, requirements, roadmap, architecture, domain model, evaluation taxonomy, metric definitions, reproducibility contract, tenancy and authorization contract, data governance, human review policy, security baseline, trust boundaries, threat model, modularity standard, milestone acceptance policy, and ADRs 0001 through 0006.

Explicit exclusions: All application code, runtime dependencies, package-manager configuration, databases, migrations, Docker services, CI/CD workflows, APIs, workers, SDKs, evaluators, dashboards, authentication implementation, tenant-isolation implementation, infrastructure implementation, and Milestone 2 or later functionality.

Measurable acceptance criteria: Required documents exist, `docs/.gitkeep` is removed, links resolve, roadmap status is correct, required metrics and threats are documented, modularity rules contain the approved 300-line threshold, validation passes, staged diff is limited to Milestone 1 documentation, and the owner reviews the milestone.

Dependencies on prior milestones: Milestone 0 approved.

## Milestone 2 — Engineering and Infrastructure Foundation

Status: Approved. Authorized by owner 2026-08-14 following Milestone 1 approval; implementation completed and validated 2026-08-15; owner approval recorded 2026-08-15. See [Milestone 2 Completion Report](MILESTONE_2_COMPLETION_REPORT.md).

Objective: Establish the engineering and infrastructure foundation authorized after Milestone 1 approval.

Major deliverables:

- Backend foundation: Python 3.13 project and dependency configuration; FastAPI application factory; typed settings and environment validation; fail-closed validation for missing or invalid sensitive configuration; structured logging with secret and sensitive-field redaction; health and readiness endpoints; standardized error-response boundary; baseline request-size limits and rate-limiting or backpressure foundations for public endpoints; dependency-injection and adapter boundaries; OpenAPI generation and validation; and no product-domain API behavior beyond foundation-level health, readiness, metadata, and connectivity verification.
- Frontend foundation: Next.js and TypeScript workspace; basic application shell only; shared design primitives sufficient for later product work; typed API-client boundary; frontend environment validation; verified frontend-to-API connectivity; and no experiment, dataset, trace, evaluator, review, comparison, or dashboard product workflows.
- Infrastructure foundation: PostgreSQL local service and connectivity checks; Redis local service and connectivity checks; S3-compatible local object-storage service and connectivity checks; migration framework with an empty or foundation-only migration baseline; Dockerfiles and Docker Compose local-development stack; reproducible local setup and teardown commands; isolated test configuration that does not require production data or production credentials; and OpenTelemetry-compatible service instrumentation foundation.
- Engineering quality: formatting and linting; static type checking; unit and foundation integration tests; coverage configuration; pre-commit hooks; GitHub Actions CI; dependency and vulnerability scanning; secret scanning and hygiene validation; Markdown-link validation; automated modularity, forbidden-filename, dependency-boundary, and circular-import checks; and a root `Makefile` with `make validate` as the authoritative validation entry point.

Explicit exclusions: Authentication implementation; authorization and tenant-isolation implementation; tenant and evaluation-domain persistence models; functional experiment execution; ingestion APIs and SDK product behavior; dataset and test-case workflows; evaluator implementations; model judges and human-review workflows; RAG, tool-use, agent, safety, comparison, regression, or gate engines; product dashboards; deployment integrations; and all Milestone 3–15 functionality.

Measurable acceptance criteria: A clean clone can install the documented toolchain; the documented local-development stack starts successfully; API health and readiness checks pass; the frontend can reach the API; PostgreSQL, Redis, and object-storage connectivity are verified; invalid sensitive configuration fails closed; logs and error responses do not expose configured secrets; baseline request-size limits and rate-limiting or backpressure foundations are demonstrably active on public endpoints; tests run without production data or live production services; `make validate` performs the complete required validation suite; CI passes from a clean checkout; every modularity violation is reported with its path and physical line count; and no unauthorized Milestone 3 or later product functionality is introduced.

Dependencies on prior milestones: Milestones 0 and 1 approved.

## Milestone 3 — Authentication, Authorization, and Tenant Isolation

Status: Approved. Implementation completed and validated 2026-08-15; owner approval recorded 2026-08-15. See [Milestone 3 Completion Report](MILESTONE_3_COMPLETION_REPORT.md).

Objective: Implement the initial security model for users, service identities, roles, permissions, and tenant-scoped enforcement.

Major deliverables: Authentication integration, authorization policy enforcement, tenant membership model, service identity controls, and audit evidence for protected operations.

Explicit exclusions: Full evaluation domain, experiment execution, dashboards beyond security workflows, CI/CD deployment gates, and later evaluator functionality.

Measurable acceptance criteria: Server-side authorization is enforced for protected resources, cross-tenant access is rejected, audit events are emitted, and UI filtering is not treated as authorization.

Dependencies on prior milestones: Milestones 0–2 approved.

## Milestone 4 — Versioned Evaluation Domain and Persistence

Status: Approved. Implementation completed and validated 2026-08-15; owner approval recorded 2026-08-15. See [Milestone 4 Completion Report](MILESTONE_4_COMPLETION_REPORT.md).

Objective: Implement persistent versioned domain concepts for evaluation artifacts and immutable snapshots.

Major deliverables: Domain entities, persistence mappings, dataset snapshots, artifact versioning, lineage, hashing, retention metadata, and audit hooks.

Explicit exclusions: SDKs, trace ingestion, experiment execution engine, evaluator implementations, dashboards, integrations, and deployment gates.

Measurable acceptance criteria: Versioned artifacts and immutable snapshots obey the domain model, tenant isolation applies to persistence, and completed immutable records cannot be modified through supported paths.

Dependencies on prior milestones: Milestones 0–3 approved.

## Milestone 5 — SDK, API, Trace, and Run Ingestion

Status: Approved. Implementation completed and validated 2026-08-15; owner approval recorded 2026-08-17. See [Milestone 5 Completion Report](MILESTONE_5_COMPLETION_REPORT.md).

Objective: Implement controlled ingestion paths for runs, traces, spans, and artifacts through APIs and SDK contracts.

Major deliverables: Public ingestion APIs, SDK surface, canonical trace and span mapping, artifact upload controls, validation, idempotency, and audit events.

Explicit exclusions: Dataset authoring workflows, full experiment execution, evaluator engines, human review, dashboards beyond ingestion inspection, and deployment gates.

Measurable acceptance criteria: Authorized ingestion creates tenant-scoped traces and runs, malformed input is rejected, duplicate submissions are idempotent, and trace data links to versioned artifacts.

Dependencies on prior milestones: Milestones 0–4 approved.

## Milestone 6 — Dataset and Test-Case Management

Status: Implemented and validated 2026-08-17; owner review pending. See [Milestone 6 Completion Report](MILESTONE_6_COMPLETION_REPORT.md).

Objective: Implement dataset and test-case authoring, import, export, versioning, and snapshot workflows.

Major deliverables: Dataset management UI or API, test-case CRUD within authorization boundaries, import and export, snapshot creation, validation, and retention metadata.

Explicit exclusions: Full experiment execution, evaluator implementations, model judges, human-review adjudication, dashboards beyond dataset workflows, and deployment gates.

Measurable acceptance criteria: Datasets and test cases are versioned, snapshots are immutable, tenant-scoped imports and exports are authorized, and audit history records material changes.

Dependencies on prior milestones: Milestones 0–5 approved.

## Milestone 7 — Experiment Execution and Reproducibility Engine

Status: Not started.

Objective: Implement durable experiment execution with reproducible run metadata and repeated-run support.

Major deliverables: Experiment definitions, variants, run scheduling, attempts, repetition indexes, durable state transitions, retry and cancellation behavior, and completed-run immutability.

Explicit exclusions: Deterministic evaluator library, model-based evaluation, human review, RAG-specific metrics, tool-use metrics, dashboards beyond execution state, and deployment gates.

Measurable acceptance criteria: Experiments execute asynchronously with captured reproducibility metadata, retries are idempotent, completed runs are immutable, and failures preserve diagnostic evidence.

Dependencies on prior milestones: Milestones 0–6 approved.

## Milestone 8 — Deterministic Evaluation Framework

Status: Not started.

Objective: Implement deterministic evaluator contracts and initial deterministic metrics.

Major deliverables: Evaluator interfaces, exact and normalized matching, schema validation, rule-based checks, reference scoring, aggregation, and test coverage for deterministic behavior.

Explicit exclusions: Model judges, human-review workflows, RAG-specific advanced evaluation, agent trajectory evaluation, dashboards beyond deterministic results, and deployment gates.

Measurable acceptance criteria: Deterministic evaluators are versioned, repeatable, isolated from model judges, and produce auditable metric observations and scores.

Dependencies on prior milestones: Milestones 0–7 approved.

## Milestone 9 — Model-Based and Human Evaluation

Status: Not started.

Objective: Implement model-judge and human-review workflows under evaluator isolation and review policy.

Major deliverables: LLM-as-judge evaluator contracts, judge versioning, calibration evidence, rubric review, reviewer assignment, adjudication, inter-rater agreement, and audit history.

Explicit exclusions: RAG-specific grounding metrics, tool-use and agent-trajectory evaluation, deployment gates, and final production hardening.

Measurable acceptance criteria: Model judges are versioned and bounded by policy, human decisions are auditable, disagreements can be adjudicated, and model output is not used as authorization policy.

Dependencies on prior milestones: Milestones 0–8 approved.

## Milestone 10 — RAG, Grounding, and Citation Evaluation

Status: Not started.

Objective: Implement retrieval, grounding, faithfulness, and citation evaluation for RAG workflows.

Major deliverables: Retrieval metrics, citation presence and validity checks, entailment and completeness metrics, groundedness, faithfulness, context relevance, and RAG failure analysis support.

Explicit exclusions: Tool-use and agent-trajectory evaluation, deployment integration gates, and final hardening.

Measurable acceptance criteria: RAG evaluations link answers to retrieved context and citations, document limitations, and support aggregate and per-test-case analysis.

Dependencies on prior milestones: Milestones 0–9 approved.

## Milestone 11 — Tool-Use, Agent-Trajectory, and Safety Evaluation

Status: Not started.

Objective: Implement evaluation for tool selection, tool arguments, tool-call sequences, agent trajectories, and safety policy behavior.

Major deliverables: Tool-use metrics, trajectory success criteria, step-efficiency metrics, policy compliance checks, safety violation detection, refusal appropriateness, and trace-level diagnostics.

Explicit exclusions: Deployment integration gates and final production hardening.

Measurable acceptance criteria: Tool and agent evaluations use versioned tool and workflow definitions, preserve evidence, distinguish safety decisions from model output, and support regression analysis.

Dependencies on prior milestones: Milestones 0–10 approved.

## Milestone 12 — Metrics, Comparison, Regression, and Quality-Gate Engine

Status: Not started.

Objective: Implement aggregate metrics, comparison workflows, regression findings, and quality gates.

Major deliverables: Metric aggregation, slices, confidence intervals where applicable, baseline comparison, regression magnitude, pass and error rates, gate criteria, gate decisions, and override audit.

Explicit exclusions: CI/CD integration wiring, production deployment gates, and final hardening.

Measurable acceptance criteria: Quality gates are deterministic over stored inputs where applicable, decisions are auditable, overrides are authorized, and regression findings link to evidence.

Dependencies on prior milestones: Milestones 0–11 approved.

## Milestone 13 — Dashboard, Trace Inspection, and Failure Analysis

Status: Not started.

Objective: Implement user-facing workflows for dashboards, trace inspection, review queues, comparison, and failure analysis.

Major deliverables: Dashboard views, run and experiment inspection, trace and span drilldown, failure grouping, evaluator output review, human review workflows, and accessible UX states.

Explicit exclusions: CI/CD integration, deployment gate wiring, and final production hardening.

Measurable acceptance criteria: Users can navigate from aggregate results to evidence, inspect failures without cross-tenant leakage, and complete review workflows with audit history.

Dependencies on prior milestones: Milestones 0–12 approved.

## Milestone 14 — CI/CD, Integrations, and Deployment Gates

Status: Not started.

Objective: Connect EvalForge results and quality gates to development and deployment workflows.

Major deliverables: CI/CD integration contracts, deployment gate checks, webhook verification, import and export integrations, status reporting, and authorized gate override paths.

Explicit exclusions: Final hardening activities reserved for Milestone 15.

Measurable acceptance criteria: Integrations verify callbacks, gate decisions are reproducible and auditable, unauthorized overrides fail, and deployment status reflects stored quality evidence.

Dependencies on prior milestones: Milestones 0–13 approved.

## Milestone 15 — Production Hardening, Demonstration, Documentation, and Final Acceptance

Status: Not started.

Objective: Harden, demonstrate, document, and complete final Phase 1 acceptance.

Major deliverables: Security review, performance and recovery validation, demonstration data, final documentation, operational checks, accessibility review, and acceptance evidence.

Explicit exclusions: New product scope not already authorized by the roadmap.

Measurable acceptance criteria: All prior milestone evidence is complete, validation passes without unresolved failures, demonstration uses synthetic or redacted data, production hardening controls are documented, and the owner grants final acceptance.

Dependencies on prior milestones: Milestones 0–14 approved.
