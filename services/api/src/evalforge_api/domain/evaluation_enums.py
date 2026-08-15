"""Milestone 4 evaluation-domain enums.

These mirror the Postgres enum types created by the evaluation-domain
migration. Kept separate from ``domain/enums.py`` (identity and
tenancy) because they describe a distinct set of concepts.
"""

from __future__ import annotations

from enum import StrEnum


class ResourceKind(StrEnum):
    """The versioned evaluation-configuration concepts fixed by the
    domain model. Each kind shares identical versioning mechanics
    (stable logical resource, immutable content-hashed versions,
    explicit lineage) so they share persistence and application
    machinery; only the JSON content shape differs per kind, and that
    shape is validated by domain schemas per kind, not by the shared
    storage mechanism.
    """

    MODEL_CONFIG = "model_config"
    PROMPT_CONFIG = "prompt_config"
    RETRIEVAL_CONFIG = "retrieval_config"
    TOOL_DEFINITION = "tool_definition"
    WORKFLOW_DEFINITION = "workflow_definition"
    EVALUATOR_DEFINITION = "evaluator_definition"
    PRICING_ASSUMPTION = "pricing_assumption"


class VersionedResourceStatus(StrEnum):
    DRAFTED = "drafted"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class WorkspaceStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class EvaluationTargetStatus(StrEnum):
    REGISTERED = "registered"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class DatasetStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class TestCaseStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class DatasetSnapshotStatus(StrEnum):
    DRAFT = "draft"
    FINALIZED = "finalized"
    ARCHIVED = "archived"


class ArtifactStatus(StrEnum):
    UPLOADED = "uploaded"
    VALIDATED = "validated"
    REFERENCED = "referenced"
    ARCHIVED = "archived"


class RetentionClass(StrEnum):
    """Tenant-scoped retention classification.

    This milestone does not implement retention/deletion execution; it
    only captures the classification so a later milestone can enforce
    policy against it. See docs/DATA_GOVERNANCE.md.
    """

    STANDARD = "standard"
    EXTENDED = "extended"
    LEGAL_HOLD = "legal_hold"
