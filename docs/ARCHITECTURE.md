# Architecture

## Status

This document defines the conceptual EvalForge architecture for later milestones. It does not add implementation files or select a runtime framework, database, queue, workflow engine, model vendor, or UI stack.

## System Context

EvalForge will sit between teams that build AI applications and the systems those applications depend on. It will ingest datasets, experiment definitions, traces, artifacts, evaluation results, and human-review decisions; execute or coordinate evaluation work; and present reproducible quality, safety, latency, and cost evidence.

External systems may include model providers, embedding providers, retrieval stores, target applications, CI/CD systems, authentication providers, object storage, queues or workflow engines, observability tools, and human reviewers.

## Primary Actors

- Authenticated users: engineers, reviewers, product stakeholders, and administrators.
- Service identities: workers, SDK clients, ingestion clients, CI systems, and integration services.
- External providers: model, embedding, authentication, storage, queue, workflow, and trace sources.
- Administrative operators: limited users with elevated operational responsibilities.

## Major Trust Boundaries

Detailed trust-boundary requirements are defined in [Trust Boundaries](TRUST_BOUNDARIES.md). Primary boundaries include browser clients, public APIs, authentication provider, control API, workers, queue or workflow system, database, object storage, model and embedding providers, external target applications, trace ingestion sources, tool-execution environments, human reviewers, CI systems, deployment systems, and administrative operators.

## Planned Runtime Containers

Later milestones may introduce these runtime containers:

- User-facing applications for dashboards, trace inspection, experiment management, and review workflows.
- Control API for authenticated application operations, artifact management, quality-gate decisions, and administrative actions.
- Ingestion API for SDK, trace, run, artifact, and integration submissions.
- Background execution workers for experiments, evaluations, imports, exports, comparison, regression analysis, and gates.
- Durable queue or workflow system for asynchronous orchestration, retries, cancellation, and recovery.
- Persistence stores for tenant-scoped relational state, immutable snapshots, audit events, traces, and artifacts.
- Provider adapters for model, embedding, authentication, storage, queue, workflow, and trace integrations.
- Observability and audit pipelines for operational telemetry and security evidence.

These containers are planned contracts, not current implementation.

## Monorepo Directory Responsibilities

| Directory | Responsibility |
| --- | --- |
| `apps/` | User-facing applications and delivery-specific UI code introduced in later milestones. |
| `packages/` | Shared domain contracts, policy modules, evaluator interfaces, SDK packages, and provider-neutral utilities introduced in later milestones. |
| `services/` | Runtime services such as control APIs, ingestion APIs, and background workers introduced in later milestones. |
| `infrastructure/` | Deployment, provisioning, environment, and operational infrastructure introduced only when authorized. |
| `scripts/` | Local validation, maintenance, and repository automation scripts introduced only when authorized. |
| `tests/` | Cross-package, architecture, integration, and acceptance tests introduced only when authorized. |
| `docs/` | Authoritative product, architecture, governance, security, roadmap, and ADR documentation. |

## Separation Of Responsibilities

- User-facing applications present workflows and call APIs; they do not enforce final authorization decisions.
- Control APIs authenticate callers, enforce server-side authorization, coordinate domain policy, and emit audit events.
- Background workers perform durable asynchronous work under service identity and tenant-scoped authorization.
- Domain contracts and policy define versioning, reproducibility, evaluation, authorization-relevant decisions, and gate rules independently of delivery and infrastructure.
- Evaluation engines execute evaluator contracts and produce observations without owning authorization policy.
- Provider adapters translate provider-specific behavior behind interfaces.
- Persistence adapters store state and artifacts without embedding domain decisions.
- Queue or workflow infrastructure schedules work but does not determine tenant access or quality policy.
- Authentication and authorization components establish identity and access decisions for protected operations.
- Observability components record telemetry and audit evidence without exposing sensitive tenant data unnecessarily.

## Allowed Dependency Direction

Dependencies must point inward toward stable domain contracts:

1. Delivery code in `apps/` and `services/` may depend on domain contracts and application services.
2. Application services may depend on domain contracts and abstract ports.
3. Domain contracts and policy must not import delivery code, database adapters, queue adapters, model-provider adapters, authentication-provider adapters, or UI components.
4. Infrastructure and provider adapters may implement domain-defined interfaces.
5. Tests may depend on the code under test but must not create production dependency cycles.

Circular package dependencies are prohibited. The detailed rule is defined in [Modularity Standard](MODULARITY_STANDARD.md) and ADR [0006](adr/0006-modularity-and-dependency-policy.md).

## Interface Boundaries

Interfaces must exist between:

- Domain policy and persistence adapters.
- Domain policy and queue or workflow infrastructure.
- Evaluator contracts and evaluator implementations.
- Model-provider-neutral requests and provider-specific clients.
- Trace ingestion contracts and source-specific trace formats.
- Authentication identity and authorization policy.
- Quality-gate policy and CI/CD integration delivery.
- File or artifact handling and storage implementation.

Provider-specific behavior belongs behind interfaces and must not leak into domain policy.

## Replaceability Requirements

Later implementation must preserve replaceability for:

- Model providers.
- Embedding providers.
- Storage.
- Databases.
- Queues or durable workflow engines.
- Authentication providers.
- Trace ingestion.

Replacement must not require rewriting domain policy or evaluator contracts.

## Synchronous And Asynchronous Responsibilities

Synchronous paths should handle authentication, authorization, validation, small reads, small writes, status transitions, and user-visible command acceptance.

Asynchronous paths should handle experiment execution, trace ingestion processing, evaluator execution, imports, exports, comparison and regression analysis, quality-gate calculation, provider calls, and large artifact operations.

Long-running or provider-dependent work must not block interactive control paths except where explicitly designed and bounded.

## Failure And Retry Boundaries

- API command acceptance must be idempotent where duplicate submissions are possible.
- Workers must distinguish retryable provider, network, queue, and storage failures from permanent validation or authorization failures.
- Completed immutable artifacts and completed runs must not be mutated during retry.
- Cancellation must leave auditable terminal or recoverable state.
- Partial failures must preserve diagnostic trace, error, and audit evidence.

## Audit-Event Boundaries

Audit events are required for authentication-sensitive actions, authorization denials, tenant membership changes, artifact version creation, dataset snapshot creation, experiment creation, run state transitions, imports, exports, deletion requests, human review decisions, adjudication, quality-gate decisions, gate overrides, administrative access, and integration callbacks.

Audit logs must be append-oriented and tenant-scoped for access control while remaining available for authorized security review.

## Data Flows

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

Domain and application policy must remain independent from specific web frameworks, databases, queues, model vendors, and UI implementations.
