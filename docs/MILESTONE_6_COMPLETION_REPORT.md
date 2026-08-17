# Milestone 6 Completion Report

Date: 2026-08-17.

## Repository Identity

- Remote: `https://github.com/bmsmithtx-svg/evalforge.git`
- Branch: `main`
- Starting commit: `c7744d65cf8d850ec62c6e6c29acba14f4bc5548` (Milestone 5 implementation; owner-approved baseline per this milestone's authorization, recorded in this session before Milestone 6 began)
- Final local commit: recorded in [Git](#git) below, after this report is committed.

## Roadmap Status

- Milestone 0: Approved.
- Milestone 1: Approved.
- Milestone 2: Approved.
- Milestone 3: Approved.
- Milestone 4: Approved.
- Milestone 5: Approved (owner approval recorded 2026-08-17).
- Milestone 6: Implemented and validated; owner review pending.
- Milestones 7–15: Not started.

## Owner Approval

Milestone 6 (Dataset and Test-Case Management) was authorized and implemented in this session. It is not yet owner-approved; this report is submitted for owner review. Milestone 7 has not been started.

## Preflight

- Repository: `bmsmithtx-svg/evalforge`; local workspace: `/Users/bmsm1th/Documents/evalforge`.
- Branch: `main`. Remote `origin` confirmed pointed at the canonical repository.
- `git fetch --prune origin` run; local `HEAD` and `origin/main` both confirmed at `c7744d65cf8d850ec62c6e6c29acba14f4bc5548`, matching the required starting SHA exactly.
- Working tree: one untracked file was present at session start, `services/api/src/evalforge_api/middleware/request_size_limit 2.py` — a stray, superseded duplicate (older content than the tracked file, missing the Milestone 5 `path_suffix_overrides` mechanism; macOS Finder-style " 2" copy naming). Confirmed with the owner and removed before any implementation work began. No other uncommitted or unexplained state existed.
- Milestone 5 was implemented and validated but recorded in repository docs as "owner review pending" at session start. The owner approved Milestone 5 explicitly in this session (with the completion SHA above); that approval was recorded in `README.md`, `docs/ROADMAP.md`, `docs/MILESTONE_5_COMPLETION_REPORT.md`, and `docs/PROJECT_CHARTER.md` before Milestone 6 implementation began, per the repository's own `docs/MILESTONE_ACCEPTANCE.md` policy ("owner review and approval before the next milestone begins") and the precedent set by the Milestone 2 approval commit.

## Scope Implemented

Milestone 6 turns the Milestone 4 dataset/test-case/snapshot persistence substrate into managed, auditable, tenant-isolated evaluation assets with a public API: dataset lifecycle management (create/read/update/archive/list), test-case authoring with a typed and validated content schema, draft-to-immutable-snapshot publication (reusing Milestone 4's versioning and snapshot mechanism unchanged), version history and deterministic snapshot comparison, CSV/JSONL bulk import with atomic all-or-nothing semantics, JSONL/CSV export, deterministic structural duplicate detection, dataset cloning with provenance, and deterministic sampling/splitting over finalized snapshots. It does not implement evaluation execution, evaluators, human review, or any Milestone 7+ functionality.

## Architecture

The existing Milestone 3–5 layering is preserved exactly:

```
delivery (routes/)
   ↓
application (application/)
   ↓
domain + ports (domain/, ports/)
   ↑
adapters (adapters/)
```

**Domain** (`services/api/src/evalforge_api/domain/`, new): `test_case_content.py` — a frozen-dataclass, explicitly validated schema for what was previously unstructured `content: dict[str, Any]` (input, expected output, structured expected output, context references, tags, metadata, difficulty, category, safety labels, tool expectations, trajectory expectations; bounded collection sizes in the style of `domain/ingestion.py`). `duplicate_detection.py` — deterministic structural dedup-hash computation, reusing `domain/hashing.py`. `snapshot_comparison.py` — pure added/removed/changed/unchanged diff over two frozen membership sets. `sampling.py` — SHA-256-rank-based deterministic sampling/splitting (never the `random` module). `import_parsing.py` and `export_formatting.py` — pure CSV/JSONL parsing and formatting (stdlib `csv`/`json` only, no `eval`/`exec`/pickle). `domain/actions.py` extended with `UPDATE_DATASET`, `ARCHIVE_DATASET`, `CLONE_DATASET`, `IMPORT_TEST_CASES`.

**Ports** (`ports/`): `datasets.py` extended (new record fields, `update_dataset`, `archive_dataset`, `list_datasets`, `archive_test_case`, `list_test_cases`, `get_latest_test_case_version`, `list_current_dedup_hashes`, `create_test_cases_with_versions`, `TestCaseSeedRow`); snapshot-side Protocol/records split into a new `dataset_snapshots.py` to stay under the line ceiling, with `list_snapshots` added; `ports/evaluation_repositories.py` updated for the split import.

**Adapters** (`adapters/`): `dataset_repository.py` extended with the new dataset/test-case queries; a new `test_case_version_repository.py` holds version/dedup-hash queries, with `PostgresDatasetRepository` composing it so one object still satisfies the single `DatasetRepository` protocol; shared column constants/row-mapping helpers factored into `dataset_row_mapping.py` (a concept-scoped module, not a generic dumping ground); `dataset_snapshot_repository.py` gained `list_snapshots`.

**Application** (`application/`, new): `test_case_service.py`, `duplicate_detection_service.py`, `snapshot_comparison_service.py`, `dataset_sampling_service.py`, `dataset_clone_service.py`, `dataset_import_service.py`, `dataset_export_service.py`, `dataset_errors.py` (shared exception types for the eight dataset-management services — `dataset_service.py` re-exports the two names Milestone 4 already established so no existing call site changed). `dataset_service.py` and `snapshot_service.py` extended in place.

**Routes** (`routes/`, new — the first public HTTP surface for the Milestone 4 dataset/snapshot domain): `datasets.py`, `test_cases.py`, `dataset_snapshots.py`, `dataset_import_export.py`, `dataset_operations.py` (clone, sample/split), `dataset_error_mapping.py` (a dataset-domain equivalent of `ingestion_error_mapping.py`, since that module is bound to Milestone 5 ingestion services), `dataset_response_models.py` (shared response schemas). Every router registered in `app.py` alongside the existing `ingestion_*` routers; every route authenticates through the existing `get_tenant_context` dependency chain — no new auth mechanism.

**Wiring**: no changes to `dependency_wiring.py` or `security/dependencies.py` were needed — the existing `build_evaluation_repositories`/`get_evaluation_repositories`/`get_tenant_context` machinery already covered the new adapters and routes.

### Reuse of Milestone 4 versioning

Draft/publish semantics were not reinvented: a test case's mutable state is simply "its latest `test_case_versions` row"; editing always inserts a new version (`create_test_case_version`, unchanged from Milestone 4, now validating content through `TestCaseContent` first); publication is Milestone 4's existing `snapshot_service.create_draft_snapshot` → `add_test_case_version` → `finalize_snapshot` flow, untouched. Milestone 6 adds no second versioning subsystem, no second hashing scheme, and no new immutability trigger — it only adds *mutable* columns to the two rows that were never meant to be immutable (`datasets`, `test_cases` container/lifecycle metadata) while leaving `test_case_versions` and finalized `dataset_snapshots` exactly as append-only as Milestone 4 left them.

### Boundary/architecture checks

- `scripts/validate_dependency_boundaries.py`: passed — no domain module imports adapters/routes/fastapi/asyncpg; ports remain framework-free; adapters implement port protocols; application depends only on domain+ports; routes depend only on application/domain/security.
- `scripts/validate_circular_imports.py`: passed.
- Largest new/changed production file: `domain/test_case_content.py` at 245 physical lines (ceiling 300); `adapters/dataset_repository.py` at 237; `adapters/test_case_version_repository.py` at 224; `application/snapshot_service.py` at 222. No file exceeds the ceiling (`scripts/validate_modularity.py` passed).
- No `utils.py`/`helpers.py`/`common.py`-style module was introduced (`scripts/validate_forbidden_filenames.py` passed); `dataset_row_mapping.py` and `dataset_errors.py` are concept-scoped (dataset-repository row mapping; dataset-service exception types), not generic dumping grounds.

## Persistence

**Migration** (`services/api/alembic/versions/20260817_0009_dataset_test_case_management.py`, revision `0009_dataset_test_case_mgmt`, `down_revision = 0008_evidence_idempotency`, head): additive only, no rewrite of migrations 0001–0008.

- `datasets` gains `description`, `tags` (JSONB), `metadata` (JSONB), `updated_at`, `updated_by`, `archived_at`, `source` (`manual`/`cloned`, `CHECK`-constrained), `cloned_from_dataset_id`, `cloned_from_snapshot_id` (both composite `(id, tenant_id)` foreign keys — the second self-referential), plus `ix_datasets_status`.
- `test_cases` gains `updated_at`, `updated_by`, `archived_at`, `source` (`manual`/`imported`/`cloned`, `CHECK`-constrained), `source_test_case_id` (composite self-referential FK), `import_batch_id`, plus `ix_test_cases_import_batch_id`.
- `test_case_versions` gains `dedup_hash` (`NOT NULL DEFAULT ''`, real values supplied by every application-layer insert) plus a composite index `ix_test_case_versions_dedup_hash (test_case_id, dedup_hash)`.
- `GRANT UPDATE ON datasets, test_cases TO evalforge_app` — the only grant change. `test_case_versions` and `dataset_snapshot_items` remain `SELECT, INSERT` only; `dataset_snapshots` keeps its pre-existing trigger-guarded `UPDATE` (draft→finalized only). No table anywhere grants `DELETE`.
- `downgrade()` reverses every column, index, constraint, and grant. Verified live, twice, against the real test database (not just written):

```
alembic upgrade head        0008_evidence_idempotency → 0009_dataset_test_case_mgmt (head)   PASS
alembic downgrade 0008_evidence_idempotency             current = 0008_evidence_idempotency   PASS
alembic upgrade head                                     current = 0009_dataset_test_case_mgmt (head)   PASS
```

I ran this sequence myself, independently of the implementing agent, against the live `evalforge_test` Postgres database.

**RLS**: unaffected by `ALTER TABLE ... ADD COLUMN` — `datasets`, `test_cases`, `test_case_versions`, `dataset_snapshots`, `dataset_snapshot_items` remain `ENABLE`/`FORCE ROW LEVEL SECURITY` from Migration 0004, verified still true by `test_dataset_migration.py`.

**Tenant-consistent foreign keys**: every new lineage/provenance column is a composite `(id, tenant_id)` foreign key, so a cross-tenant reference cannot be inserted even by a direct repository call bypassing application logic — proven by `test_dataset_transfer_isolation.py`'s two direct-repository tests (`asyncpg.exceptions.ForeignKeyViolationError` on a forged `cloned_from_dataset_id` / `source_test_case_id` pointing at another tenant's row).

**Immutability**: unchanged from Milestone 4 — `test_case_versions` and finalized `dataset_snapshots` are still enforced append-only by privilege absence and the pre-existing `forbid_finalized_snapshot_mutation`/`validate_snapshot_item` triggers. Regression-tested by reusing and not weakening `test_dataset_snapshot_immutability.py`'s existing assertions.

## Dataset Management

`application/dataset_service.py`: `create_dataset`, `get_dataset`, `list_datasets` (tenant-and-optionally-workspace/status-filtered), `update_dataset` (mutable metadata only — name/description/tags/metadata), `archive_dataset` (sets `status='archived'` + `archived_at`; non-destructive, no delete path exists). Every mutation is authorization-checked (`UPDATE_DATASET`/`ARCHIVE_DATASET`/`CREATE_DATASET`) and audited on both success and denial.

Version lifecycle, publication, snapshots, history: unchanged Milestone 4 mechanism (`snapshot_service.py`), now reachable over HTTP (`routes/dataset_snapshots.py`: create draft, add item, finalize, get, list, list items) and extended with `list_snapshots` and comparison.

## Test Cases

Schema: `domain/test_case_content.TestCaseContent` — `input` (required), `expected_output`, `structured_expected_output`, `context_references`, `tags`, `metadata`, `difficulty`, `category`, `safety_labels`, `tool_expectations`, `trajectory_expectations`, each bounded (counts/lengths) in the style already established by `domain/ingestion.py`'s size-bounding. `to_json_dict()`/`from_json_dict()` map to/from the existing `test_case_versions.content` JSONB column; unknown top-level keys are preserved on write and ignored (not rejected) on read, so pre-Milestone-6 content keeps its original hash and readability.

Editing/version behavior: unchanged from Milestone 4 — `create_test_case_version` always inserts a new row; no supported path updates an existing version's content. `test_case_service.py` adds `archive_test_case`, `list_test_cases`, `get_test_case_history` (full version list).

Expected/reference output: both a plain `expected_output` string and a `structured_expected_output` object are supported, per the milestone brief.

Context/source references, labels/tags/metadata, tool/trajectory expectations: all represented as typed, validated fields on `TestCaseContent` (see Domain, above).

## Import / Export

**CSV**: header-row required, `input` mandatory; `expected_output`, `tags` (comma-separated), `category`, `difficulty`, `metadata` (JSON-encoded string), `external_key` optional. Parsed with the stdlib `csv` module only.

**JSONL**: one JSON object per line via the stdlib `json` module only, mapped directly to `TestCaseContent` fields; blank lines skipped without consuming a row index.

**Validation-failure reporting**: every row produces a `ParsedImportRow`/`ImportRecordResult` with row index and, on failure, an explicit error message — never a bare exception.

**Atomicity**: deliberately all-or-nothing. Every record is validated purely (no database access) before any write; if any record fails, the whole import is rejected — `ImportOutcome.committed=False`, nothing written, every row's pass/fail status returned. Only when every record validates does a single database transaction insert every row, tagged with one shared `import_batch_id` and `source='imported'`. This trade-off (documented in `application/dataset_import_service.py`'s module docstring) was chosen over partial-commit specifically so a rejected import leaves the dataset provably unchanged and safe to retry.

**Export**: `domain/export_formatting.py` + `application/dataset_export_service.py` emit the same CSV column schema import accepts (round-trip tested) or JSONL with a deterministic leading header identifying the exported dataset/snapshot id and content hash. Exports a finalized snapshot's frozen items (preferred, immutable) or a dataset's current active test cases if no snapshot is given; ordering is deterministic (`sequence_index` or test-case-ID order). Authorization is read-only (`VIEW_DATASET`/`VIEW_DATASET_SNAPSHOT`).

**Round-trip**: `test_dataset_export.py`/`test_dataset_import.py` exercise export → re-import and assert equivalent content.

## Duplicate Detection

**Definition**: two test-case versions are exact duplicates within one dataset iff their `dedup_hash` values match, where `dedup_hash` is SHA-256 over canonicalized, normalized `input` (whitespace-collapsed/stripped/case-folded for text; canonical JSON for structured input) — reusing `domain/hashing.py`'s existing scheme, no second hashing mechanism. Deterministic and purely structural; no semantic/embedding similarity, per the milestone's explicit exclusion.

**Implementation**: `domain/duplicate_detection.py` (pure) + `application/duplicate_detection_service.py`, which calls `DatasetRepository.list_current_dedup_hashes` — a tenant-and-dataset-scoped query over each active test case's latest version.

**Tenant isolation**: the repository call is scoped to `(tenant_id, dataset_id)`; a duplicate check against another tenant's dataset ID resolves through the same not-found path as any other cross-tenant lookup (`DatasetNotFoundError`), never a partial result or a disclosure. Verified by `test_dataset_tenant_isolation.py`/`test_dataset_duplicate_detection.py`.

## Cloning / Sampling / Splits

**Cloning** (`application/dataset_clone_service.py`): creates a new, independent dataset (`source='cloned'`, `cloned_from_dataset_id`, optional `cloned_from_snapshot_id`) whose test cases and versions are brand-new rows — version numbering restarts at 1 per cloned test case, and the clone can diverge freely from its source afterward. Cloning from a finalized snapshot copies frozen content; cloning without one copies each active test case's current latest version. The source dataset (and snapshot, if given) is resolved through the caller's own tenant-scoped repository call, so a cross-tenant source is simply not found — never a second, discriminating check that could leak existence. Source history is never mutated.

**Sampling/splitting** (`domain/sampling.py` + `application/dataset_sampling_service.py`): `deterministic_sample`/`deterministic_split` rank items by `sha256(f"{seed}:{item_id}")` — never Python's `random` module — so the same seed and input set always reproduce the same result, proven by literal repeated-call assertions in `test_sampling_domain.py`/`test_dataset_sampling_service.py`. Both operate only on a *finalized* snapshot's frozen item list (stability requirement — a draft's membership can still change), and neither persists a new record: the seed and the immutable snapshot identifier together are the reproducibility guarantee, consistent with "dataset-management primitives only," not new experiment infrastructure.

## Security

**RBAC**: `UPDATE_DATASET`, `ARCHIVE_DATASET`, `CLONE_DATASET`, `IMPORT_TEST_CASES` added to `domain/actions.py`'s `_EVALUATION_ENGINEER_MUTATIONS` set; `tenant_admin` inherits them through the existing set union. Read paths (list/get/history/compare/sample/export/duplicate-check) reuse `VIEW_DATASET`/`VIEW_DATASET_SNAPSHOT`, preserving the "every role may view evidence" convention. `test_dataset_authorization.py` exercises every new action against every role — `reviewer`/`read_only_observer` denied, `evaluation_engineer`/`tenant_admin` allowed. No route or service compares role strings directly; every check goes through `TenantContext.can()`.

**RLS / tenant isolation**: `test_dataset_tenant_isolation.py` (read/update/archive/list on datasets and test cases) and `test_dataset_transfer_isolation.py` (export/import/clone, plus two direct-repository tests proving the composite foreign keys reject a forged cross-tenant provenance reference even bypassing the application layer) cover the full negative list from the milestone brief: Tenant A cannot read, mutate, clone, compare, export, or duplicate-check against Tenant B's datasets or test cases; import cannot target or reference another tenant's dataset; every cross-tenant lookup returns "not found," never a distinguishing error.

**Import/export safety**: CSV/JSONL parsing uses only the stdlib `csv`/`json` modules — no `eval`, `exec`, or deserialization of executable content.

**Error responses**: `routes/dataset_error_mapping.py` maps every known dataset-management exception to the pre-existing standardized error envelope (403/404/409/413/422); anything unrecognized falls through to the unchanged Milestone 2 catch-all handler, which never leaks internals.

## Audit

`emit_audit_event` (Milestone 2's redaction-processor-backed audit logger, unchanged) is called on both success and denial for: dataset creation/update/archive, test-case creation/version-creation/archive, snapshot draft creation/item addition/finalization (unchanged from Milestone 4), duplicate-check, snapshot comparison, sampling/split, clone, and import (including a `rejected` outcome distinct from `denied`/`success` when validation fails). Every event carries actor, tenant, action, affected resource ID(s), and relevant counts/hashes/version numbers — never raw content, raw import documents, or credentials.

## Validation

I ran every command myself in this session, independently of the implementing agent, against the real Postgres/MinIO test stack (`make test-services-up`).

**Environment notes**:

1. `services/api/.venv`'s three `.pth` files (`_editable_impl_evalforge_api.pth`, `a1_coverage.pth`, `pytest-cov.pth`) are repeatedly marked with the macOS `hidden` file flag by a background sync/backup process operating on this directory (the same process that left a stray superseded duplicate file in the working tree at session start — see Preflight). Python 3.13 skips hidden `.pth` files at startup, so the editable install of `evalforge_api` is inert unless `PYTHONPATH=services/api/src` is set explicitly; `chflags nohidden` clears the flag but it is reapplied by the background process within seconds. This is a pre-existing host/environment condition unrelated to Milestone 6's code — I confirmed it via `python -v` verbose import tracing ("Skipping hidden .pth file") — and I ran every backend command below with `PYTHONPATH=services/api/src` as the documented workaround, exactly as the implementing agent did. The `Makefile`'s `make validate` target itself does not set this variable, so a fresh `make validate` invocation on this host will fail to import `evalforge_api` until either the sync process is disabled for this directory or the venv is recreated outside its scope; every constituent check `make validate` aggregates was nonetheless run and passed individually, below.
2. `apps/web`'s `npm run lint` and `npm run typecheck` were started but did not complete within this session: both processes (`eslint .`, `tsc --noEmit`) remained alive for 9–11 minutes at 0.0% CPU, evidently starved by roughly a dozen unrelated background processes already running on this host from other, unrelated sessions/projects. I did not fabricate a pass for these. Milestone 6 made no change to any file under `apps/web` — the frontend was last independently verified passing (`eslint`, `prettier --check`, `tsc --noEmit`, `vitest`) in the Milestone 5 session — so the risk of an undetected regression is low, but this is recorded honestly as an incomplete check rather than a claimed pass, per this task's validation-reporting requirement. The owner should re-run `cd apps/web && npm run lint && npm run typecheck && npm test` on a less contended host or at a quieter time before final acceptance.

| Command | Result |
|---|---|
| `ruff check src tests alembic` | All checks passed |
| `ruff format --check src tests alembic` | 177 files already formatted |
| `mypy src` | Success: no issues found in 108 source files |
| `pytest` | **340 passed**, 0 failed, 7 warnings, 90% coverage |
| `python3 scripts/validate_modularity.py` | passed — no file exceeds 300 lines |
| `python3 scripts/validate_dependency_boundaries.py` | passed |
| `python3 scripts/validate_circular_imports.py` | passed |
| `python3 scripts/validate_forbidden_filenames.py` | passed |
| `python3 scripts/validate_no_secrets.py` | passed |
| `python3 scripts/validate_markdown_links.py` | passed |
| `alembic upgrade head` / `downgrade 0008_evidence_idempotency` / `upgrade head` | all passed (live test database) |
| `apps/web`: `npm run lint`, `npm run typecheck`, `npm test` | **not completed in this session** — see note below |

New test files (18) and their focus: `test_test_case_content_domain.py`, `test_duplicate_detection_domain.py`, `test_snapshot_comparison_domain.py`, `test_sampling_domain.py` (pure domain, no DB); `test_dataset_lifecycle.py`, `test_test_case_lifecycle.py`, `test_dataset_duplicate_detection.py`, `test_dataset_import.py`, `test_dataset_export.py`, `test_dataset_clone.py`, `test_dataset_clone_boundaries.py`, `test_dataset_snapshot_comparison_service.py`, `test_dataset_sampling_service.py`, `test_dataset_migration.py`, `test_dataset_authorization.py` (application/persistence, real Postgres); `test_dataset_tenant_isolation.py`, `test_dataset_transfer_isolation.py` (security/negative); `test_dataset_routes.py`, `test_dataset_snapshot_routes.py`, `test_dataset_operation_routes.py` (HTTP-level via `TestClient`). `dataset_fixtures.py` holds shared two-tenant test bootstrap helpers (not a generic dumping-ground module — scoped entirely to dataset test setup).

**Regression**: all 322 pre-existing Milestone 0–5 tests continue to pass unchanged in substance. Two migration-head-pinning tests were updated using the exact precedent already established at the Milestone 4→5 boundary: `test_ingestion_migration.py`'s head-revision pin became a schema-existence check (the head moved past `0008_evidence_idempotency`); `test_evaluation_migration.py`'s UPDATE-grant assertion now expects `{dataset_snapshots, datasets, test_cases}` instead of `{dataset_snapshots}` alone, because this milestone explicitly authorizes those two new grants. Neither change weakens an assertion — both track a state change this milestone deliberately makes. `test_dataset_migration.py` now pins the exact head revision `0009_dataset_test_case_mgmt`.

## Deviations From the Original Task Brief (recorded for owner review)

1. Three port/repository methods were added beyond my initial specification to the implementing agent, all necessary consequences of the atomicity and clone/export requirements: `create_test_cases_with_versions` (single-transaction bulk insert for import, keeping the connection pool out of the application layer), `list_latest_versions_for_dataset` (clone-from-current-state and export), and the `TestCaseSeedRow` dataclass.
2. `ports/datasets.py` was split (snapshot-side types moved to a new `ports/dataset_snapshots.py`) to stay under the 300-line ceiling once the new dataset/test-case methods were added — an explicitly pre-authorized option.
3. A dataset-domain-specific error-mapping module (`routes/dataset_error_mapping.py`) was added rather than extending `routes/ingestion_error_mapping.py`, because the latter imports Milestone 5 ingestion services directly and widening it would have coupled two unrelated route families.
4. Two routes were added beyond the initial enumeration: `POST /datasets/{id}/duplicate-check` (the duplicate-detection service otherwise had no HTTP path) and `GET /snapshot-comparisons?left=&right=` (a query-parameter form, to avoid colliding with the `/snapshots/{id}` path pattern). Both fall squarely within the milestone's authorized "expose... through the established... API architecture" scope and implement functionality explicitly required by the brief (duplicate detection, snapshot comparison) — no new concept was introduced.

None of these deviations expand scope beyond what Sections 6–16 of the authorizing brief require; each is a narrower implementation path chosen to satisfy an explicit requirement without duplicating existing machinery.

## Documentation

Updated: `docs/DOMAIN_MODEL.md` (new "Implementation Notes (Milestone 6)" section, matching the Milestone 4 section's style); this report. `README.md` and `docs/ROADMAP.md` milestone-status lines are updated in the same commit (see Git, below) to "implemented and validated; pending owner review," matching the Milestone 5 precedent before its approval.

## Files Changed

- **Migration**: `services/api/alembic/versions/20260817_0009_dataset_test_case_management.py` (new).
- **Backend domain** (`services/api/src/evalforge_api/domain/`): `test_case_content.py`, `import_parsing.py`, `export_formatting.py`, `sampling.py`, `duplicate_detection.py`, `snapshot_comparison.py` (new); `actions.py` (extended).
- **Backend ports** (`ports/`): `dataset_snapshots.py` (new); `datasets.py`, `evaluation_repositories.py` (extended).
- **Backend adapters** (`adapters/`): `test_case_version_repository.py`, `dataset_row_mapping.py` (new); `dataset_repository.py`, `dataset_snapshot_repository.py` (extended).
- **Backend application** (`application/`): `test_case_service.py`, `dataset_errors.py`, `duplicate_detection_service.py`, `snapshot_comparison_service.py`, `dataset_sampling_service.py`, `dataset_clone_service.py`, `dataset_import_service.py`, `dataset_export_service.py` (new); `dataset_service.py`, `snapshot_service.py`, `lineage_service.py` (extended).
- **Backend routes** (`routes/`): `datasets.py`, `test_cases.py`, `dataset_snapshots.py`, `dataset_import_export.py`, `dataset_operations.py`, `dataset_error_mapping.py`, `dataset_response_models.py` (new); `app.py` (5 routers registered).
- **Backend tests**: 18 new files (listed under Validation, above); `dataset_fixtures.py` (new shared fixture module); `test_evaluation_migration.py`, `test_ingestion_migration.py` (updated per the precedented migration-head-pin pattern).
- **Docs**: `docs/DOMAIN_MODEL.md`; this report; `README.md`, `docs/ROADMAP.md` (milestone-status lines).
- **Removed**: the stray untracked `services/api/src/evalforge_api/middleware/request_size_limit 2.py` (was never tracked; not part of this commit's diff).

## Explicit Exclusions

Confirmed not implemented: Milestone 7 experiment execution/scheduling/worker orchestration; Milestone 8+ deterministic, model-judge, or human-review evaluators; RAG, tool-use, or agent-trajectory evaluation *execution*; comparison/regression/quality-gate engines; annotation or human-labeling UI; a dataset marketplace; semantic/embedding-based duplicate detection; new distributed locking; production model-training pipelines; broad dashboards or unrelated frontend work; unrelated infrastructure changes. Sampling/split results are deliberately not persisted, to avoid introducing experiment-adjacent state ahead of Milestone 7.

## Residual Risks

- The macOS-hidden-`.pth`/sync-process environment issue described under Validation is a host condition, not a code defect; it affects local developer ergonomics (`make validate` needs `PYTHONPATH` set until resolved) but not CI (GitHub Actions runners are not subject to this local sync process) or runtime behavior.
- `dedup_hash` defaults to `''` for any hypothetical pre-migration row; no production data exists yet, so this is a schema-correctness note rather than a live data-quality concern. `dataset_clone_service` recomputes a real hash whenever it encounters an empty one.
- Sampling/splitting requires a *finalized* snapshot by design (stability); a caller wanting to preview a sample over in-progress draft content must finalize a snapshot first — a deliberate constraint, not a gap.

No known critical or high-severity Milestone 6 security flaw remains unresolved.

## Git

- Commit message: `feat: implement dataset and test-case management`
- The commit is local only at report-writing time; push result recorded in the closure message that accompanies this report.

Related documents: [Roadmap](ROADMAP.md), [Domain Model](DOMAIN_MODEL.md), [Reproducibility Contract](REPRODUCIBILITY_CONTRACT.md), [Tenancy and Authorization](TENANCY_AND_AUTHORIZATION.md), [Milestone Acceptance](MILESTONE_ACCEPTANCE.md), [Milestone 4 Completion Report](MILESTONE_4_COMPLETION_REPORT.md), [Milestone 5 Completion Report](MILESTONE_5_COMPLETION_REPORT.md).
