# ADR 0004: Tenant Isolation And Data Ownership

## Status

Accepted.

## Context

EvalForge will handle prompts, completions, retrieved context, traces, tool inputs, tool outputs, datasets, human-review comments, audit events, and gate decisions. The repository is public, and the planned product must support tenant-scoped private evaluation evidence.

## Decision

Tenant is the top-level ownership and isolation boundary. Datasets, experiments, runs, traces, results, artifacts, reviews, gates, imports, exports, audit events, and background work must be tenant-scoped. Cross-tenant access is prohibited unless a future owner-approved support policy defines a controlled administrative path.

Authorization must be enforced server-side. UI filtering alone is never authorization. Persistence and storage must include tenant scope, and audit events must record material data, security, review, and gate actions.

## Rationale

Evaluation evidence can contain sensitive business, user, and model-provider data. Tenant isolation must be a core architecture constraint rather than a UI convention.

## Alternatives Considered

- Workspace-only isolation. Rejected because workspace boundaries do not replace tenant ownership.
- Client-side filtering. Rejected because clients are untrusted.
- Shared global records without tenant scope. Rejected because lookup mistakes could leak data.

## Consequences

Every protected operation must carry tenant context. Background workers and integration callbacks must revalidate tenant and resource authorization rather than trusting queued or external messages.

## Security Implications

Cross-tenant data access and broken object-level authorization are highest-priority threats. Audit history must support investigation and accountability.

## Modularity Implications

Authorization policy must not be implemented inside UI components, provider adapters, evaluator adapters, or database adapters. Domain and application services must define access requirements.

## Revisit Conditions

Revisit if owner-approved enterprise administration requires cross-tenant support workflows, if storage architecture changes tenant-scoping mechanics, or if regulatory constraints require stronger isolation.
