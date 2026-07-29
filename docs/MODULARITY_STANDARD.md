# Modularity Standard

## Status

This standard is binding for future implementation. Milestone 1 defines the policy only; automated enforcement begins in Milestone 2.

## File-Size Ceiling

Every tracked, handwritten `.py`, `.ts`, `.tsx`, and `.js` file under application, package, service, script, and test directories must contain no more than 300 physical lines. Exactly 300 physical lines is allowed. A file with 301 physical lines fails validation. Nested directories are included.

Generated clients, lockfiles, and specifically allowlisted generated migrations may be excluded. Any exclusion must be narrow, documented, and incapable of hiding handwritten application logic.

## Prohibited Dumping-Ground Modules

Generic dumping-ground modules are prohibited, including:

- `utils.py`
- `helpers.py`
- `common.py`
- `utils.ts`
- `helpers.ts`
- `common.ts`
- Equivalent generic catch-all modules.

An exception may not authorize a generic dumping-ground module.

## Architecture Rules

- Domain and application policy must not be placed in route handlers, UI components, database adapters, queue adapters, model-provider adapters, or other delivery or infrastructure code.
- Domain packages must not import delivery or infrastructure packages.
- Provider-specific behavior must be placed behind interfaces.
- Evaluator implementations must conform to common evaluator contracts.
- Storage, queue, authentication, model-provider, and trace-ingestion dependencies must remain replaceable.
- Circular imports and circular package dependencies are prohibited.
- Model-output parsing must remain separate from authorization, security, and deployment-gate policy.
- Evaluator or provider adapters must not determine authorization requirements.
- Later-milestone functionality may not be preimplemented to prepare the architecture.

## Enforcement

Automated enforcement will begin in Milestone 2 and must eventually run through local validation, architecture tests, pre-commit hooks, and GitHub Actions. Validation failures must identify every violating file and its physical line count.

Any exception requires a specific owner-approved ADR before the nonconforming code is introduced. The exception must identify the exact file or generated-file class, reason, maximum scope, validation behavior, and expiration or revisit condition.

Related documents: [Architecture](ARCHITECTURE.md), [Milestone Acceptance](MILESTONE_ACCEPTANCE.md), and ADR [0006](adr/0006-modularity-and-dependency-policy.md).
