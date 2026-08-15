# Milestone 4 Completion Report

Date: 2026-08-15.

## Repository Identity

- Remote: `https://github.com/bmsmithtx-svg/evalforge.git`
- Branch: `main`
- Starting commit: `6a9ca92131555c3eb2891fd15d69a7e54817b2be` (Milestone 3 implementation; owner-approved baseline per this milestone's authorization)
- Final local commit: recorded in [Git](#git) below, after this report is committed.

## Roadmap Status

- Milestone 0: Approved.
- Milestone 1: Approved.
- Milestone 2: Approved.
- Milestone 3: Approved (owner approval recorded 2026-08-15, per this milestone's authorization).
- Milestone 4: Implemented and validated; owner review pending.
- Milestones 5–15: Not started.

## Owner Approval

Milestone 4 (Versioned Evaluation Domain and Persistence) was authorized and implemented in this session. It is not yet owner-approved; this report is submitted for owner review. Milestone 5 has not been started.

## Scope Implemented

Milestone 4 implements the persistent, tenant-scoped, versioned domain and persistence substrate required to make later evaluation work reproducible and auditable: workspaces and evaluation targets; a unified versioned-configuration mechanism covering model, prompt, retrieval, tool, workflow, evaluator, and pricing versions; versioned test cases; immutable, hash-verified dataset snapshots; artifact metadata backed by tenant-scoped S3-compatible object storage; explicit relational lineage; retention metadata; PostgreSQL row-level security and database-enforced immutability on every new table; and audit-event integration for every material operation.

No new public API routes were added. The milestone brief explicitly allows "snapshot creation/finalization... as an internal application service," and warns against "broad product CRUD merely to demonstrate persistence." Milestone 4 is proved through internal application services, direct repository/adapter tests, and PostgreSQL/object-storage integration tests — not through a premature product API. Experiment execution, trace ingestion, evaluators, dataset-management UI, and every other later-milestone concern were not implemented.

## Domain Model

Logical/versioned entities implemented, matching [Domain Model](DOMAIN_MODEL.md) terminology (see that document's new "Implementation Notes (Milestone 4)" section for the full mapping):

- Workspace (`workspaces`)
- Evaluation target (`evaluation_targets`)
- Model, prompt, retrieval-configuration, tool-definition, workflow, evaluator, and pricing versions — unified as `versioned_resources` (logical identity) / `versioned_resource_versions` (immutable version identity), discriminated by `ResourceKind`
- Dataset (`datasets`)
- Test case (`test_cases` / `test_case_versions`)
- Dataset version / immutable snapshot (`dataset_snapshots` / `dataset_snapshot_items`)
- Artifact (`artifacts` / `artifact_versions`)

Every versioned entity separates a stable logical-resource identity from an immutable version identity with a per-resource sequential `version_number`; no supported path rewrites an existing version's content. Deferred entities (experiment, variant, run, attempt, trace, span, evaluation result, metric observation, human review, adjudication, comparison, regression finding, quality gate) remain conceptual, per the roadmap.

## Database

**Migrations** (all under `services/api/alembic/versions/`, each ≤300 physical lines per the modularity standard):

- `20260815_0003_evaluation_domain_workspaces_and_resources.py` — `resource_kind`, `versioned_resource_status`, `workspace_status`, `evaluation_target_status`, `retention_class` enum types; `workspaces`, `evaluation_targets`, `versioned_resources`, `versioned_resource_versions` tables; a `validate_resource_version_lineage` trigger.
- `20260815_0004_evaluation_domain_datasets_and_snapshots.py` — `dataset_status`, `test_case_status`, `dataset_snapshot_status` enum types; `datasets`, `test_cases`, `test_case_versions`, `dataset_snapshots`, `dataset_snapshot_items` tables; `forbid_finalized_snapshot_mutation` and `validate_snapshot_item` triggers.
- `20260815_0005_evaluation_domain_artifacts.py` — `artifact_status` enum type; `artifacts`, `artifact_versions` tables; a `validate_artifact_version_lineage` trigger.

Chained after `0002_identity_and_tenancy`; head is `0005_eval_domain_artifacts`. Every migration has a tested `downgrade()`.

**Constraints and integrity**: every child table's foreign key to its parent is a **composite `(id, tenant_id)` foreign key** against a `UNIQUE (id, tenant_id)` constraint on the parent — the primary mechanism preventing cross-tenant lineage at the database level, independent of RLS or application code. Self-referential `derived_from_version_id` / `derived_from_artifact_version_id` columns are also composite-tenant foreign keys, backstopped by `BEFORE INSERT` triggers (`validate_resource_version_lineage`, `validate_artifact_version_lineage`) that additionally reject a derivation crossing *logical resource/artifact* boundaries within the same tenant — a case the composite foreign key alone does not catch. `CHECK` constraints enforce positive version numbers and non-negative byte sizes; `UNIQUE` constraints enforce per-resource sequential version numbers, per-snapshot sequence-index and membership uniqueness, and a globally unique artifact storage key.

**Immutability mechanisms**:

- No table grants `DELETE` to the request-serving `evalforge_app` role.
- No table grants `UPDATE` except `dataset_snapshots`, and only for the draft-to-finalized transition.
- A `BEFORE UPDATE` trigger (`forbid_finalized_snapshot_mutation`) rejects any update to a `dataset_snapshots` row once `status = 'finalized'`.
- A `BEFORE INSERT` trigger (`validate_snapshot_item`) rejects a new `dataset_snapshot_items` row unless the parent snapshot is still `draft`, and rejects a test-case version that does not belong to the snapshot's own dataset.
- Version rows (`versioned_resource_versions`, `test_case_versions`, `artifact_versions`) are immutable purely by privilege absence — the only supported write is `INSERT`.

**RLS**: every new tenant-owned table has `ENABLE`/`FORCE ROW LEVEL SECURITY` with a single `FOR ALL` policy keyed on the transaction-local `app.current_tenant_id` setting, matching the Milestone 3 pattern exactly. `evalforge_app` remains non-superuser, without `BYPASSRLS`, and is never used to serve migrations.

**Indexes**: added on every foreign-key column used in lookups (`workspace_id`, `dataset_id`, `test_case_id`, `resource_id`, `artifact_id`, `snapshot_id`, tenant/kind composite).

## Hashing and Snapshot Semantics

- **Algorithm**: SHA-256 (`evalforge_api.domain.hashing.HASH_ALGORITHM`), recorded alongside every hash — never Python's process-randomized `hash()`.
- **Canonicalization**: structured JSON content is serialized with recursively sorted keys, fixed separators, and ASCII-escaped output (`canonicalize_json`) before hashing, tagged with a `canonicalization_version` string (`json-canonical-v1`) so a later canonicalization change is distinguishable from a content change. Artifact bytes hash directly.
- **Snapshot membership**: `dataset_snapshot_items` freezes one row per included test-case version with an explicit `sequence_index` for deterministic ordering.
- **Finalization**: `evalforge_api.application.snapshot_service.finalize_snapshot` computes the snapshot's content hash over the frozen `(test_case_id, test_case_version_id, version_number, content_hash)` membership list, then transitions the snapshot to `finalized` in one database update guarded by the immutability trigger above.
- **Immutability**: proven by test — `test_dataset_snapshot_immutability.py::test_finalized_snapshot_is_unchanged_after_dataset_evolves` builds Dataset A, finalizes Snapshot 1, revises a test case to a new version, finalizes Snapshot 2, and asserts Snapshot 1's membership and hash are byte-for-byte unchanged while Snapshot 2 has a distinct identity and hash.
- **Lineage**: `evalforge_api.application.lineage_service` walks `derived_from_version_id` / `derived_from_artifact_version_id` chains and snapshot membership under verified tenant context.

## Artifact Storage

PostgreSQL (`artifacts`, `artifact_versions`) holds metadata, content hash, byte size, content type, and the object-storage key; `evalforge_api.adapters.artifact_object_storage.S3ArtifactObjectStorage` (boto3, reusing the Milestone 2 S3-compatible foundation) holds bytes. `evalforge_api.application.artifact_service` constructs every storage key from server-verified `tenant_id` plus the computed content hash — never from caller input — as `tenants/{tenant_id}/artifacts/{artifact_id}/versions/{version_number}-{content_hash}`; objects are never written with a public ACL. No public upload/ingestion API was added, per the milestone's explicit exclusion. `retrieve_and_verify_artifact_version` re-hashes retrieved bytes and raises `ArtifactHashMismatchError` on a mismatch rather than returning unverified content.

## Tenant Isolation

Defense-in-depth, matching Milestone 3 exactly:

- **Application layer**: every application-service function takes a `TenantContext` built only from server-verified identity and checks `context.can(action)` against the centralized `TenantAction` permission table before any mutation; every repository call takes `tenant_id` as an explicit parameter, never inferred from payload content.
- **Persistence layer**: RLS on every table plus composite tenant-consistent foreign keys (above).

Validation evidence (`services/api/tests/test_evaluation_tenant_isolation.py`, `test_dataset_snapshot_immutability.py`, `test_artifact_storage.py`):

- Tenant A cannot read Tenant B's versioned resource by ID (`get_resource` returns `None`).
- Tenant A cannot attach Tenant B's test-case version to its own snapshot (rejected by the `validate_snapshot_item` trigger — RLS hides Tenant B's row from the trigger's own lookup, so it raises before the composite foreign key is even reached).
- Tenant A cannot reference Tenant B's artifact version as lineage (rejected by the `validate_artifact_version_lineage` trigger for the same reason; the composite foreign key remains an independent second barrier).
- Substituting a random UUID for a real resource ID returns `None`, not an error that would distinguish "doesn't exist" from "exists but not yours."
- Direct database access through `evalforge_app` with no `app.current_tenant_id` session setting returns zero rows from every Milestone 4 table, despite real data existing.
- The application role has no `DELETE` grant on any Milestone 4 table, and no `UPDATE` grant except `dataset_snapshots` (verified by querying `information_schema.role_table_grants`).

## Authorization

`services/api/src/evalforge_api/domain/actions.py` extends the single, deny-by-default `TenantAction` permission table with: `create_workspace` / `view_workspace`, `create_evaluation_target` / `view_evaluation_target`, `create_versioned_resource` / `view_versioned_resource`, `create_dataset` / `view_dataset`, `create_test_case`, `finalize_dataset_snapshot` / `view_dataset_snapshot`, `create_artifact` / `view_artifact`. Every role may view every evaluation-domain concept. `tenant_admin` and `developer` may create workspaces (workspace-only, standing in for the not-yet-implemented workspace-administrator role), evaluation targets, and versioned configuration resources. `tenant_admin` and `evaluation_engineer` may create datasets, test cases, and finalize snapshots. `reviewer` and `read_only_observer` have no evaluation-domain mutation rights. No route, repository, or adapter compares role strings directly — every check goes through `TenantContext.can()`.

## Audit

Every application-service function emits a structured audit event (`evalforge_api.audit.emit_audit_event`, inheriting Milestone 2's log-redaction processor) on both success and denial: workspace/target/resource/dataset/test-case/artifact creation, version creation, snapshot draft creation, item addition (including `denied_immutable` when the trigger rejects a mutation), snapshot finalization, and artifact retrieval (including `hash_mismatch`). No audit event embeds raw content, artifact bytes, or credentials — only tenant, actor, resource, and hash/count metadata.

## Tests

**Backend** (`services/api`, `pytest`): **107 passed, 0 failed.** Coverage 88% (`--cov=evalforge_api`); uncovered lines are pre-existing network-failure branches in connectivity adapters, `dev_seed.py` (a manually invoked script), and a handful of not-yet-exercised repository/service branches consistent with the coverage profile of prior milestones.

New test files:

- `test_hashing.py` (7) — canonicalization determinism, key-order invariance, content-change sensitivity, SHA-256 pinning against a reference implementation.
- `test_versioning.py` (10) — version numbering, lineage validation, draft/immutability rules.
- `test_evaluation_authorization.py` (6) — every new `TenantAction` against every role.
- `test_evaluation_migration.py` (6) — head revision, table existence, composite foreign keys, RLS enabled/forced on every table, `DELETE`/`UPDATE` grant absence.
- `test_evaluation_versioning.py` (6) — version increment/immutability, cross-resource lineage rejection (application layer and, independently, the database trigger), authorization denial, ancestry traversal.
- `test_dataset_snapshot_immutability.py` (3) — the full Dataset A → Snapshot 1 → mutate → Snapshot 2 scenario; rejected post-finalization membership changes; a direct SQL `UPDATE` blocked by the trigger.
- `test_evaluation_tenant_isolation.py` (5) — cross-tenant read/write/lineage rejection, UUID substitution, RLS default-deny across every table.
- `test_artifact_storage.py` (5) — round-trip store/retrieve/verify against live MinIO, tenant-scoped keys, cross-tenant retrieval denial, hash-mismatch detection, authorization denial.

All 60 pre-existing Milestone 2/3 tests continue to pass unchanged, with one intentional update: `test_membership_repository.py`'s migration-head test now checks that the identity/tenancy schema exists (`to_regclass`) rather than pinning the exact head revision string, since the head has moved past `0002_identity_and_tenancy`; the exact head is now pinned by `test_evaluation_migration.py`.

**Frontend** (`apps/web`, `vitest`): 13 passed, 0 failed, across 3 files — unchanged, no frontend files were modified.

## Static Analysis

- `ruff check` (`services/api/src tests alembic`): passed.
- `ruff format --check`: passed (90 files).
- `mypy --strict` (`services/api/src`, 62 source files): passed, no issues.
- `eslint .` (`apps/web`): passed.
- `prettier --check .` (`apps/web`): passed.
- `tsc --noEmit` (`apps/web`): passed.

## Docker / Integration Verification

`infrastructure/docker-compose.test.yml` gained an `object-storage-test` (MinIO) service and an `object-storage-test-init` one-shot bucket-creation service, matching `services/api/tests/conftest.py`'s pre-existing test-settings expectations (`localhost:9100`, bucket `evalforge-test`). While wiring this in, `make test-services-up` (`docker compose up -d --wait`) was found to fail against the new one-shot init container — Compose's `--wait` does not tolerate a `restart: "no"` container that exits 0 in this environment's Compose version, even though the main `docker-compose.yml`'s equivalent `object-storage-init` pattern has always worked without `--wait`. Fixed by waiting only on the two long-running, health-checked services and running the init container via `docker compose run --rm`, which is designed for one-shot completion. This is a genuine, reproducible fix (`make validate` failed before it and passes after), not a workaround.

Live-verified against this fixed test stack: the evaluation-domain Alembic migrations apply to a clean database reached via the Milestone 2/3 baseline (`alembic upgrade head`, and `alembic downgrade 0002_identity_and_tenancy` followed by re-`upgrade head`, both succeeded); the full backend test suite (above) ran against real PostgreSQL and real MinIO, exercising every RLS policy, every immutability trigger, and real S3-compatible object storage round trips — not mocks.

The main `docker-compose.yml` development stack (API/web containers, full `make up`) could not be rebuilt in this session: pulling the `python:3.13-slim` and `node:22-slim` base images from Docker Hub did not complete despite the registry being reachable (`curl` to `registry-1.docker.io` succeeded) and other images (`postgres:17-alpine`, `minio/minio`, `minio/mc`) pulling normally — most likely because those images were already cached locally from prior Milestone 2/3 sessions on this machine, while `python`/`node` were not. Milestone 4 added no new HTTP routes and no changes to `app.py`'s existing health/readiness behavior beyond wiring the new repositories into `app.state` at startup, so the residual risk from not rebuilding the full container stack is low; it is recorded honestly below rather than claimed as verified. `services/api/tests/test_readiness.py` and the full Milestone 3 auth/tenant-isolation suite continue to pass unchanged, confirming Milestone 3 behavior is preserved.

## Validation

`make validate` (lint, format-check, typecheck, `pytest`, `vitest`, modularity, forbidden-filenames, markdown-link, dependency-boundary, circular-import, secret-scan) **passed in full**, including the fixed `test-services-up` dependency described above.

## Security Review

Reviewed and evidenced by test:

- **Cross-tenant reads/writes/foreign-key attacks**: composite `(id, tenant_id)` foreign keys make a cross-tenant reference fail to insert; RLS independently hides cross-tenant rows from ordinary queries and from the lineage-validation triggers' own lookups. Both layers are exercised by `test_evaluation_tenant_isolation.py`.
- **UUID substitution**: proven not to distinguish "does not exist" from "exists but not yours" (`get_resource`/`get_dataset` return `None` either way).
- **RLS bypass**: every new table has both `ENABLE` and `FORCE ROW LEVEL SECURITY`, so even the table-owning migration role would not bypass it; the request-serving role is a separate non-superuser role without `BYPASSRLS`, verified by direct-connection tests.
- **Application-role privilege escalation**: `information_schema.role_table_grants` queried directly in tests to confirm no `DELETE` grant anywhere and no `UPDATE` grant outside `dataset_snapshots`.
- **Mutable immutable-record paths**: a direct SQL `UPDATE` against the least-privilege role is blocked by the `forbid_finalized_snapshot_mutation` trigger, independent of the application service.
- **Object-storage tenant isolation and path/key injection**: storage keys are always server-constructed from a UUID, another UUID, an integer, and a hex hash — no caller-supplied string ever reaches a storage key, so path traversal or cross-tenant key guessing is not possible through the implemented paths. No public upload endpoint exists to attack.
- **Hash spoofing/mismatch handling**: `retrieve_and_verify_artifact_version` re-hashes on every read and raises rather than returning tampered content silently; proven by test with an intentionally mismatched recorded hash.
- **Log/exception leakage**: audit events carry only IDs, hashes, and counts — never raw content or bytes; unhandled exceptions still flow through Milestone 2's catch-all handler, which returns only a generic message and an `error_id`.
- **Committed secrets**: `scripts/validate_no_secrets.py` passed; the new MinIO test credentials (`test-access-key` / `test-secret-key`) are synthetic, local-test-only values in the same category as the pre-existing `evalforge-test` Postgres password.

**Findings and remediation performed during this review** (not residual — fixed before this report):

1. A version's `derived_from_version_id` / `derived_from_artifact_version_id` composite foreign key only guarantees the same *tenant*, not the same logical *resource/artifact* — a bug bypassing the application-layer `validate_lineage_within_resource` check could otherwise attach one resource's version history to an unrelated resource within the same tenant. Remediated by adding `validate_resource_version_lineage` and `validate_artifact_version_lineage` `BEFORE INSERT` triggers, independent of the application layer, and covered by `test_database_trigger_rejects_cross_resource_lineage_even_bypassing_the_domain_check`.
2. `make test-services-up` failed unconditionally once the MinIO init container was added (Docker Compose `--wait` incompatibility, described above). Remediated in the `Makefile`; not a security finding but a correctness/availability defect that would have broken every future `make validate`/CI run.

**Residual risks** (not remediated in this milestone, out of scope, or deferred by design):

- `content: dict[str, Any]` for versioned-resource and test-case content has no schema validation yet — malformed content (e.g., NaN, non-JSON-serializable values) surfaces as an unhandled encoding error rather than a structured validation error. Low severity today because no untrusted HTTP route exists yet to reach this code; Milestone 5/6 ingestion APIs must add input validation at their boundary before accepting untrusted content.
- `store_artifact_version` accepts `bytes` with no explicit size ceiling of its own; Milestone 2's `RequestSizeLimitMiddleware` only protects HTTP request bodies, and no HTTP route calls this yet. A future ingestion API must apply an explicit artifact-size limit.
- The main `docker-compose.yml` development stack (API/web containers) was not rebuilt and live-verified this session, per the Docker/Integration Verification section above; a future session should verify it once the base-image pull succeeds.

No known critical or high-severity Milestone 4 security flaw remains unresolved.

## Documentation

Updated: `README.md` (status, new paragraph, doc index); `docs/ROADMAP.md` (Milestone 3 → Approved, Milestone 4 → implemented/pending review); `docs/DOMAIN_MODEL.md` (new "Implementation Notes (Milestone 4)" section); `docs/REPRODUCIBILITY_CONTRACT.md` (new "Implementation Notes (Milestone 4)" section); `docs/TENANCY_AND_AUTHORIZATION.md` (new "Implementation Notes (Milestone 4)" section); this report.

## Files Changed

- **Backend domain** (`services/api/src/evalforge_api/domain/`): `evaluation_enums.py`, `hashing.py`, `versioning.py` (new); `actions.py` (extended).
- **Backend ports** (`services/api/src/evalforge_api/ports/`): `workspaces.py`, `versioned_resources.py`, `datasets.py`, `artifacts.py`, `evaluation_repositories.py` (new).
- **Backend adapters** (`services/api/src/evalforge_api/adapters/`): `rls_session.py`, `workspace_repository.py`, `versioned_resource_repository.py`, `dataset_repository.py`, `dataset_snapshot_repository.py`, `artifact_repository.py`, `artifact_object_storage.py` (new).
- **Backend application** (`services/api/src/evalforge_api/application/`): `workspace_service.py`, `versioned_resource_service.py`, `dataset_service.py`, `snapshot_service.py`, `artifact_service.py`, `lineage_service.py` (new).
- **Backend wiring**: `dependency_wiring.py`, `app.py` (extended).
- **Migrations**: `services/api/alembic/versions/20260815_0003_*`, `0004_*`, `0005_*` (new).
- **Backend tests**: 8 new test files (above); `conftest.py` (extended — `evaluation_repositories`, `create_user`, `build_tenant_context` fixtures); `test_membership_repository.py` (one test updated).
- **Infrastructure**: `infrastructure/docker-compose.test.yml` (MinIO test service); `Makefile` (`test-services-up` fix).
- **Docs**: as listed above.

## Explicit Exclusions

Confirmed not implemented: Milestone 5 SDK/ingestion functionality; trace/span persistence; experiment execution or scheduling; worker orchestration; deterministic, model-judge, or human-review evaluators; RAG, tool-use, or agent-trajectory evaluation; regression/comparison/quality-gate engines; dashboards or trace-inspection UI; CI/CD deployment gates; dataset/test-case management UI or full CRUD; external identity-provider integration; service-identity provisioning; broad frontend redesign. No public HTTP routes were added for any Milestone 4 concept.

## Residual Risks

See the Security Review section above for the complete, evidenced list.

## Git

- Commit message: `feat: implement versioned evaluation domain and persistence`
- The commit is local only; it has not been pushed to `origin/main`. The owner will review this report and authorize the push separately.

Related documents: [Roadmap](ROADMAP.md), [Domain Model](DOMAIN_MODEL.md), [Reproducibility Contract](REPRODUCIBILITY_CONTRACT.md), [Tenancy and Authorization](TENANCY_AND_AUTHORIZATION.md), [Milestone Acceptance](MILESTONE_ACCEPTANCE.md), ADR [0002](adr/0002-versioned-artifacts-and-immutable-run-snapshots.md), ADR [0004](adr/0004-tenant-isolation-and-data-ownership.md).
