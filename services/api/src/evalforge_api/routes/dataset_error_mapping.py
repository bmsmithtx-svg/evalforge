"""Maps Milestone 6 dataset-management application exceptions to
standardized HTTP responses.

The ingestion equivalent (``routes/ingestion_error_mapping``) is bound
to the Milestone 5 ingestion services it imports, so dataset routes get
their own mapping rather than widening that one. Both produce the same
standardized error envelope from ``evalforge_api.error_handling`` —
this module only chooses the status code.
"""

from __future__ import annotations

from typing import NoReturn

from fastapi import HTTPException, status

from evalforge_api.application.dataset_errors import (
    AuthorizationDeniedError,
    DatasetArchivedError,
    DatasetNotFoundError,
    ImportRejectedError,
    SnapshotNotFinalizedError,
    SnapshotNotFoundError,
    TestCaseNotFoundError,
)
from evalforge_api.application.dataset_export_service import UnsupportedExportFormatError
from evalforge_api.application.dataset_import_service import UnsupportedImportFormatError
from evalforge_api.application.snapshot_service import (
    AuthorizationDeniedError as _SnapshotAuthDenied,
)
from evalforge_api.application.snapshot_service import (
    SnapshotNotDraftError,
)
from evalforge_api.application.snapshot_service import (
    SnapshotNotFoundError as _SnapshotNotFound,
)
from evalforge_api.domain.import_parsing import ImportPayloadTooLargeError
from evalforge_api.domain.sampling import InvalidSamplingRequestError
from evalforge_api.domain.test_case_content import InvalidTestCaseContentError
from evalforge_api.domain.versioning import ImmutableRecordError, LineageViolationError

_AUTHORIZATION_DENIED_TYPES = (AuthorizationDeniedError, _SnapshotAuthDenied)
_NOT_FOUND_TYPES = (
    DatasetNotFoundError,
    TestCaseNotFoundError,
    SnapshotNotFoundError,
    _SnapshotNotFound,
)
_CONFLICT_TYPES = (SnapshotNotDraftError, ImmutableRecordError, DatasetArchivedError)
_UNPROCESSABLE_TYPES = (
    InvalidTestCaseContentError,
    InvalidSamplingRequestError,
    SnapshotNotFinalizedError,
    LineageViolationError,
    UnsupportedImportFormatError,
    UnsupportedExportFormatError,
    ImportRejectedError,
)


def raise_as_http(exc: Exception) -> NoReturn:
    """Translate a known dataset-management exception into an
    ``HTTPException``.

    Must be called from inside an ``except Exception as exc:`` block.
    An exception type not covered here is re-raised unchanged and falls
    through to the standardized unhandled-exception handler, which
    never leaks internals.
    """
    if isinstance(exc, _AUTHORIZATION_DENIED_TYPES):
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    if isinstance(exc, _NOT_FOUND_TYPES):
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    if isinstance(exc, _CONFLICT_TYPES):
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    if isinstance(exc, ImportPayloadTooLargeError):
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, str(exc)) from exc
    if isinstance(exc, _UNPROCESSABLE_TYPES):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    raise exc
