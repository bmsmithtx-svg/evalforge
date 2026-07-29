# Product Requirements

## Status

This document defines planned EvalForge Phase 1 requirements. It does not claim that these requirements are currently implemented.

## Functional Requirements

| ID | Requirement | Measurable contract |
| --- | --- | --- |
| FR-01 | Versioned datasets and test cases | Each dataset and test case change must create or reference a version identity with lineage, author, timestamp, tenant, and change reason. |
| FR-02 | Immutable dataset snapshots | Experiment execution must use immutable dataset snapshots whose membership and content cannot change after snapshot finalization. |
| FR-03 | Versioned prompts | Prompt content, template variables, rendering rules, and metadata must be versioned before use in a run. |
| FR-04 | Versioned models | Provider, model identifier, model parameters, capability assumptions, and deprecation status must be captured as a versioned artifact. |
| FR-05 | Versioned retrieval configurations | Retrieval source, index identity, embedding configuration, filters, ranking settings, chunking assumptions, and top-k behavior must be versioned. |
| FR-06 | Versioned tool definitions | Tool names, descriptions, input schemas, output schemas, side-effect classification, and safety constraints must be versioned. |
| FR-07 | Versioned workflows | Workflow and agent-policy definitions must capture step order, branching policy, tool-use policy, retry policy, termination criteria, and version lineage. |
| FR-08 | Versioned evaluators | Deterministic evaluators, model judges, rubrics, calibration sets, thresholds, and evaluator configuration must be versioned. |
| FR-09 | Versioned pricing definitions | Unit prices, currency, provider, model, effective dates, and pricing assumptions must be versioned. |
| FR-10 | Experiment definitions and variants | Experiments must define evaluation target, dataset snapshot, artifacts under comparison, metrics, gates, repetitions, and variants. |
| FR-11 | Repeated runs | Experiments must support repeated runs with repetition index, timestamps, captured parameters, trace references, and reproducibility metadata. |
| FR-12 | Canonical traces and spans | LLM calls, retrieval calls, tool calls, workflow steps, errors, artifacts, timing, token usage, and cost observations must map to canonical traces and spans. |
| FR-13 | Evaluation results | Evaluation output must bind evaluator version, run attempt, test case, raw observation, score, rationale when applicable, confidence when applicable, and errors. |
| FR-14 | Human reviews | Human review must support rubric version, reviewer identity, assignment, comments, evidence, decision, disagreement, and adjudication. |
| FR-15 | Comparison and regression analysis | The platform must compare variants across metrics, slices, confidence intervals where applicable, and previous baselines. |
| FR-16 | Quality gates | Quality gates must evaluate documented criteria and produce auditable pass, warn, fail, or override decisions. |
| FR-17 | Trace inspection and failure analysis | Users must be able to inspect failed runs, traces, spans, artifacts, evaluator outputs, and contributing metric observations. |
| FR-18 | Import and export | Authorized users must be able to import and export datasets, experiment definitions, results, traces, and reports with tenant-scoped controls. |
| FR-19 | APIs and SDKs | Later APIs and SDKs must expose versioned artifact, ingestion, execution, result, review, and export workflows without bypassing authorization. |
| FR-20 | Background execution | Long-running experiments, ingestion, evaluation, exports, and gate calculations must execute durably with idempotency, retry, cancellation, and recovery contracts. |
| FR-21 | Dashboard and review workflows | User-facing applications must support experiment setup, monitoring, review, comparison, trace inspection, and gate workflows. |
| FR-22 | Authentication and tenant isolation | All protected runtime operations must authenticate users or services and enforce tenant-scoped server-side authorization. |
| FR-23 | Audit history | Security-sensitive and quality-gate operations must emit audit events with actor, tenant, resource, action, timestamp, and outcome. |

## Nonfunctional Requirements

| ID | Requirement | Measurable contract |
| --- | --- | --- |
| NFR-01 | Reproducibility | Completed runs must retain enough artifact versions, parameters, timestamps, source commit, traces, and hashes to explain or rerun the experiment where provider behavior allows. |
| NFR-02 | Determinism where applicable | Deterministic evaluators must produce the same result for the same inputs and version; nondeterministic dependencies must be disclosed. |
| NFR-03 | Reliability and recovery | Background work must be recoverable after process interruption without duplicating committed results. |
| NFR-04 | Security | Later implementation must meet [Security Baseline](SECURITY_BASELINE.md) before production acceptance. |
| NFR-05 | Tenant isolation | Tenant data must be isolated in persistence, authorization, audit, export, deletion, and background processing. |
| NFR-06 | Auditability | Material data, security, review, and gate decisions must be reconstructable from durable audit evidence. |
| NFR-07 | Extensibility | New evaluators, providers, trace sources, and storage backends must be addable behind interfaces without changing domain policy. |
| NFR-08 | Replaceable infrastructure and model providers | Storage, database, queue or workflow system, authentication provider, model provider, embedding provider, and trace ingestion mechanisms must remain replaceable. |
| NFR-09 | Performance | Interactive pages and APIs must expose paginated, bounded access patterns; long-running work must be asynchronous. |
| NFR-10 | Scalability | Execution, ingestion, and evaluation workloads must support horizontal scaling without breaking idempotency or tenant isolation. |
| NFR-11 | Availability expectations | The architecture must separate interactive control paths from background execution so failures degrade predictably. |
| NFR-12 | Cost visibility | Runs and experiments must capture token, latency, provider, pricing-version, and total cost observations where available. |
| NFR-13 | Observability | Services and workers must eventually emit logs, metrics, traces, and audit events suitable for operations and failure analysis. |
| NFR-14 | Accessibility | User-facing workflows must target accessible navigation, readable contrast, keyboard operation, and clear status feedback. |
| NFR-15 | Testability | Domain policy, evaluator contracts, authorization behavior, and quality-gate logic must be testable without live providers. |
| NFR-16 | Maintainability | Code introduced in later milestones must follow [Modularity Standard](MODULARITY_STANDARD.md). |
| NFR-17 | Data retention and deletion | Tenant-scoped retention, export, and deletion behavior must be explicit and auditable. |

## Requirement Interpretation

Functional requirements describe eventual platform contracts. A requirement is satisfied only when the authorized milestone implements it, validates it, documents it, and receives owner approval under [Milestone Acceptance](MILESTONE_ACCEPTANCE.md).
