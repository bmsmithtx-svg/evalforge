# ADR 0002: Versioned Artifacts And Immutable Run Snapshots

## Status

Accepted.

## Context

EvalForge must compare model, prompt, retrieval, tool, workflow, evaluator, and pricing changes. Reproducibility depends on knowing exactly which dataset, test cases, prompts, model parameters, retrieval settings, tool schemas, workflows, evaluator versions, pricing assumptions, traces, artifacts, and source commits were used.

## Decision

Evaluation-significant artifacts must be versioned. Finalized dataset snapshots and completed run snapshots must be immutable. Completed run evidence must include hashes or stable references where practical, lineage, timestamps, repetition index, source commit, evaluator versions, and external dependency limitations.

Reruns create new run identities. Corrections create new versions, superseding records, or audited correction events rather than mutating completed evidence.

## Rationale

Historical evidence must remain explainable after prompts, datasets, providers, pricing, and evaluator behavior change. Immutable snapshots make comparison and audit possible.

## Alternatives Considered

- Mutable latest-state records only. Rejected because historical comparisons would become unreliable.
- Full byte-for-byte replay guarantees for all providers. Rejected because hosted models and external systems may be nondeterministic.
- Store only aggregate results. Rejected because trace and artifact evidence are required for failure analysis and gate decisions.

## Consequences

Storage requirements increase because historical artifacts and snapshots must be retained under policy. Reports must disclose when exact reproduction is impossible due to provider or dependency behavior.

## Security Implications

Immutable evidence can preserve sensitive data, so retention, deletion, redaction, and access control must be tenant-scoped and auditable.

## Modularity Implications

Versioning, hashing, and snapshot policy belong in domain contracts and application services, not in database adapters or UI components.

## Revisit Conditions

Revisit if retention constraints require alternative immutable evidence strategies, if provider APIs expose stronger reproducibility guarantees, or if owner-approved policy changes the required evidence set.
