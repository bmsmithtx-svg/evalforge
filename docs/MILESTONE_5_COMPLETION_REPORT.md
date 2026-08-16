# Milestone 5 Completion Report

Date: 2026-08-15.

## Repository Identity

- Remote: `https://github.com/bmsmithtx-svg/evalforge.git`
- Branch: `main`
- Starting commit: `ac0c5d0bdd1f612d449851f608b3eb3665630d38` (Milestone 4 implementation; owner-approved baseline per this milestone's authorization)
- Final local commit: recorded in [Git](#git) below, after this report is committed.

## Roadmap Status

- Milestone 0: Approved.
- Milestone 1: Approved.
- Milestone 2: Approved.
- Milestone 3: Approved.
- Milestone 4: Approved (owner approval recorded 2026-08-15, per this milestone's authorization).
- Milestone 5: Implemented and validated; owner review pending.
- Milestones 6–15: Not started.

## Owner Approval

Milestone 5 (SDK, API, Trace, and Run Ingestion) was authorized and implemented in this session. It is not yet owner-approved; this report is submitted for owner review. Milestone 6 has not been started.

## Scope Implemented

Milestone 5 implements the controlled ingestion boundary through which target applications, SDK clients, and service integrations submit externally produced execution evidence to EvalForge: runs, canonical traces and spans, and artifact evidence, all tenant-isolated, authenticated, authorized, idempotent, and audited. It receives and preserves execution evidence — it does not execute or schedule experiments (Milestone 7), does not implement evaluators (Milestone 8+), and does not add dataset-authoring workflows (Milestone 6).

## Architecture

The existing Milestone 3/4 layering is preserved exactly:

```
delivery (routes/)
   ↓
application (application/)
   ↓
domain + ports (domain/, ports/)
   ↑
adapters (adapters/)
```

New modules follow the established per-concept file pattern (one port/adapter/service module per concept, no shared "utils" module):

- **Domain** (`services/api/src/evalforge_api/domain/`): `ingestion_enums.py` (`RunStatus`, `TraceStatus`, `SpanKind`, `SpanStatus`), `ingestion.py` (immutability rules, batch/payload size bounds, idempotency request-fingerprint hashing — reuses `domain/hashing.py`, no second hashing scheme). `domain/actions.py` extended with `INGEST_RUN`, `VIEW_RUN`, `INGEST_TRACE`, `VIEW_TRACE`.
- **Ports** (`ports/`): `runs.py`, `traces.py` (traces + spans), `evidence_artifacts.py`, `ingestion_repositories.py` (bundle, mirrors `evaluation_repositories.py`).
- **Adapters** (`adapters/`): `run_repository.py`, `trace_repository.py`, `span_repository.py`, `evidence_artifact_repository.py`, `idempotency_sql.py` (shared transactional idempotency helper — the only cross-cutting adapter helper, justified because every ingestion write needs the identical race-safety pattern).
- **Application** (`application/`): `run_service.py`, `trace_service.py`, `span_service.py`, `evidence_artifact_service.py`, `artifact_ingestion_service.py` (wraps Milestone 4's `artifact_service` with idempotency, does not reimplement it), `ingestion_validation.py` (shared cross-tenant reference validation — resource-kind and artifact-ownership checks reused by run/trace/span services).
- **Routes** (`routes/`): `ingestion_runs.py`, `ingestion_traces.py`, `ingestion_spans.py`, `ingestion_artifacts.py`, `ingestion_error_mapping.py` (centralizes exception→HTTP-status translation so route handlers stay thin).
- **Security**: `security/dependencies.py` extended with `get_evaluation_repositories`, `get_ingestion_repositories`, `get_db_pool` (the last one only for `artifact_ingestion_service`'s idempotency-record coordination around the non-transactional S3 side effect).
- **Middleware**: `middleware/request_size_limit.py` extended with `path_suffix_overrides` so the artifact-upload path can use a larger size ceiling than JSON command payloads without loosening the global default.

Every new module respects the 300-physical-line modularity ceiling; the largest new source file is 253 lines (`adapters/run_repository.py`).

### Dependency direction

No new violations: domain modules import nothing from `adapters`/`routes`/`app`; `ports` stay free of `fastapi`/`asyncpg`/`boto3`; adapters implement port protocols; application services depend only on domain + ports; routes depend only on application services + domain (for enums/exceptions) + security dependencies. Verified by `scripts/validate_dependency_boundaries.py` and `scripts/validate_circular_imports.py`.

## Persistence

**Migrations** (`services/api/alembic/versions/`, chained after `0005_eval_domain_artifacts`; each ≤300 physical lines):

- `20260815_0006_ingestion_runs.py` (revision `0006_ingestion_runs`) — `run_status` enum; `runs` table; `run_tool_versions` join table; `forbid_terminal_run_mutation` and `validate_run_tool_version_insert` triggers.
- `20260815_0007_ingestion_traces_and_spans.py` (revision `0007_ingestion_traces_spans`) — `trace_status`, `span_kind`, `span_status` enums; `traces` table; `spans` table; `forbid_finalized_trace_mutation` and `validate_span_insert` triggers.
- `20260815_0008_ingestion_evidence_and_idempotency.py` (revision `0008_evidence_idempotency`, head) — `run_evidence_artifacts` join table; `idempotency_records` table.

Both `upgrade()` and `downgrade()` were exercised against the live test database (`alembic upgrade head` → `alembic downgrade 0005_eval_domain_artifacts` → `alembic upgrade head`), not just written.

**Tables added**: `runs`, `run_tool_versions`, `traces`, `spans`, `run_evidence_artifacts`, `idempotency_records`.

**Tenant-consistent foreign keys**: every child-to-parent reference is a composite `(id, tenant_id)` foreign key against the parent's `UNIQUE (id, tenant_id)` constraint, exactly matching the Milestone 4 pattern — `runs` → `workspaces`/`evaluation_targets`/`versioned_resource_versions` (five optional lineage columns); `run_tool_versions` → `runs`/`versioned_resource_versions`; `traces` → `workspaces`/`runs`; `spans` → `traces`/`spans` (self, parent) /`versioned_resource_versions` (four optional lineage columns) /`artifact_versions` (input/output); `run_evidence_artifacts` → `runs`/`traces`/`artifact_versions`. `idempotency_records.tenant_id` references `tenants(id) ON DELETE CASCADE` directly (it is not a child of any other Milestone 5 table). A cross-tenant reference is rejected by the database even if application validation were bypassed — verified by `test_ingestion_migration.py::test_composite_tenant_consistent_foreign_keys_exist`.

**RLS**: every new table has `ENABLE`/`FORCE ROW LEVEL SECURITY` with the same `FOR ALL ... USING/WITH CHECK (tenant_id = app.current_tenant_id)` policy Milestone 3/4 established, keyed on the same transaction-local session setting. `evalforge_app` remains non-superuser, without `BYPASSRLS`. Verified against the *actual application role* with no session context, not a privileged role (`test_ingestion_tenant_isolation.py::test_direct_database_access_with_no_tenant_context_exposes_no_rows` — zero rows visible across all six tables despite live data existing).

**Grants**: `SELECT, INSERT, UPDATE` on `runs` and `traces` (UPDATE needed only for the active→terminal/finalized transition); `SELECT, INSERT` only on every other table (`run_tool_versions`, `spans`, `run_evidence_artifacts`, `idempotency_records`). No table grants `DELETE`. Verified by `test_ingestion_migration.py`.

**Immutability**: database triggers are the enforcement mechanism, independent of application code —

- `forbid_terminal_run_mutation` (`BEFORE UPDATE` on `runs`): rejects any update once `status` is `completed`/`failed`/`canceled`.
- `forbid_finalized_trace_mutation` (`BEFORE UPDATE` on `traces`): rejects any update once `status = 'finalized'`.
- `validate_span_insert` (`BEFORE INSERT` on `spans`): rejects a new span unless the parent trace is still `ingesting`; rejects a parent-span reference that belongs to a different trace; rejects a span naming itself as its own parent.
- `validate_run_tool_version_insert` (`BEFORE INSERT` on `run_tool_versions`): rejects new tool-version lineage once the parent run is terminal.

Every trigger is exercised by a live-database test, including two (self-parent, cross-trace parent) that are unreachable through the normal application-layer request shape and are tested by issuing raw SQL directly against the least-privilege role — proving the database enforces the invariant independently of the API even bypassing it (`test_ingestion_tenant_isolation.py::test_span_cannot_be_its_own_parent`, `test_span_parent_must_belong_to_the_same_trace`).

**Idempotency storage**: `idempotency_records (tenant_id, operation, idempotency_key)` is `UNIQUE`, and is the durable source of truth — never Redis, never process memory. See [Idempotency Semantics](#idempotency-semantics).

## Canonical Trace/Run Model

**Run** (`runs`): represents captured execution evidence submitted by an external caller, not an EvalForge-scheduled execution (that remains Milestone 7). Optional lineage: `evaluation_target_id`, `model_version_id`, `prompt_version_id`, `retrieval_config_version_id`, `workflow_version_id`, `pricing_version_id` (each an optional `versioned_resource_versions` reference, kind-checked at the application layer), plus a `run_tool_versions` join table for the *plural* tool-definition-version references the domain model calls for. `workspace_id` is required and validated as belonging to the caller's tenant. `status` starts `running`; `finalize_run` transitions to `completed`/`failed`/`canceled`, after which the run is immutable (`forbid_terminal_run_mutation`). `metadata` (JSONB, size-bounded) carries execution/source metadata; `schema_version`, `source`, `correlation_id` carry ingestion/schema and correlation identifiers per the milestone's evidence-metadata requirements.

**Trace** (`traces`): always belongs to exactly one run — `workspace_id` is *derived from the run*, never accepted from the caller, so a trace can never be attached to a workspace inconsistent with its own run's workspace. `status` starts `ingesting` (appendable) and transitions to `finalized` via `finalize_trace`, after which it is immutable. `provider_trace_id` carries the caller's external trace identifier (OpenTelemetry or otherwise) alongside the canonical `id`.

**Span** (`spans`): canonical, provider-neutral span record. `span_kind` is a fixed vocabulary (`llm_call`, `retrieval_call`, `tool_call`, `workflow_step`, `other`) independent of any vendor's `SpanKind`. Each span carries a caller-assigned `provider_span_id` (the external/OTel identifier) alongside the server-generated canonical `id`; `parent_span_id` is resolved server-side from the batch's `provider_parent_span_id` references (see [Idempotency Semantics](#idempotency-semantics)). Optional lineage: `model_version_id`, `retrieval_config_version_id`, `tool_definition_version_id`, `workflow_version_id` (kind-checked), `input_artifact_version_id`/`output_artifact_version_id` (tenant-checked against Milestone 4 artifacts). `attributes` (JSONB, size-bounded) carries safe structured attributes; `token_count_input`/`token_count_output`/`cost_amount`/`cost_currency` carry cost/latency evidence where available. Spans may only be inserted while their trace is `ingesting` (`validate_span_insert`).

**Finalization behavior**: both run and trace finalization are single, database-trigger-enforced one-way transitions. A *replay* of the exact same finalize request (same idempotency key, same fingerprint) after finalization succeeds and returns the already-finalized record; a *new*, distinct finalize attempt against an already-terminal run/trace is rejected (`ImmutableRunError`/`ImmutableTraceError`) — see idempotency semantics below for why the ordering of these two checks matters and was a real bug caught by tests.

**Lineage to Milestone 4 resources**: every optional reference above is independently re-verified against the requesting tenant (`application/ingestion_validation.py`) before being persisted — a caller-supplied UUID is never trusted as proof of ownership; repository lookups are tenant-scoped, so a cross-tenant ID resolves to "not found," not another tenant's row.

## Public API

All routes require a valid bearer token (`get_current_principal`) and resolve tenant context via the path's `{tenant_id}` (`get_tenant_context`), exactly as Milestone 3 established — no new authentication or authorization mechanism was introduced.

| Route | Method | Auth | Idempotency-Key required |
| --- | --- | --- | --- |
| `/tenants/{tenant_id}/runs` | POST | `INGEST_RUN` | Yes |
| `/tenants/{tenant_id}/runs/{run_id}/finalize` | POST | `INGEST_RUN` | Yes |
| `/tenants/{tenant_id}/runs/{run_id}` | GET | `VIEW_RUN` | — |
| `/tenants/{tenant_id}/traces` | POST | `INGEST_TRACE` | Yes |
| `/tenants/{tenant_id}/traces/{trace_id}/finalize` | POST | `INGEST_TRACE` | Yes |
| `/tenants/{tenant_id}/traces/{trace_id}` | GET | `VIEW_TRACE` | — |
| `/tenants/{tenant_id}/traces/{trace_id}/spans` | POST | `INGEST_TRACE` | Yes |
| `/tenants/{tenant_id}/traces/{trace_id}/spans` | GET | `VIEW_TRACE` | — |
| `/tenants/{tenant_id}/artifacts` | POST (multipart) | `CREATE_ARTIFACT` (Milestone 4 action, reused) | Yes |

Request/response bodies are typed Pydantic models with bounded string lengths, bounded collections (`tool_definition_version_ids` ≤ 50, span batches 1–500), and enum-constrained fields (`span_kind`, `status`). Standardized error envelope (`error.code`/`message`/`error_id`) is preserved from Milestone 2/3 unchanged; `routes/ingestion_error_mapping.py` maps every ingestion exception to 401 (via existing auth dependency)/403/404/409/413/422 consistently. Malformed input never reaches an unhandled exception — the pre-existing catch-all handler remains the final backstop and still never leaks internals.

Every route module stays thin: authenticate → resolve tenant → parse/validate transport shape → call an application service → map result/exception → return. No persistence logic in route modules (verified by code inspection and by `scripts/validate_dependency_boundaries.py`, which would fail if `ports/` imported delivery code — routes only ever import *from* application/domain/ports, never the reverse).

## Artifact Controls

Reuses Milestone 4's `artifact_service.create_artifact`/`store_artifact_version` and `S3ArtifactObjectStorage` entirely unchanged — bytes and metadata continue to live exactly where Milestone 4 put them; this milestone does not bypass that boundary.

- **Size ceiling**: new `Settings.max_artifact_bytes` (default 25 MB, env-configurable). Enforced twice: the global `RequestSizeLimitMiddleware` now accepts `path_suffix_overrides`, so `/artifacts` uses the larger artifact ceiling instead of the 2 MB JSON-command default; the route also reads the upload body in bounded 64 KB chunks and aborts as soon as the configured limit is exceeded, so an oversized upload never gets buffered in full. This directly addresses the Milestone 4 completion report's recorded residual risk ("a future ingestion API must apply an explicit artifact-size limit").
- **Tenant-safe storage keys**: unchanged from Milestone 4 — always server-constructed from verified `tenant_id` + artifact ID + content hash, never from caller input.
- **Content-type/media handling**: taken from the multipart part's declared content type, bounded to 200 characters; never trusted as a security boundary.
- **Integrity**: SHA-256 content hash computed and verified exactly as Milestone 4 already does (`retrieve_and_verify_artifact_version` unchanged).
- **Optional evidence attachment**: the same upload call can attach the new artifact version to a run or trace in one request (`run_id`/`trace_id` form fields), via `evidence_artifact_service.attach_artifact` — enforces exactly one of run/trace, tenant-scoped existence of both the run/trace and the artifact version.
- **No public buckets, no credentials in responses/logs**: unchanged from Milestone 4; audit events never embed raw bytes or credentials (see [Audit](#audit-and-security)).

## Idempotency Semantics

Idempotency is durable (PostgreSQL `idempotency_records`, never Redis-only or in-process) and race-safe by construction:

- **`adapters/idempotency_sql.with_idempotency`**: the shared mechanism every run/trace/span/evidence-artifact write uses. It inserts or updates the resource *and* records the idempotency key in one transaction. If a concurrent request wins the race on the `UNIQUE (tenant_id, operation, idempotency_key)` constraint, the losing transaction rolls back atomically (including the resource write) — no orphaned duplicate evidence can ever become visible — and the caller re-reads the winning record in a fresh transaction, returning the original result.
- **Same key + same request fingerprint** (`domain.ingestion.compute_request_fingerprint`, reusing the existing canonical-JSON hashing from `domain.hashing` — no second hashing scheme): the original result is replayed; `created=False` is returned to the caller without repeating the write.
- **Same key + different fingerprint**: `IdempotencyConflictError` → HTTP 409, deterministically, rather than silently treating the requests as equivalent.
- **Span batches**: ingested as one idempotent unit per request. A repeated batch replays exactly the spans that batch created (tracked via a `batch_id` column on `spans`), not a re-derived or partial set.
- **A real bug this design caught**: the first implementation of `finalize_run`/`finalize_trace`/`ingest_spans` pre-checked "is this run/trace still active" *before* consulting the idempotency record. That ordering silently broke replay — a genuine retry of an already-finalized request was rejected as `Immutable*Error` instead of returning the original result, because the pre-check never got to see that the request was a replay. Fixed by removing the premature status pre-check and letting the repository's idempotency-first path run first; a *new*, distinct request against a terminal resource still correctly fails via the database trigger. Caught by `test_run_ingestion_lifecycle.py::test_finalize_replays_with_same_key_and_payload` (and the trace/span equivalents) during this session — see [Tests](#tests).
- **Artifact upload** (`artifact_ingestion_service.upload_artifact`) is a best-effort variant of the same pattern rather than the fully atomic one: because an S3 PUT is a real external side effect that cannot be wrapped in the same PostgreSQL transaction as the idempotency-record insert, a lost race between two concurrent identical uploads may store bytes twice, but only the *winning* artifact version is ever recorded in `idempotency_records` or returned to any caller — the loser's bytes become an orphaned-but-harmless, never-referenced S3 object. This is a deliberate, documented, narrower guarantee than the pure-database case, called out here rather than silently assumed.

## Python SDK

**Location**: `packages/evalforge-sdk/` (own `pyproject.toml`, `src/evalforge_sdk/`, own venv/tests — a real distributable, not folded into `services/api`).

**Modules** (each ≤300 lines; no `utils`/`helpers`/`common` dumping ground):

- `transport.py` — `EvalForgeTransport`: the only module that knows about `httpx`, bearer-token headers, and standardized-error-response parsing. No automatic retries — a network failure or timeout surfaces as a typed exception (`EvalForgeTimeoutError`/`EvalForgeConnectionError`) rather than being silently retried, since retrying a write is only safe when the caller controls the idempotency key.
- `exceptions.py` — `EvalForgeSDKError` base, `EvalForgeAPIError` (carries `status_code`/`code`/`message`/`error_id` parsed from the server's standardized envelope), `EvalForgeConnectionError`, `EvalForgeTimeoutError`.
- `runs.py`, `traces.py`, `spans.py`, `artifacts.py` — typed dataclass request/response models (`RunInput`/`RunRecord`, etc.) plus a client mixin per concept. `EvalForgeClient` composes all four mixins with `EvalForgeTransport`.
- `otel_mapping.py` — pure function mapping a provider-neutral OpenTelemetry-*shaped* dict (plain dict/duck-typed input — no `opentelemetry-sdk` runtime dependency) into a `SpanInput`, behind the interoperability boundary `docs/ARCHITECTURE.md` calls for, without coupling EvalForge's domain to a vendor schema.

**Configuration/authentication**: `EvalForgeClient(base_url=..., access_token=..., timeout=..., transport=...)`. No hardcoded credentials; the caller sources the bearer token however they choose (e.g., their own call to `POST /auth/login`). `transport=` exists solely so tests can inject `httpx.MockTransport` — never used in production.

**Idempotency**: every write method accepts an optional `idempotency_key`; if omitted, a fresh UUID is generated per call automatically (ergonomic default), so repeated calls are *not* implicitly deduplicated unless the caller supplies and reuses their own key — matching "do not silently retry unsafe requests."

**Validation discipline**: the SDK does not duplicate server-side domain/security validation — it only shapes requests and parses typed responses; the server remains the sole source of truth for what is actually accepted.

**Dependencies**: `httpx` only (already a well-known, minimal HTTP client; no competing framework introduced).

## Authorization and Security

- `domain/actions.py` extends the single, deny-by-default `TenantAction` table with `INGEST_RUN`/`VIEW_RUN`/`INGEST_TRACE`/`VIEW_TRACE`. Per `docs/TENANCY_AND_AUTHORIZATION.md` ("developer... submits runs and traces"), `developer` and `tenant_admin` may ingest; every role may view; `evaluation_engineer`/`reviewer`/`read_only_observer` have no ingestion mutation rights. Artifact upload reuses Milestone 4's `CREATE_ARTIFACT` action rather than inventing a parallel concept.
- No route, service, or repository compares role strings directly — every check goes through `TenantContext.can()`, exactly as Milestone 3/4 established.
- Service/SDK authentication reuses the existing bearer-JWT mechanism unchanged; no new credential system, no API-key product was introduced (explicitly out of scope per the milestone brief). `UserKind.SERVICE` (Milestone 3's existing hook) is the intended identity for automated callers; no new provisioning workflow was added.
- Rate limiting and request-size middleware (Milestone 2) apply unchanged to every ingestion route; the artifact route's larger size ceiling is scoped narrowly via `path_suffix_overrides`, not a global loosening.

## Audit and Security

Every application-service function emits a structured audit event on both success/replay and denial, inheriting the Milestone 2 log-redaction processor: `run_ingestion`, `run_finalization`, `trace_ingestion`, `trace_finalization`, `span_batch_ingestion`, `evidence_artifact_attachment`, `artifact_ingestion` — each with outcome `success`/`replayed`/`denied`/`denied_immutable`/`denied_invalid`. No audit event embeds raw payload bodies, span attributes, artifact bytes, or credentials — only tenant, actor, resource IDs, counts, and status, matching the Milestone 4 convention exactly.

## Tests

**Backend** (`services/api`, `pytest`): full suite **184 passed, 0 failed**, coverage 90%. New/changed test files:

- `test_ingestion_migration.py` (7) — head revision, table existence, composite FKs, tenant-cascade FK on `idempotency_records`, RLS enabled/forced, DELETE/UPDATE grant boundaries.
- `test_ingestion_domain.py` (13, including a 3-way parametrized immutability test) — pure unit tests for immutability guards, batch/payload-size bounds, deterministic request-fingerprint hashing, all without a database.
- `test_ingestion_authorization.py` (3) — every role against `VIEW_RUN`/`VIEW_TRACE`/`INGEST_RUN`/`INGEST_TRACE`.
- `test_run_ingestion.py` (5) + `test_run_ingestion_lifecycle.py` (6) — valid ingestion, authorization denial, cross-tenant workspace/model-version rejection, wrong-resource-kind rejection, idempotent create (same/different payload), finalize transition, immutability after finalize, finalize replay, view/not-found.
- `test_trace_ingestion.py` (4) + `test_trace_ingestion_lifecycle.py` (5) — run linkage (including cross-tenant run rejection), workspace derived from run, idempotent create/finalize, immutability, view/not-found.
- `test_span_ingestion.py` (5) + `test_span_ingestion_references.py` (2) + `test_span_ingestion_lifecycle.py` (4) — valid parent/child within and across batches, invalid parent rejected, cross-trace parent rejected, oversized batch rejected, cross-tenant artifact/wrong-kind reference rejected, idempotent batch ingestion, finalized-trace rejection, listing.
- `test_evidence_artifact_ingestion.py` (4) + `test_evidence_artifact_ingestion_lifecycle.py` (2) — attach to run/attach to trace, exactly-one-owner validation, cross-tenant artifact rejection, idempotent attach.
- `test_artifact_ingestion_service.py` (4) — upload creates a version, oversized upload rejected, idempotent upload (same/different payload).
- `test_ingestion_tenant_isolation.py` (3) — RLS default-deny across all six new tables using the *actual application role* with no session context (not a superuser); self-parent and cross-trace-parent database triggers exercised directly via raw SQL, proving the database enforces these invariants independently of (and even bypassing) the application layer.
- `test_ingestion_routes.py` (7) + `test_ingestion_artifact_upload_routes.py` (3) — full HTTP-level coverage via `TestClient`: unauthenticated denial (401), authorization denial (403), missing `Idempotency-Key` header (422), idempotent creation via HTTP (201 then 200, same ID), complete run→trace→spans→finalize-trace→finalize-run→view flow, cross-tenant run lookup returns 404 (not leaking existence), multipart artifact upload with and without evidence attachment, OpenAPI (`/openapi.json`) includes every ingestion path.
- Regression: all 106 pre-existing Milestone 0–4 tests continue to pass unchanged, with one intentional update mirroring the Milestone 3→4 precedent: `test_evaluation_migration.py`'s head-pinning test now checks schema existence (`to_regclass`) instead of pinning the exact head revision, since the head moved past `0005_eval_domain_artifacts`; the exact head is now pinned by `test_ingestion_migration.py`.

**Python SDK** (`packages/evalforge-sdk`, `pytest`, isolated via `httpx.MockTransport` — no live server or network access): **34 passed, 0 failed**, coverage 99%. Covers client configuration (base-URL normalization, default/custom timeout, transport injection), bearer-token header injection and that the token never leaks into a request body, `Idempotency-Key` header presence/absence, per-call idempotency-key auto-generation producing *different* keys across calls, typed error translation for API errors (including non-JSON error bodies), timeout and connection-failure translation, explicit absence of automatic retry (exactly one transport call per logical request even on failure), context-manager cleanup, every resource mixin's request shape (run/trace/span/artifact), and the OpenTelemetry-mapping utility. A real typing bug was caught and fixed while writing these tests: `EvalForgeTransport.__aenter__` was annotated to return the base class instead of `Self`, which would have made `async with EvalForgeClient(...) as client:` type-check `client` as the base transport instead of the full client — fixed using `typing.Self`.

## Validation

Commands run, in order:

```bash
cd services/api && .venv/bin/ruff check src tests alembic && .venv/bin/ruff format --check src tests alembic
cd services/api && .venv/bin/mypy src
cd services/api && .venv/bin/pytest
cd packages/evalforge-sdk && .venv/bin/ruff check src tests && .venv/bin/ruff format --check src tests
cd packages/evalforge-sdk && .venv/bin/mypy src
cd packages/evalforge-sdk && .venv/bin/pytest
python3 scripts/validate_modularity.py
python3 scripts/validate_dependency_boundaries.py
python3 scripts/validate_circular_imports.py
python3 scripts/validate_forbidden_filenames.py
python3 scripts/validate_no_secrets.py
alembic upgrade head / downgrade 0005_eval_domain_artifacts / upgrade head (reversibility check)
```

All passed. `make validate` was run as the authoritative combined entry point (now extended with `sdk-venv` and SDK lint/typecheck/test targets in the root `Makefile`); see [Final Validation Note](#final-validation-note) for one environmental caveat encountered while running it in this session.

### Final Validation Note

The host machine's disk was at 96% capacity (9 GB free) during this session, which made some individual filesystem-heavy operations (`git status`, the modularity scanner walking two freshly created Python virtual environments plus `apps/web/node_modules`) run considerably slower than in prior milestone sessions — several minutes rather than seconds for `git status` at one point. This is an environmental condition of the host, not a defect introduced by this milestone's code; every command listed above was run to completion and passed. The two new `.venv/` directories this milestone's tooling created are already covered by the repository's existing `.gitignore` (`.venv/`) and are not part of this commit.

## Security Review

Reviewed and evidenced by test, matching the Milestone 4 review's structure:

- **Cross-tenant reads/writes/foreign-key attacks**: composite `(id, tenant_id)` foreign keys make a cross-tenant lineage reference fail to insert; independently, every application service re-verifies every optional reference against the tenant before persisting (`ingestion_validation.py`); RLS is a third, independent layer verified with the actual non-superuser application role.
- **UUID substitution / existence leakage**: `get_run`/`get_trace` and every reference-validation helper return "not found" identically whether a resource does not exist or belongs to another tenant; the HTTP-level cross-tenant test confirms a 404, not a 403 or a data leak, for another tenant's real run ID.
- **RLS bypass**: every new table has both `ENABLE` and `FORCE ROW LEVEL SECURITY`; the request-serving role remains the separate non-superuser `evalforge_app`, verified with no session context returning zero rows across all six tables.
- **Structural evidence poisoning**: a span cannot claim a parent from another trace or claim itself as its own parent — enforced by a database trigger proven to fire even when called directly, bypassing the application's own resolver logic.
- **Replay attacks**: every mutating ingestion endpoint requires a caller-supplied `Idempotency-Key`; duplicate submissions with the same key and same effective request never create duplicate evidence (proven for runs, traces, span batches, evidence attachment, and — with the documented narrower guarantee — artifact upload); a same-key-different-payload replay is rejected deterministically (409) rather than silently accepted.
- **Unbounded ingestion**: span batches are capped at 500 and rejected below 1; metadata and span attributes are size-bounded at the domain layer (16 KB / 8 KB) independent of the transport-level request-size middleware; artifact uploads are capped by a dedicated, configurable ceiling enforced both at the middleware layer (for this path only) and via a bounded streaming read in the route handler, closing the exact residual risk the Milestone 4 report flagged.
- **Log/exception leakage**: audit events never embed raw content, span attributes, or artifact bytes; the pre-existing catch-all exception handler is untouched and still returns only a generic message plus an `error_id`; the SDK never logs the bearer token and it never appears in a request body (verified by SDK test).
- **Committed secrets**: `scripts/validate_no_secrets.py` passed; no new credential-shaped value was introduced — every synthetic identifier used in tests (`test-token`, JWT signing keys, MinIO test credentials) matches the pre-existing Milestone 2–4 convention of clearly-local-only values.

**Residual risks** (not remediated in this milestone, out of scope, or deferred by design):

- Artifact-upload idempotency is best-effort, not fully atomic, because of the S3 PUT side effect — documented above and accepted as the correct, honest trade-off rather than a false atomicity claim.
- Service-identity provisioning (issuing a dedicated bearer token to a non-human `UserKind.SERVICE` caller through a supported workflow) remains a later-milestone concern; Milestone 5 SDK/service callers authenticate through the same human-issued bearer-token path as any other user, consistent with the brief's instruction not to invent a new credential system.
- No dedicated ingestion-specific rate limit beyond the existing global per-process rate limiter and request-size middleware was added; span-batch and artifact-size bounds are the primary abuse controls for this milestone, consistent with "this milestone does not require a production-scale distributed streaming system."

No known critical or high-severity Milestone 5 security flaw remains unresolved.

## Documentation

Updated: `README.md` (status, new paragraph, doc index — implicitly includes this report); `docs/ROADMAP.md` (Milestone 4 → Approved, Milestone 5 → implemented/pending review); this report. `docs/DOMAIN_MODEL.md`, `docs/TENANCY_AND_AUTHORIZATION.md`, and `docs/REPRODUCIBILITY_CONTRACT.md` were reviewed and were not judged to need new "Implementation Notes" sections beyond what this report already records, since — unlike Milestone 4, which introduced the entities those documents define — Milestone 5 implements ingestion *for* entities (run, trace, span) that remain conceptual in those documents pending their own later-milestone sections; this report is the authoritative implementation record for Milestone 5.

## Files Changed

- **Backend domain** (`services/api/src/evalforge_api/domain/`): `ingestion_enums.py`, `ingestion.py` (new); `actions.py` (extended).
- **Backend ports** (`ports/`): `runs.py`, `traces.py`, `evidence_artifacts.py`, `ingestion_repositories.py` (new).
- **Backend adapters** (`adapters/`): `run_repository.py`, `trace_repository.py`, `span_repository.py`, `evidence_artifact_repository.py`, `idempotency_sql.py` (new).
- **Backend application** (`application/`): `run_service.py`, `trace_service.py`, `span_service.py`, `evidence_artifact_service.py`, `artifact_ingestion_service.py`, `ingestion_validation.py` (new).
- **Backend routes** (`routes/`): `ingestion_runs.py`, `ingestion_traces.py`, `ingestion_spans.py`, `ingestion_artifacts.py`, `ingestion_error_mapping.py` (new).
- **Backend wiring/security/middleware/settings**: `security/dependencies.py`, `dependency_wiring.py`, `app.py`, `middleware/request_size_limit.py`, `settings.py`, `.env.example`, `pyproject.toml` (extended).
- **Migrations**: `services/api/alembic/versions/20260815_0006_*`, `0007_*`, `0008_*` (new).
- **Backend tests**: 16 new test files (listed above); `conftest.py` (extended — `ingestion_repositories` fixture); `test_evaluation_migration.py` (head-pin test updated, one test).
- **Python SDK** (`packages/evalforge-sdk/`, new package): `pyproject.toml`; `src/evalforge_sdk/{__init__,exceptions,transport,client,runs,traces,spans,artifacts,otel_mapping}.py`; `tests/{conftest,test_transport,test_runs,test_traces,test_spans,test_artifacts,test_otel_mapping,test_client}.py`.
- **Infrastructure/config**: `Makefile` (`sdk-venv`, SDK lint/typecheck/test wiring); `.github/workflows/ci.yml` (new `sdk` job, dependency-audit and `local-stack-integration` updated).
- **Docs**: this report; `README.md`; `docs/ROADMAP.md`.
- **Removed**: `packages/.gitkeep` (superseded by real package content).

## Explicit Exclusions

Confirmed not implemented: Milestone 6 dataset/test-case authoring, import/export, or management UI; Milestone 7 experiment execution, scheduling, or worker orchestration; Milestone 8+ deterministic, model-judge, or human-review evaluators; RAG, tool-use, or agent-trajectory evaluation; comparison/regression/quality-gate engines; a trace-inspection dashboard beyond the minimal ingestion-inspection GET endpoints this milestone's own acceptance criteria call for; CI/CD deployment gates; a new service-identity/API-key management product; a JavaScript/TypeScript SDK; an OpenTelemetry-SDK runtime dependency.

## Residual Risks

See the Security Review section above for the complete, evidenced list.

## Git

- Commit message: `feat: implement sdk api trace and run ingestion`
- The commit is local only; it has not been pushed to `origin/main`. The owner will review this report and authorize the push separately.

Related documents: [Roadmap](ROADMAP.md), [Domain Model](DOMAIN_MODEL.md), [Reproducibility Contract](REPRODUCIBILITY_CONTRACT.md), [Tenancy and Authorization](TENANCY_AND_AUTHORIZATION.md), [Milestone Acceptance](MILESTONE_ACCEPTANCE.md), [Milestone 4 Completion Report](MILESTONE_4_COMPLETION_REPORT.md), ADR [0002](adr/0002-versioned-artifacts-and-immutable-run-snapshots.md), ADR [0004](adr/0004-tenant-isolation-and-data-ownership.md).
