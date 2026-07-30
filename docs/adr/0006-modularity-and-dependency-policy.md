# ADR 0006: Modularity And Dependency Policy

## Status

Accepted.

## Context

EvalForge will grow across applications, packages, services, infrastructure, scripts, and tests. The project needs enforceable boundaries that prevent large files, dumping-ground modules, circular dependencies, provider lock-in, and domain policy leaking into delivery or infrastructure code.

## Decision

Every tracked, handwritten `.py`, `.ts`, `.tsx`, and `.js` file under `apps/`, `packages/`, `services/`, `scripts/`, and `tests/`, including all nested directories, must contain no more than 300 physical lines. Exactly 300 physical lines is allowed. A file with 301 physical lines fails validation.

Generic dumping-ground modules are prohibited, including `utils.py`, `helpers.py`, `common.py`, `utils.ts`, `helpers.ts`, `common.ts`, and equivalent generic catch-all modules.

Generated clients, lockfiles, and specifically allowlisted generated migrations may be excluded only through narrow, documented exceptions incapable of hiding handwritten application logic. Any exception requires a specific owner-approved ADR before the nonconforming code is introduced. An exception may not authorize a generic dumping-ground module.

Automated enforcement begins in Milestone 2 and must run through `make validate`, pre-commit hooks, architecture tests, and GitHub Actions. The Milestone 2 implementation must report every modularity violation with its path and physical line count rather than stop after the first.

## Rationale

Small, focused files and explicit dependency direction make review, testing, and architecture validation practical. The 300-line threshold is simple to enforce and creates early pressure to separate responsibilities.

## Alternatives Considered

- Advisory style guidance only. Rejected because unenforced guidance tends to decay.
- Higher file-size limits. Rejected because large files would hide policy and adapter coupling.
- Allow generic helpers when convenient. Rejected because dumping-ground modules hide domain logic and dependencies.

## Consequences

Later implementation must split modules before they exceed the threshold. Validation must report every violating file and physical line count.

## Security Implications

Security and authorization policy must remain separate from model-output parsing, evaluator adapters, provider adapters, route handlers, and UI components. This reduces the chance that untrusted output or provider-specific behavior controls access.

## Modularity Implications

Domain packages must not import delivery or infrastructure packages. Provider-specific behavior must be behind interfaces. Evaluators must conform to common contracts. Storage, queue, authentication, model-provider, and trace-ingestion dependencies must remain replaceable. Circular imports and circular package dependencies are prohibited.

## Revisit Conditions

Revisit only through owner-approved ADR if a generated artifact class needs an allowlisted exception, if validation discovers an unavoidable false positive, or if the roadmap changes the implementation language set.
