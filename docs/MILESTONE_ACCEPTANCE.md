# Milestone Acceptance

## Purpose

This policy defines how EvalForge milestones move from authorization to owner approval. Codex implementation does not itself constitute owner approval.

## Milestone States

- Not started: work has not been authorized.
- Authorized: the owner has approved starting the milestone.
- In progress: authorized work is underway.
- Implemented pending owner review: implementation is complete and awaiting owner review.
- Corrections required: owner review found required changes.
- Approved: owner has accepted the milestone.

## Required Acceptance Conditions

Every milestone must provide:

- Implementation limited to the authorized milestone.
- Appropriate tests or structural validation for the milestone type.
- Documentation updates matching the implemented scope.
- Verification evidence with commands and results.
- No unresolved validation failures.
- No unauthorized scope.
- No committed secrets.
- A clean working tree after completion.
- Local `HEAD` matching `origin/main` after push when a push is required.
- A completion report.
- Owner review and approval before the next milestone begins.

## Review Principles

- Later-milestone work must not begin before prior milestone approval.
- Documentation may define future contracts but must not claim unimplemented functionality exists.
- Runtime, infrastructure, dependency, or CI/CD changes require explicit milestone authorization.
- Security, tenancy, reproducibility, and modularity contracts are acceptance criteria for later implementation.
- Corrections must remain within the authorized milestone unless the owner approves a formal scope change.

## Completion Report Expectations

Milestone reports should identify repository identity, starting and final commits, changed files, purpose of changes, validation evidence, secret-scan result, roadmap status, exclusions, residual risks, and final working-tree status.

Related documents: [Roadmap](ROADMAP.md), [Project Charter](PROJECT_CHARTER.md), and [Modularity Standard](MODULARITY_STANDARD.md).
