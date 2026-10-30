"""Domain model — productforge/<Entity>/v1 typed contracts.

Single source of truth for entities, states and permissions. Mirrors the
cycle-1 domain model: Workspace → Product → contexts/knowledge/agents/
sources/dashboards/planning, all auditable and versioned.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def utcnow() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class Actor(BaseModel):
    id: str = "local"
    kind: Literal["human", "agent", "service"] = "human"
    display: str = "local"


class Role(StrEnum):
    VIEWER = "viewer"
    EDITOR = "editor"
    PRODUCT_ADMIN = "product_admin"
    WORKSPACE_ADMIN = "workspace_admin"
    AGENT_OPERATOR = "agent_operator"


# permission catalog — see docs/audit/PRODUCT_FORGE_ARCHITECTURE.md
PERMISSIONS: dict[str, set[Role]] = {
    "workspace.read": {Role.VIEWER, Role.EDITOR, Role.PRODUCT_ADMIN, Role.WORKSPACE_ADMIN},
    "product.read": {Role.VIEWER, Role.EDITOR, Role.PRODUCT_ADMIN, Role.WORKSPACE_ADMIN},
    "product.write": {Role.EDITOR, Role.PRODUCT_ADMIN, Role.WORKSPACE_ADMIN},
    "knowledge.write": {Role.EDITOR, Role.PRODUCT_ADMIN},
    "agent.manage": {Role.PRODUCT_ADMIN, Role.AGENT_OPERATOR, Role.WORKSPACE_ADMIN},
    "query.execute": {Role.EDITOR, Role.PRODUCT_ADMIN, Role.AGENT_OPERATOR},
    "dashboard.write": {Role.EDITOR, Role.PRODUCT_ADMIN},
    "planning.write": {Role.EDITOR, Role.PRODUCT_ADMIN},
}


class Entity(BaseModel):
    id: str
    created_at: str = Field(default_factory=utcnow)
    updated_at: str = Field(default_factory=utcnow)
    created_by: str = "local"
    schema_: str = Field(default="", alias="schema")

    def schema_name(self) -> str:
        return self.schema_ or f"productforge/{type(self).__name__}/v1"


class Workspace(Entity):
    name: str
    description: str = ""
    status: Literal["active", "archived"] = "active"
    settings: dict[str, Any] = Field(default_factory=dict)


class Product(Entity):
    workspace_id: str
    name: str
    description: str = ""
    domain: str = ""
    tags: list[str] = Field(default_factory=list)
    stakeholders: list[str] = Field(default_factory=list)
    status: Literal["draft", "active", "archived"] = "draft"


class SourceType(StrEnum):
    MARKDOWN = "markdown"
    TEXT = "text"
    PDF = "pdf"
    DOCX = "docx"
    URL = "url"
    API = "api"
    DATABASE = "database"
    TICKET = "ticket"
    MEETING = "meeting"
    REPO = "repo"
    DATA_PRODUCT = "data_product"


class SourceStatus(StrEnum):
    REGISTERED = "registered"
    INDEXING = "indexing"
    INDEXED = "indexed"
    ERROR = "error"
    STALE = "stale"
    UNVERIFIED = "unverified"


class KnowledgeSource(Entity):
    product_id: str
    name: str
    type: SourceType = SourceType.MARKDOWN
    locator: str = ""  # path or URI — never credentials
    status: SourceStatus = SourceStatus.REGISTERED
    classification: str = "internal"
    metadata_: dict[str, Any] = Field(default_factory=dict, alias="metadata")
    last_indexed_at: str | None = None


class DocumentStatus(StrEnum):
    IMPORTED = "imported"
    CHUNKED = "chunked"
    INDEXED = "indexed"
    FAILED = "failed"


class Document(Entity):
    product_id: str
    source_id: str | None = None
    title: str
    content_hash: str = ""
    status: DocumentStatus = DocumentStatus.IMPORTED
    chunk_count: int = 0
    metadata_: dict[str, Any] = Field(default_factory=dict, alias="metadata")


class EntityKind(StrEnum):
    PRODUCT = "product"
    MODULE = "module"
    FEATURE = "feature"
    METRIC = "metric"
    EVENT = "event"
    DIMENSION = "dimension"
    API = "api"
    DATASET = "dataset"
    TABLE = "table"
    COLUMN = "column"
    TEAM = "team"
    STAKEHOLDER = "stakeholder"
    RISK = "risk"
    DECISION = "decision"
    INITIATIVE = "initiative"
    AGENT = "agent"
    SOURCE = "source"
    OTHER = "other"


class RelKind(StrEnum):
    HAS_FEATURE = "has_feature"
    MEASURED_BY = "measured_by"
    OWNED_BY = "owned_by"
    EXPOSED_VIA = "exposed_via"
    READS_FROM = "reads_from"
    DEPENDS_ON = "depends_on"
    DOCUMENTED_IN = "documented_in"
    DECIDED_BY = "decided_by"
    RELATED_TO = "related_to"


class KnowledgeEntity(Entity):
    product_id: str
    kind: EntityKind
    name: str
    description: str = ""
    confidence: float = 0.0
    attributes: dict[str, Any] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)  # chunk ids
    provisional: bool = True


class Relation(Entity):
    product_id: str
    from_entity: str
    to_entity: str
    kind: RelKind
    confidence: float = 0.0
    evidence: list[str] = Field(default_factory=list)


class AgentStatus(StrEnum):
    DRAFT = "draft"
    TESTING = "testing"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class AgentDefinition(Entity):
    product_id: str
    name: str
    mission: str = ""
    template: str = "custom"
    status: AgentStatus = AgentStatus.DRAFT
    knowledge_scope: list[str] = Field(default_factory=list)
    tools_allowed: list[str] = Field(default_factory=list)
    policies: dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    eval_summary: dict[str, Any] | None = None


class ConnectorType(StrEnum):
    SQLITE = "sqlite"
    POSTGRES = "postgres"
    MYSQL = "mysql"
    DUCKDB = "duckdb"
    ATHENA = "athena"
    TRINO = "trino"
    DATABRICKS = "databricks"
    FABRIC = "fabric"
    BIGQUERY = "bigquery"
    CSV = "csv"


class ConnectorStatus(StrEnum):
    UNVERIFIED = "unverified"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    ERROR = "error"


class DataSource(Entity):
    product_id: str
    name: str
    connector: ConnectorType
    status: ConnectorStatus = ConnectorStatus.UNVERIFIED
    locator: str = ""  # host/path — credentials via secret refs only
    dialect: str = "sql"
    read_only: bool = True
    catalog_allowlist: list[str] = Field(default_factory=list)
    last_verified_at: str | None = None


class QueryRunStatus(StrEnum):
    VALIDATED = "validated"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    FAILED = "failed"
    REJECTED = "rejected"


class QueryRun(Entity):
    product_id: str
    dialect: str = "sql"
    statement: str
    status: QueryRunStatus = QueryRunStatus.VALIDATED
    rows: int = 0
    duration_ms: float = 0.0
    error: str | None = None
    truncated: bool = False


class Dashboard(Entity):
    product_id: str
    name: str
    description: str = ""
    widgets: list[dict[str, Any]] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    shared_with: list[str] = Field(default_factory=list)


class Initiative(Entity):
    product_id: str
    title: str
    hypothesis: str = ""
    status: Literal["proposed", "prioritized", "in_progress", "done", "rejected"] = "proposed"
    priority_score: float = 0.0
    evidence: list[str] = Field(default_factory=list)


class Decision(Entity):
    product_id: str
    title: str
    context: str = ""
    decision: str = ""
    alternatives: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class AuditEvent(Entity):
    workspace_id: str | None = None
    product_id: str | None = None
    actor: str = "local"
    actor_kind: str = "human"
    action: str = ""
    resource_type: str = ""
    resource_id: str = ""
    correlation_id: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
