# ADR 0001: System Architecture And Service Boundaries

## Status

Accepted.

## Context

EvalForge will evaluate LLM, RAG, tool-using, and agent applications. The platform needs user-facing workflows, APIs, ingestion, background execution, evaluation engines, provider adapters, persistence, authorization, and observability without coupling domain policy to delivery frameworks, infrastructure APIs, or vendors.

## Decision

EvalForge will use one canonical monorepo with the existing `apps/`, `packages/`, `services/`, `infrastructure/`, `scripts/`, and `tests/` boundaries. The architecture is a modular monolith with separate domain, application, delivery, evaluator, persistence, provider-adapter, and infrastructure boundaries.

The selected Phase 1 foundation is Python 3.13 for backend services, workers, evaluation code, automation, and the later Python SDK; FastAPI for the backend HTTP API boundary; OpenAPI for machine-readable API contracts; Next.js with TypeScript for the user-facing web application; PostgreSQL for primary relational persistence; Redis for bounded queueing, coordination, or ephemeral infrastructure responsibilities; S3-compatible private object storage for datasets, traces, run artifacts, exports, and other large artifacts; OpenTelemetry-compatible telemetry; Docker Compose for local development; GitHub Actions for CI; and a root `make validate` entry point beginning in Milestone 2.

Domain and application policy must remain independent from delivery-framework APIs, database clients, Redis clients, object-storage clients, model vendors, UI implementations, and provider adapters. Dependencies must point inward toward domain contracts.

## Rationale

Evaluation and governance logic must be testable, reusable, and auditable without relying on delivery mechanisms. The selected foundation removes ambiguity for Phase 1 implementation while ports and adapters keep provider-specific and infrastructure-specific behavior replaceable. Reproducibility, authorization, and evaluator contracts must remain stable.

## Alternatives Considered

- Single monolithic application with route-level policy. Rejected because it would mix delivery, infrastructure, and domain decisions.
- Provider-first architecture. Rejected because model, storage, queue, authentication, telemetry, and deployment providers must remain replaceable behind ports.
- Leaving all framework and infrastructure choices undecided. Rejected because the authoritative roadmap already locks the Phase 1 foundation stack while still prohibiting provider-specific domain coupling.
- UI-driven authorization. Rejected because UI filtering is not authorization.

## Consequences

Later milestones must define clear interfaces before adding provider-specific behavior. The repository can implement the selected Python 3.13, FastAPI, OpenAPI, Next.js, TypeScript, PostgreSQL, Redis, S3-compatible storage, OpenTelemetry, Docker Compose, GitHub Actions, and `make validate` foundation without coupling domain policy to provider or infrastructure details.

## Security Implications

Server-side authorization, tenant scope, audit events, and model-output isolation must be enforced outside UI components and provider adapters.

## Modularity Implications

Domain packages must not import delivery or infrastructure packages. Circular dependencies are prohibited. Route handlers, UI components, PostgreSQL adapters, Redis adapters, object-storage adapters, OpenTelemetry wiring, and provider adapters must not contain domain policy.

## Revisit Conditions

Revisit if future implementation shows a boundary prevents required Phase 1 workflows, if a selected infrastructure tool imposes unavoidable constraints, or if an owner-approved roadmap amendment changes the platform architecture.
