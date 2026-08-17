"""Dataset-scoped duplicate detection.

Read-shaped: it answers "does this dataset already contain this exact
test case?" against the caller's own tenant only. ``VIEW_DATASET`` is
therefore the correct permission — no data is written and nothing
outside the caller's tenant is reachable, because the repository call
is tenant-scoped and RLS enforces the same boundary independently.

A dataset ID belonging to another tenant simply yields an empty
mapping, which is indistinguishable from an empty dataset — the check
cannot be used to probe for the existence of another tenant's data.
"""

from __future__ import annotations

from uuid import UUID

from evalforge_api.application.dataset_errors import AuthorizationDeniedError
from evalforge_api.domain.actions import TenantAction
from evalforge_api.domain.duplicate_detection import compute_dedup_hash, find_duplicate_ids
from evalforge_api.domain.tenant_context import TenantContext
from evalforge_api.domain.test_case_content import TestCaseContent
from evalforge_api.ports.evaluation_repositories import EvaluationRepositories


async def check_for_duplicates(
    *,
    context: TenantContext,
    dataset_id: UUID,
    content: TestCaseContent,
    repositories: EvaluationRepositories,
) -> tuple[UUID, ...]:
    """Every active test case in ``dataset_id`` whose current content is
    an exact duplicate of ``content``, in deterministic ID order."""
    if not context.can(TenantAction.VIEW_DATASET):
        raise AuthorizationDeniedError("Not authorized to inspect this dataset.")

    existing = await repositories.datasets.list_current_dedup_hashes(
        tenant_id=context.tenant_id, dataset_id=dataset_id
    )
    return find_duplicate_ids(compute_dedup_hash(content), dict(existing))
