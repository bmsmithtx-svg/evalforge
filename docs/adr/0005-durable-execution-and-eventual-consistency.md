# ADR 0005: Durable Execution And Eventual Consistency

## Status

Accepted.

## Context

EvalForge experiments, trace processing, evaluator execution, imports, exports, comparisons, regression analysis, and quality gates may be long-running and dependent on external providers. These workloads need retries, cancellation, recovery, idempotency, and clear state transitions.

The Phase 1 foundation is already selected: Python 3.13, FastAPI, PostgreSQL, Redis for bounded queueing, coordination, or ephemeral infrastructure responsibilities, Docker Compose for local development, and OpenTelemetry-compatible instrumentation. Milestone 1 documents those choices but does not implement or configure them.

## Decision

Long-running work must be asynchronous and durable. Workers must use idempotency keys, explicit tenant and resource context, retry boundaries, cancellation states, terminal states, and audit events. Eventual consistency is acceptable for background-derived views when user-facing state discloses pending, running, failed, canceled, or completed status.

PostgreSQL is the selected relational foundation for durable state, run and job metadata, audit indexes, and transactional consistency. Redis is the selected Phase 1 local foundation for bounded queueing, coordination, or ephemeral infrastructure responsibilities, but domain policy and durable evidence must not depend on Redis as the source of truth.

This decision does not implement workers, queues, database schemas, migrations, experiment execution, evaluator execution, or product behavior during Milestone 1. It also does not select a higher-level workflow framework; any such framework requires later authorization.

## Rationale

Provider calls and large evaluations cannot reliably run inside interactive request paths. Durable execution protects reproducibility and user trust when failures, retries, and partial results occur.

## Alternatives Considered

- Synchronous execution in API requests. Rejected because long-running provider work would be fragile and hard to recover.
- Best-effort background jobs without idempotency. Rejected because duplicate or lost results would corrupt evidence.
- Treating all database, queue, and runtime choices as deferred. Rejected because the locked roadmap already selects PostgreSQL, Redis, Python 3.13, FastAPI, Docker Compose, and OpenTelemetry-compatible foundations.
- Early selection of a higher-level workflow engine in Milestone 1. Rejected because this milestone is documentation-only and Redis only establishes the Phase 1 local queueing, coordination, or ephemeral foundation.

## Consequences

Later milestones must model job state, retryability, cancellation, and recovery explicitly. User-facing pages must handle pending and eventually consistent data. Functional durable experiment and evaluator execution remains later-milestone work.

## Security Implications

Queue messages are untrusted for authorization. Workers must authenticate as service identities and revalidate tenant and resource scope before processing.

## Modularity Implications

Execution policy and state transitions belong in domain or application services. Queue or workflow adapters must remain replaceable and must not own tenant authorization or gate policy.

## Revisit Conditions

Revisit if Phase 1 requirements demand stronger consistency for specific gate decisions, if selected infrastructure changes retry semantics, or if operational validation exposes unrecoverable failure modes.
