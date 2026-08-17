"""Application-layer error vocabulary for dataset management.

Milestone 6 splits dataset management across several concept-scoped
application services (authoring, lifecycle, duplicates, cloning,
import, export, sampling, comparison). They share one error vocabulary
so the delivery layer has a single, unambiguous mapping to HTTP status
codes (``evalforge_api.routes.dataset_error_mapping``) instead of one
near-identical exception class per module.

Every not-found error here is deliberately undifferentiated: a
repository lookup is always tenant-scoped, so "belongs to another
tenant" and "does not exist" are indistinguishable to the caller by
construction (docs/TENANCY_AND_AUTHORIZATION.md).
"""

from __future__ import annotations


class AuthorizationDeniedError(Exception):
    """The caller's role does not permit the requested dataset action."""


class DatasetNotFoundError(Exception):
    """No dataset with this ID exists within the caller's tenant."""


class TestCaseNotFoundError(Exception):
    """No test case with this ID exists within the caller's tenant."""


class SnapshotNotFoundError(Exception):
    """No dataset snapshot with this ID exists within the caller's tenant."""


class SnapshotNotFinalizedError(Exception):
    """An operation that requires a stable membership set was asked to
    run against a draft snapshot, whose membership can still change."""


class DatasetArchivedError(Exception):
    """An archived dataset does not accept new authoring."""


class ImportRejectedError(Exception):
    """At least one import record failed validation, so the whole
    import was rejected and nothing was written."""
