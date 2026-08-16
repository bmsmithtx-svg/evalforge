"""Maps Milestone 5 ingestion application-layer exceptions to
standardized HTTP responses.

Centralizing this mapping keeps every ingestion route handler thin —
route modules call ``raise_as_http(exc)`` from an ``except Exception``
block instead of repeating status-code decisions
(docs/ARCHITECTURE.md: "route handlers remain thin").
"""

from __future__ import annotations

from typing import NoReturn

from fastapi import HTTPException, status

from evalforge_api.application.artifact_service import (
    AuthorizationDeniedError as _ArtifactAuthDenied,
)
from evalforge_api.application.evidence_artifact_service import (
    AuthorizationDeniedError as _EvidenceAuthDenied,
)
from evalforge_api.application.evidence_artifact_service import InvalidEvidenceOwnerError
from evalforge_api.application.evidence_artifact_service import RunNotFoundError as _EvidenceRunNF
from evalforge_api.application.evidence_artifact_service import (
    TraceNotFoundError as _EvidenceTraceNF,
)
from evalforge_api.application.ingestion_validation import (
    ReferencedArtifactNotFoundError,
    ReferencedEvaluationTargetNotFoundError,
    ReferencedResourceKindMismatchError,
    ReferencedResourceNotFoundError,
    ReferencedWorkspaceNotFoundError,
)
from evalforge_api.application.run_service import AuthorizationDeniedError as _RunAuthDenied
from evalforge_api.application.run_service import RunNotFoundError
from evalforge_api.application.span_service import AuthorizationDeniedError as _SpanAuthDenied
from evalforge_api.application.span_service import TraceNotFoundError as _SpanTraceNF
from evalforge_api.application.trace_service import AuthorizationDeniedError as _TraceAuthDenied
from evalforge_api.application.trace_service import RunNotFoundError as _TraceRunNF
from evalforge_api.application.trace_service import TraceNotFoundError
from evalforge_api.domain.ingestion import (
    IdempotencyConflictError,
    ImmutableRunError,
    ImmutableTraceError,
    PayloadTooLargeError,
    SpanBatchTooLargeError,
    SpanParentNotFoundError,
)

_AUTHORIZATION_DENIED_TYPES = (
    _RunAuthDenied,
    _TraceAuthDenied,
    _SpanAuthDenied,
    _EvidenceAuthDenied,
    _ArtifactAuthDenied,
)
_NOT_FOUND_TYPES = (
    RunNotFoundError,
    TraceNotFoundError,
    _TraceRunNF,
    _SpanTraceNF,
    _EvidenceRunNF,
    _EvidenceTraceNF,
    ReferencedResourceNotFoundError,
    ReferencedResourceKindMismatchError,
    ReferencedArtifactNotFoundError,
    ReferencedWorkspaceNotFoundError,
    ReferencedEvaluationTargetNotFoundError,
)
_CONFLICT_TYPES = (ImmutableRunError, ImmutableTraceError, IdempotencyConflictError)
_UNPROCESSABLE_TYPES = (SpanBatchTooLargeError, InvalidEvidenceOwnerError, SpanParentNotFoundError)


def raise_as_http(exc: Exception) -> NoReturn:
    """Translate a known ingestion exception into an ``HTTPException``.

    Must be called from inside an ``except Exception as exc:`` block.
    An exception type not covered here is re-raised unchanged and
    falls through to the standardized unhandled-exception handler
    (``evalforge_api.error_handling``), which never leaks internals.
    """
    if isinstance(exc, _AUTHORIZATION_DENIED_TYPES):
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    if isinstance(exc, _NOT_FOUND_TYPES):
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    if isinstance(exc, _CONFLICT_TYPES):
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    if isinstance(exc, PayloadTooLargeError):
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, str(exc)) from exc
    if isinstance(exc, _UNPROCESSABLE_TYPES):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    raise exc
