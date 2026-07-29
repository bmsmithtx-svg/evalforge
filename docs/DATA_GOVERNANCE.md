# Data Governance

## Status

This document defines planned data governance rules for EvalForge. It does not implement storage, deletion, export, or retention controls.

## Data Classification

EvalForge data must be classified before production use:

- Public project metadata: documentation and non-sensitive repository metadata.
- Tenant confidential data: prompts, completions, traces, datasets, retrieved context, tool inputs, tool outputs, evaluations, reviews, and reports.
- Sensitive tenant data: private customer content, regulated data, credentials accidentally included in traces, proprietary source material, and security findings.
- Operational security data: audit logs, access records, provider credential references, callback metadata, and administrative actions.
- Synthetic demonstration data: generated or redacted data approved for public demonstration.

## Tenant Ownership

Tenant-scoped data belongs to the tenant. EvalForge records creator, reviewer, service identity, and administrator actions for audit, but those actors do not gain personal ownership over tenant data.

## Data Minimization

Later implementation must collect only data needed for evaluation, reproducibility, audit, failure analysis, and governance. Trace ingestion, artifact upload, and imports should support redaction or field suppression where practical.

## Handling Expectations

- Prompts and completions: treat as tenant confidential by default and sensitive when they contain private or regulated content.
- Retrieved context: preserve enough source identity for grounding while respecting source access and retention limits.
- Traces: store canonical spans with required evidence and redact sensitive fields where policy requires.
- Tool inputs and tool outputs: classify by tool side effects and data content; restrict sensitive tool evidence to authorized users.
- Uploaded datasets: validate file type, size, schema, tenant ownership, and sensitivity labels.
- Human-review content: protect comments, evidence selections, reviewer identity, and adjudication history according to role and tenant policy.

## Retention Policy Framework

Each tenant must eventually be able to define retention expectations for datasets, snapshots, runs, traces, artifacts, evaluation results, review records, exports, and audit logs. Retention policy must distinguish immutable evidence needed for gates from data eligible for deletion or redaction.

## Deletion And Export

Tenant-scoped deletion must remove or render inaccessible tenant data according to policy while preserving required audit evidence. Exports must require authorization for every included resource and should include metadata needed to interpret versions, hashes, and limitations.

## Auditability

Material data actions must emit audit events, including import, export, deletion, retention changes, data classification changes, administrative access, and redaction.

## Sensitive-Data Handling

Sensitive data must not be committed to the public repository. Production private data should not be used in demonstrations. Demonstrations should prefer synthetic or redacted data.

## Model-Provider Data Retention

Model-provider requests may be subject to provider-specific logging and retention. EvalForge must record provider and model identity, disclose provider retention assumptions where known, and keep provider credentials isolated by tenant or environment.

## Backup And Recovery

Backups must preserve tenant isolation, encryption controls where supported, and recovery evidence. Recovery procedures must avoid restoring deleted tenant data beyond documented retention rules unless policy explicitly allows it.

Related documents: [Security Baseline](SECURITY_BASELINE.md), [Reproducibility Contract](REPRODUCIBILITY_CONTRACT.md), and [Tenancy and Authorization](TENANCY_AND_AUTHORIZATION.md).
