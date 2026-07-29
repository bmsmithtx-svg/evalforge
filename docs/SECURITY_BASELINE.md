# Security Baseline

## Status

This document defines minimum security requirements for later milestones. It does not implement security controls.

## Minimum Requirements

- No committed secrets in source, documentation, datasets, traces, artifacts, screenshots, or configuration.
- Secrets must be injected through environment-specific mechanisms rather than hardcoded values.
- Least privilege must apply to users, service identities, provider credentials, storage access, queue access, database access, and administrative operations.
- Tenant isolation must be enforced in server-side authorization and persistence.
- UI filtering alone must never be treated as authorization.
- Encryption in transit is required for production network paths.
- Encryption at rest must be used where supported by chosen storage and database systems.
- Secure defaults must deny access when identity, tenant, role, resource, or policy cannot be verified.
- Audit logging is required for material data, security, review, and deployment-gate events.
- Dependency review must be performed before adding runtime or development dependencies.
- Secret scanning must run before acceptance of milestones that introduce files capable of containing credentials.
- Input validation must cover APIs, SDK ingestion, uploads, imports, webhooks, callbacks, queue messages, tool outputs, and model outputs.
- Output encoding must be used where untrusted content is displayed.
- Rate limiting and quotas must protect public and tenant-scoped endpoints where practical.
- Safe file handling must validate type, size, path, parser behavior, storage location, and tenant ownership.
- Network egress restrictions should be applied where practical, especially for tool execution and worker environments.
- Model-provider credential isolation must prevent one tenant or environment from using another tenant or environment credential.
- Webhook and callback verification must authenticate source, validate payload, prevent replay where practical, and audit failures.
- Secure deletion expectations must be defined for tenant data, artifacts, exports, backups, and provider-side limitations.
- Backup and recovery controls must preserve tenant isolation and auditability.
- Development, test, and production environments must be separated.
- Sensitive trace data must be redacted or access-restricted according to classification and tenant policy.
- Untrusted model output must not be used as authorization policy, security policy, or deployment-gate override authority.

## Known Security Limitations During Milestone 1

Milestone 1 is documentation-only. No runtime security control exists yet. Later milestones must implement and validate controls before claiming operational security.

Related documents: [Threat Model](THREAT_MODEL.md), [Trust Boundaries](TRUST_BOUNDARIES.md), [Data Governance](DATA_GOVERNANCE.md), and [Tenancy and Authorization](TENANCY_AND_AUTHORIZATION.md).
