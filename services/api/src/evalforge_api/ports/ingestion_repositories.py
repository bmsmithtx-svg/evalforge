"""Bundle of Milestone 5 ingestion ports handed to application
services, mirroring ``evalforge_api.ports.evaluation_repositories``.
"""

from __future__ import annotations

from dataclasses import dataclass

from evalforge_api.ports.evidence_artifacts import EvidenceArtifactRepository
from evalforge_api.ports.runs import RunRepository
from evalforge_api.ports.traces import SpanRepository, TraceRepository


@dataclass(frozen=True, slots=True)
class IngestionRepositories:
    runs: RunRepository
    traces: TraceRepository
    spans: SpanRepository
    evidence_artifacts: EvidenceArtifactRepository
