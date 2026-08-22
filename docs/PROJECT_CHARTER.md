# EvalForge Project Charter

## Product Vision

EvalForge will be an evaluation, observability, and regression-testing platform for LLM, RAG, tool-using, single-agent, and multi-agent applications. Its purpose is to help teams decide whether a change to a model, prompt, retrieval strategy, tool schema, workflow, evaluator, or cost profile improves production readiness without losing reproducibility, auditability, or tenant isolation.

Milestone 1 establishes product and governance contracts only. It does not provide a running product.

## Intended Users

- AI engineers who build and tune LLM, RAG, tool-using, and agent applications.
- Evaluation engineers who define datasets, metrics, rubrics, and regression gates.
- ML platform engineers who operate repeatable evaluation infrastructure.
- Application developers who need traces, failure analysis, and deployment evidence.
- Security reviewers who assess data handling, tenant isolation, model-provider risk, and tool-use risk.
- Technical product teams who compare variants and track quality, latency, and cost.

## Problems EvalForge Is Intended To Solve

- Repeated model, prompt, retrieval, tool, workflow, and evaluator changes are difficult to compare objectively.
- Evaluation results are often hard to reproduce because prompts, datasets, model parameters, retrieval settings, tool schemas, costs, and evaluator versions are not captured together.
- RAG and agent failures require trace-level inspection rather than only aggregate scores.
- Model-based evaluation can be useful but must be versioned, calibrated, and reviewed rather than treated as unquestionable truth.
- Teams need tenant-scoped audit history and quality gates before deploying risky changes.
- Cost and latency need to be evaluated alongside quality and safety.

## Supported System Categories

EvalForge is planned to support these system categories in Phase 1:

- Direct LLM applications.
- RAG applications.
- Tool-using applications.
- Single-agent systems.
- Multi-step and multi-agent workflows.

## Supported Experiment Categories

EvalForge is planned to support comparisons across:

- Model comparisons.
- Prompt comparisons.
- Retrieval comparisons.
- Tool and tool-schema comparisons.
- Workflow and agent-policy comparisons.
- Evaluator comparisons.
- Pricing and cost comparisons.

## Product Principles

- Evidence over claims: documentation and product surfaces must distinguish what is implemented from what is planned, and must never present planned behavior as currently working.
- Reproducibility over convenience: versioning and immutable snapshots take priority over ease of mutating in-place records, even when that adds friction to early implementation.
- Tenant isolation is architecture, not UI: access control must be enforced server-side and in persistence; client-side filtering is never treated as authorization.
- Human judgment governs high-stakes decisions: model-based evaluation may inform decisions but must not hold authorization, tenant-access, or deployment-gate override authority on its own.
- Replaceability over lock-in: model, storage, queue, authentication, and trace-ingestion providers must remain swappable behind interfaces, even when a specific Phase 1 foundation is selected.
- Sequential discipline over speed: milestones are completed and owner-approved in order, and later-milestone functionality is not preimplemented merely because it may be convenient later.

## Current Milestone Authorization

Milestones 0 through 6 (repository setup; documentation, architecture, governance, security, product, and decision records; engineering and infrastructure foundation; authentication, authorization, and tenant isolation; versioned evaluation domain and persistence; SDK, API, trace, and run ingestion; and dataset and test-case management) are approved. Milestone 6 owner approval was recorded 2026-08-22. Milestone 7 (Experiment Execution and Reproducibility Engine) has been authorized per [Roadmap](ROADMAP.md). No Milestone 8 or later product functionality (deterministic or model-based evaluators, human review, dashboards) may be introduced until Milestone 8 is authorized.

## Phase 1 Product Boundary

Phase 1 covers the locked roadmap from Milestone 0 through Milestone 15. The desired end state is a production-oriented demonstration of an evaluation platform with reproducible runs, versioned artifacts, trace ingestion, deterministic and model-based evaluation, human review, dashboards, integration gates, and documented hardening.

## Success Criteria

Phase 1 is successful when, by Milestone 15 final acceptance:

- A user can define an experiment, run it against an immutable dataset snapshot across at least the direct-LLM, RAG, tool-using, and agent system categories, and retrieve reproducible, explainable evidence for the result.
- Deterministic evaluation, model-based evaluation, and human review are all available as evidence sources for a comparison, with model-judge output disclosed as fallible rather than authoritative.
- Tenant isolation is demonstrably enforced server-side across persistence, authorization, export, and background execution, with no cross-tenant access achievable through supported paths.
- A regression or quality-gate decision can be traced back to the specific runs, metrics, and review decisions that produced it, with audit history intact.
- Every milestone from 0 through 15 has been completed within its authorized scope, validated, and explicitly approved by the owner in sequence, with no later-milestone functionality preimplemented early.
- The finished platform functions as a credible portfolio demonstration of product thinking, domain modeling, security and tenancy design, and evaluation literacy for AI systems, per [Portfolio and Engineering Skills Demonstrated](#portfolio-and-engineering-skills-demonstrated).

## Outside Phase 1

The following are outside Phase 1 unless a formal roadmap amendment is approved:

- Marketplace distribution of evaluators or datasets.
- Fine-tuning orchestration.
- Managed production hosting as a service.
- Enterprise procurement features beyond the initial tenant and authorization model.
- Automated red-team campaign generation beyond planned safety evaluation contracts.
- Billing, invoicing, and account-management workflows.
- Native support for every model provider, vector database, workflow engine, or ticketing system.

## Portfolio and Engineering Skills Demonstrated

EvalForge is intended to demonstrate:

- Product thinking for AI evaluation and observability.
- Domain modeling for versioned, reproducible evaluation artifacts.
- Security and tenancy design for multi-tenant AI systems.
- Modular architecture with replaceable infrastructure and provider adapters.
- Durable execution, auditability, and failure recovery.
- Evaluation literacy across deterministic metrics, model judges, human review, RAG, tool-use, cost, and safety.
- Engineering discipline through milestone gates and documented acceptance criteria.

## Governance

Milestones must be completed and approved sequentially according to the locked roadmap in [Roadmap](ROADMAP.md). Codex implementation does not constitute owner approval. Later-milestone functionality must not be preimplemented in earlier milestones.

Related contracts: [Phase 1 Scope](PHASE_1_SCOPE.md), [Product Requirements](PRODUCT_REQUIREMENTS.md), [Architecture](ARCHITECTURE.md), and [Milestone Acceptance](MILESTONE_ACCEPTANCE.md).
