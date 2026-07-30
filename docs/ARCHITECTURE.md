# Architecture

## Status

This document defines the locked EvalForge Phase 1 architecture and selected engineering foundation for later milestones. It does not add implementation files, configure dependencies, provision infrastructure, or claim that any runtime component currently exists.

Milestone 1 may document the required implementation stack for later milestones. Implementing that stack begins only when its assigned milestone is authorized.

## System Context

EvalForge will sit between teams that build AI applications and the systems those applications depend on. It will ingest datasets, experiment definitions, traces, artifacts, evaluation results, and human-review decisions; execute or coordinate evaluation work; and present reproducible quality, safety, latency, and cost evidence.

External systems may include model providers, embedding providers, retrieval stores, target applications, CI/CD systems, authentication providers, object storage, queue or coordination systems, observability tools, and human reviewers.

## Locked Phase 1 Engineering Foundation

EvalForge Phase 1 will use one canonical monorepo with the existing `apps/`, `packages/`, `services/`, `infrastructure/`, `scripts/`, and `tests/` boundaries. The implementation approach is a modular monolith: separately testable modules share one repository and one coordinated validation surface while preserving explicit domain, application, delivery, evaluator, persistence, provider-adapter, and infrastructure boundaries.

The selected Phase 1 foundation is:

- Python 3.13 for backend services, workers, evaluation code, automation, and the later Python SDK.
- FastAPI for the backend HTTP API boundary.
- OpenAPI as the machine-readable API-contract foundation.
- Next.js with TypeScript for the user-facing web application.
- PostgreSQL as the primary relational persistence foundation.
- Redis as the Phase 1 local foundation for bounded queueing, coordination, or ephemeral infrastructure responsibilities.
- S3-compatible private object storage for datasets, traces, run artifacts, exports, and other binary or large artifacts.
- OpenTelemetry-compatible operational telemetry and trace interoperability.
- Docker and Docker Compose for the reproducible local development stack.
- GitHub Actions for repository CI.
- A root Makefile with `make validate` as the authoritative local and CI validation entry point beginning in Milestone 2.

These choices do not select a commercial model provider, embedding provider, authentication provider, deployment cloud, Kubernetes, Supabase, DBOS, or a higher-level workflow engine. Provider adapters and ports must preserve replaceability without pretending that the selected Phase 1 implementation stack is undecided.

## Primary Actors

- Authenticated users: engineers, reviewers, product stakeholders, and administrators.
- Service identities: workers, SDK clients, ingestion clients, CI systems, and integration services.
- External providers: model, embedding, authentication, storage, queue or coordination, workflow where later authorized, and trace sources.
- Administrative operators: limited users with elevated operational responsibilities.

## Major Trust Boundaries

Detailed trust-boundary requirements are defined in [Trust Boundaries](TRUST_BOUNDARIES.md). Primary boundaries include browser clients, public APIs, authentication provider, FastAPI control/API process, later workers, Redis-backed queue or coordination responsibilities, PostgreSQL, S3-compatible object storage, model and embedding providers, external target applications, trace ingestion sources, tool-execution environments, human reviewers, CI systems, deployment systems, and administrative operators.

## Initial Runtime And Deployment Topology

When implemented in authorized later milestones, the initial topology must separate:

- Next.js user-facing application for dashboards, trace inspection, experiment management, and review workflows.
- FastAPI control/API process for authenticated application operations, ingestion boundaries, artifact metadata, quality-gate decisions, and administrative actions.
- Later background execution processes for experiments, evaluations, imports, exports, comparison, regression analysis, and gates.
- PostgreSQL for tenant-scoped relational state, immutable snapshot metadata, run state, audit event indexes, and transactional coordination.
- Redis for bounded queueing, coordination, cache, rate-limiting, lock, or other ephemeral infrastructure responsibilities approved in implementation milestones.
- S3-compatible private object storage for datasets, traces, run artifacts, exports, and binary or large artifacts.
- External model, embedding, authentication, target application, CI/CD, deployment, and trace-ingestion providers behind adapters.
- OpenTelemetry-compatible telemetry collection and export boundaries.

These containers and services are planned contracts, not current implementation.

## Monorepo Directory Responsibilities

| Directory | Responsibility |
| --- | --- |
| `apps/` | Next.js and TypeScript user-facing applications and delivery-specific UI code introduced in later milestones. |
| `packages/` | Shared domain contracts, application services, evaluator interfaces, SDK packages, provider-neutral utilities, OpenAPI-derived clients where authorized, and reusable policies introduced in later milestones. |
| `services/` | Python 3.13 FastAPI control/API services, ingestion boundaries, and background worker processes introduced in later milestones. |
| `infrastructure/` | Deployment, provisioning, environment, and operational infrastructure introduced only when authorized. |
| `scripts/` | Local validation, maintenance, repository automation, and future `make validate` helper scripts introduced only when authorized. |
| `tests/` | Cross-package, architecture, integration, and acceptance tests introduced only when authorized. |
| `docs/` | Authoritative product, architecture, governance, security, roadmap, and ADR documentation. |

## Separation Of Responsibilities

- Frontend delivery code in Next.js presents workflows and calls typed API clients; it does not enforce final authorization decisions.
- Backend delivery code in FastAPI exposes HTTP boundaries, validates request shape, applies authentication and authorization middleware where authorized, calls application services, and emits standardized responses.
- Control APIs authenticate callers, enforce server-side authorization, coordinate domain policy, expose OpenAPI contracts, and emit audit events.
- Background workers perform durable asynchronous work under service identity and tenant-scoped authorization.
- Application services coordinate use cases, transactions, ports, idempotency, and state transitions without binding domain policy to delivery frameworks.
- Domain contracts and policy define versioning, reproducibility, evaluation, authorization-relevant decisions, and gate rules independently of delivery and infrastructure.
- Evaluation engines execute evaluator contracts and produce observations without owning authorization policy.
- Provider adapters translate provider-specific model, embedding, authentication, storage, trace, and integration behavior behind ports.
- Persistence adapters translate domain and application persistence needs to PostgreSQL and object-storage implementations without embedding domain decisions.
- Redis-backed queueing, coordination, or ephemeral infrastructure schedules or coordinates work but does not determine tenant access or quality policy.
- Object-storage adapters manage S3-compatible artifact reads and writes behind authorization-aware application services.
- Infrastructure code defines reproducible local and deployment surfaces without owning product policy.
- Authentication and authorization components establish identity and access decisions for protected operations.
- Observability components record OpenTelemetry-compatible traces, metrics, logs, and audit evidence without exposing sensitive tenant data unnecessarily.

## Allowed Dependency Direction

Dependencies must point inward toward stable domain contracts:

1. Delivery code in `apps/` and `services/` may depend on domain contracts and application services.
2. Application services may depend on domain contracts and abstract ports.
3. Domain contracts and policy must not import delivery code, FastAPI route modules, Next.js UI components, PostgreSQL adapters, Redis adapters, object-storage adapters, model-provider adapters, authentication-provider adapters, or OpenTelemetry SDK wiring.
4. Infrastructure and provider adapters may implement domain-defined interfaces.
5. Tests may depend on the code under test but must not create production dependency cycles.

Circular package dependencies are prohibited. The detailed rule is defined in [Modularity Standard](MODULARITY_STANDARD.md) and ADR [0006](adr/0006-modularity-and-dependency-policy.md).

## Interface Boundaries

Interfaces must exist between:

- Domain policy and persistence adapters.
- Domain policy and Redis-backed queueing, coordination, cache, lock, or other ephemeral infrastructure.
- Evaluator contracts and evaluator implementations.
- Model-provider-neutral requests and provider-specific clients.
- Trace ingestion contracts and source-specific trace formats.
- Authentication identity and authorization policy.
- Quality-gate policy and CI/CD integration delivery.
- File or artifact handling and storage implementation.
- OpenAPI contracts and generated or handwritten API clients.
- OpenTelemetry-compatible trace context and provider-specific telemetry exporters.

Provider-specific behavior belongs behind interfaces and must not leak into domain policy.

## Replaceability Requirements

Later implementation must preserve replaceability for:

- Model providers.
- Embedding providers.
- Storage.
- Database adapters above the selected PostgreSQL foundation.
- Redis usage for bounded queueing, coordination, or ephemeral infrastructure.
- Durable workflow engines if a later owner-approved milestone selects one.
- Authentication providers.
- Trace ingestion.

Replacement must not require rewriting domain policy or evaluator contracts.

## Persistence, Storage, And Telemetry Responsibilities

PostgreSQL is the selected relational foundation for tenant-scoped state, artifact metadata, immutable snapshot metadata, run and job state, audit indexes, authorization-relevant records, and transactional consistency where required.

Redis is the selected Phase 1 local foundation for bounded queueing, coordination, caching, rate limiting, locks, or other ephemeral responsibilities. Domain and application policy must remain independent of Redis, and Redis must not be treated as the source of authorization or durable evidence.

S3-compatible private object storage is the selected foundation for datasets, traces, run artifacts, exports, imports, evaluator evidence, and other binary or large artifacts. Object keys, metadata, retention controls, checksums, and access decisions must be mediated by application services and persistence records.

OpenTelemetry-compatible instrumentation is the canonical operational telemetry and trace-interoperability boundary. Runtime traces, metrics, and logs must avoid exposing secrets, private tenant payloads, and model-provider credentials.

## Synchronous And Asynchronous Responsibilities

Synchronous paths should handle authentication, authorization, validation, small reads, small writes, status transitions, and user-visible command acceptance.

Asynchronous paths should handle experiment execution, trace ingestion processing, evaluator execution, imports, exports, comparison and regression analysis, quality-gate calculation, provider calls, and large artifact operations.

Long-running or provider-dependent work must not block interactive control paths except where explicitly designed and bounded.

The FastAPI API boundary may accept commands synchronously, validate idempotency and authorization, persist intent in PostgreSQL, and schedule later work through Redis-backed coordination or later-approved workflow infrastructure. Workers must revalidate tenant and resource context before processing; queue messages are not authorization decisions.

## Failure And Retry Boundaries

- API command acceptance must be idempotent where duplicate submissions are possible.
- Workers must distinguish retryable provider, network, Redis coordination, queue, PostgreSQL, and object-storage failures from permanent validation or authorization failures.
- Completed immutable artifacts and completed runs must not be mutated during retry.
- Cancellation must leave auditable terminal or recoverable state.
- Partial failures must preserve diagnostic trace, error, and audit evidence.
- Retries must not create duplicate completed evidence when an idempotency key or durable state transition already succeeded.
- Eventually consistent derived views must disclose pending, running, failed, canceled, or completed status rather than presenting incomplete background work as final.

## API And Worker Trust Boundaries

Browser clients, SDK callers, CI systems, provider callbacks, and trace sources are untrusted until authenticated, authorized, validated, and bound to tenant context at the API boundary.

FastAPI route handlers are delivery code. They may enforce transport-level validation, authentication middleware, request limits, and error-response standards, but domain policy belongs in application services and domain packages.

Worker inputs from Redis, object storage, external providers, or persisted job state are untrusted. Workers must authenticate as service identities, revalidate tenant scope and resource authorization, classify retryability, emit audit evidence, and avoid logging secrets or private payloads.

## Audit-Event Boundaries

Audit events are required for authentication-sensitive actions, authorization denials, tenant membership changes, artifact version creation, dataset snapshot creation, experiment creation, run state transitions, imports, exports, deletion requests, human review decisions, adjudication, quality-gate decisions, gate overrides, administrative access, and integration callbacks.

Audit logs must be append-oriented and tenant-scoped for access control while remaining available for authorized security review.

## Data Flows

These data flows describe required future behavior. They are not current implementation.

### Dataset Creation

An authenticated user or authorized import submits dataset and test-case content. The control API validates tenant access and input shape, stores versioned records and artifacts, emits audit events, and may schedule asynchronous import processing. Snapshot creation produces immutable membership and content references.

### Experiment Execution

An authorized user defines experiment variants over dataset snapshots and versioned artifacts. The control API records the experiment, emits audit evidence, and schedules workers. Workers execute or coordinate runs, capture attempts, traces, artifacts, costs, and timestamps, then finalize immutable completed runs.

### Trace Ingestion

SDKs, target applications, or integrations submit traces and spans through authenticated ingestion paths. The ingestion boundary validates tenant, schema, size, artifact references, and idempotency keys before persistence or asynchronous processing.

### Evaluation

Workers invoke versioned deterministic evaluators, model judges, or human-review workflows against stored run evidence. Evaluators produce raw observations, scores, rationales where applicable, and errors. Model judges are isolated from authorization and deployment-gate policy.

### Human Review

Authorized reviewers receive assignments under rubric versions. Review evidence, comments, decisions, disagreement, adjudication, and deployment-blocking determinations are stored with audit events and tenant boundaries.

### Comparison And Regression Analysis

Workers compare variants, baselines, slices, and repeated runs using stored metric observations and aggregation rules. Regression findings link back to evidence and must disclose confidence and limitations where applicable.

### Deployment Quality Gates

CI or deployment systems request gate decisions through authenticated integrations. The control API enforces authorization, evaluates stored gate criteria or retrieves calculated decisions, verifies callbacks, records pass or failure evidence, and audits overrides.

## Independence Requirement

Domain and application policy must not import or depend on FastAPI, Next.js, PostgreSQL, Redis, object-storage clients, OpenTelemetry SDK wiring, model vendors, provider-specific clients, or UI implementation details. The selected Phase 1 stack is fixed, while policy remains isolated through ports and adapters.
