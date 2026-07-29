# ADR 0005: Durable Execution And Eventual Consistency

## Status

Accepted.

## Context

EvalForge experiments, trace processing, evaluator execution, imports, exports, comparisons, regression analysis, and quality gates may be long-running and dependent on external providers. These workloads need retries, cancellation, recovery, idempotency, and clear state transitions without selecting runtime infrastructure in Milestone 1.

## Decision

Long-running work must be asynchronous and durable. Workers must use idempotency keys, explicit tenant and resource context, retry boundaries, cancellation states, terminal states, and audit events. Eventual consistency is acceptable for background-derived views when user-facing state discloses pending, running, failed, canceled, or completed status.

This decision does not select or configure a queue, workflow engine, database, or worker runtime during Milestone 1.

## Rationale

Provider calls and large evaluations cannot reliably run inside interactive request paths. Durable execution protects reproducibility and user trust when failures, retries, and partial results occur.

## Alternatives Considered

- Synchronous execution in API requests. Rejected because long-running provider work would be fragile and hard to recover.
- Best-effort background jobs without idempotency. Rejected because duplicate or lost results would corrupt evidence.
- Early selection of a workflow engine in Milestone 1. Rejected because this milestone is documentation-only.

## Consequences

Later milestones must model job state, retryability, cancellation, and recovery explicitly. User-facing pages must handle pending and eventually consistent data.

## Security Implications

Queue messages are untrusted for authorization. Workers must authenticate as service identities and revalidate tenant and resource scope before processing.

## Modularity Implications

Execution policy and state transitions belong in domain or application services. Queue or workflow adapters must remain replaceable and must not own tenant authorization or gate policy.

## Revisit Conditions

Revisit if Phase 1 requirements demand stronger consistency for specific gate decisions, if selected infrastructure changes retry semantics, or if operational validation exposes unrecoverable failure modes.
