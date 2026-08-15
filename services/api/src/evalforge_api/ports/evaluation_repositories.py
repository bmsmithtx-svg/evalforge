"""Bundle of Milestone 4 evaluation-domain ports handed to application
services, mirroring ``evalforge_api.ports.identity.IdentityRepositories``.
"""

from __future__ import annotations

from dataclasses import dataclass

from evalforge_api.ports.artifacts import ArtifactObjectStorage, ArtifactRepository
from evalforge_api.ports.datasets import DatasetRepository, DatasetSnapshotRepository
from evalforge_api.ports.versioned_resources import VersionedResourceRepository
from evalforge_api.ports.workspaces import EvaluationTargetRepository, WorkspaceRepository


@dataclass(frozen=True, slots=True)
class EvaluationRepositories:
    workspaces: WorkspaceRepository
    evaluation_targets: EvaluationTargetRepository
    versioned_resources: VersionedResourceRepository
    datasets: DatasetRepository
    snapshots: DatasetSnapshotRepository
    artifacts: ArtifactRepository
    artifact_storage: ArtifactObjectStorage
