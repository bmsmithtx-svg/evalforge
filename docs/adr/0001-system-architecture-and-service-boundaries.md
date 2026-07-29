# ADR 0001: System Architecture And Service Boundaries

## Status

Accepted.

## Context

EvalForge will evaluate LLM, RAG, tool-using, and agent applications. The platform needs user-facing workflows, APIs, ingestion, background execution, evaluation engines, provider adapters, persistence, authorization, and observability without coupling domain policy to specific frameworks or vendors.

## Decision

EvalForge will use a modular architecture with separate conceptual boundaries for user-facing applications, control APIs, ingestion APIs, background workers, domain contracts and policy, evaluator engines, provider adapters, persistence, queue or workflow infrastructure, authentication and authorization, and observability.

Domain and application policy must remain independent from web frameworks, databases, queues, model vendors, UI implementations, and provider adapters. Dependencies must point inward toward domain contracts.

## Rationale

Evaluation and governance logic must be testable, reusable, and auditable without relying on delivery mechanisms. Provider and infrastructure choices will evolve, while reproducibility, authorization, and evaluator contracts must remain stable.

## Alternatives Considered

- Single monolithic application with route-level policy. Rejected because it would mix delivery, infrastructure, and domain decisions.
- Provider-first architecture. Rejected because model, storage, queue, and authentication providers must remain replaceable.
- UI-driven authorization. Rejected because UI filtering is not authorization.

## Consequences

Later milestones must define clear interfaces before adding provider-specific behavior. More boundaries increase design discipline, but they reduce accidental coupling and make validation possible.

## Security Implications

Server-side authorization, tenant scope, audit events, and model-output isolation must be enforced outside UI components and provider adapters.

## Modularity Implications

Domain packages must not import delivery or infrastructure packages. Circular dependencies are prohibited. Route handlers, UI components, database adapters, queue adapters, and provider adapters must not contain domain policy.

## Revisit Conditions

Revisit if future implementation shows a boundary prevents required Phase 1 workflows, if a selected infrastructure tool imposes unavoidable constraints, or if an owner-approved roadmap amendment changes the platform architecture.
