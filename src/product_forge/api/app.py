"""HTTP API — forge/PortalApi/1 envelope, bearer auth, audit.

Every response uses the shared envelope: {schema, correlation_id, data|error}.
Mutations require the local bearer token (productforge api token --show).
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from collections import deque
from datetime import UTC
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .. import API_PREFIX, ENVELOPE_SCHEMA, FORGE_ID, __version__
from ..config import db_path, home_dir, load_config
from ..domain.models import (
    AgentDefinition,
    Board,
    Dashboard,
    DataSource,
    Decision,
    Experiment,
    Initiative,
    KnowledgeSource,
    Meeting,
    Notebook,
    Product,
    Task,
    Workspace,
    new_id,
    utcnow,
)
from ..errors import (
    ConflictError,
    ForgeError,
    NotFoundError,
    ReviewRequiredError,
    UrlCaptureForgeError,
    ValidationError,
)
from ..knowledge.obsidian import (
    ObsidianVaultError,
    export_vault_document,
    import_vault_document,
    plan_vault_sync,
)
from ..knowledge.url import UrlCaptureError, fetch_url_document
from ..knowledge.versions import explorer_versions, prepare_version
from ..security import TokenStore, redact, verify_oidc_token
from ..store.sqlite import Store
from ..workspace.discovery import (
    WorkspaceDiscoveryError,
    discover_workspace,
    import_workspace_document,
    preview_workspace_document,
)

MAX_BODY = 1 << 20
RATE_WINDOW = 60.0
RATE_LIMIT = 240


def _cid() -> str:
    return uuid.uuid4().hex[:16]


def envelope(data: Any = None, error: dict | None = None, cid: str | None = None) -> dict:
    env: dict[str, Any] = {"schema": ENVELOPE_SCHEMA, "correlation_id": cid or _cid()}
    if error is not None:
        env["error"] = error
    else:
        env["data"] = data
    return env


class ScopedIn(BaseModel):
    """Open body for product-scoped creates; fields whitelisted per route."""

    model_config = {"extra": "allow"}


class WorkspaceIn(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    settings: dict[str, Any] = Field(default_factory=dict)


class ProductIn(BaseModel):
    workspace_id: str
    name: str = Field(min_length=1)
    description: str = ""
    domain: str = ""
    tags: list[str] = Field(default_factory=list)


class QueryIn(BaseModel):
    question: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=50)


class RunIn(BaseModel):
    input: str = Field(min_length=1)


class JobIn(BaseModel):
    kind: str = Field(min_length=1)
    payload: dict[str, Any] | None = None
    product_id: str | None = None
    idempotency_key: str | None = None
    expires_at: str | None = None


class DelegateCallIn(BaseModel):
    workflow: str = Field(min_length=1)
    args: list[str] | None = None
    product_id: str | None = None
    timeout_s: int = Field(default=60, le=300)


class ValidateIn(BaseModel):
    statement: str = Field(min_length=1)
    dialect: str = "sql"


class ExecuteIn(BaseModel):
    source_id: str
    statement: str | None = None
    spec: dict[str, Any] | None = None
    row_limit: int = Field(default=1000, le=5000)
    timeout_s: float = Field(default=30.0, le=120.0)


class CompileIn(BaseModel):
    spec: dict[str, Any]


class NlIn(BaseModel):
    question: str = Field(min_length=1)
    source_id: str | None = None


class ContextAuthorizeIn(BaseModel):
    principal: str = ""
    product_id: str = Field(min_length=1)
    workspace_id: str | None = None
    session_id: str = ""
    provider: str = ""
    agent_profile: str = "default"
    ttl_s: int = Field(default=3600, ge=60, le=86400)


def _surface_to_paths(surface: dict[str, Any]) -> dict[str, Any]:
    """Rebuild an OpenAPI paths dict from a stored parsed surface."""
    paths: dict[str, Any] = {}
    for op in surface.get("operations", []):
        paths.setdefault(op["path"], {})[op["method"].lower()] = {
            "operationId": op.get("operation_id"),
            "summary": op.get("summary", ""),
            "parameters": [
                {
                    "name": p["name"],
                    "in": p["in"],
                    "required": p["required"],
                    "schema": {"type": p.get("type")},
                }
                for p in op.get("params", [])
            ],
            "requestBody": {"required": op.get("request_body_required", False)},
            "responses": {c: {} for c in op.get("responses", [])},
        }
    return paths


class Ctx:
    """Shared runtime: home, config, store, token, rate buckets, audit."""

    def __init__(self, home: Path | None = None) -> None:
        self.home = home or home_dir()
        self.cfg = load_config(self.home)
        self.store = Store(db_path(self.home, self.cfg))
        self.tokens = TokenStore(self.home / str(self.cfg["api"]["token_file"]))
        self._req: deque[float] = deque()
        self._lock = threading.Lock()
        self.started = time.time()
        from ..jobs.registry import JobRegistry

        self.jobs = JobRegistry(self.store)
        self.jobs_recovered = self.jobs.recover()

    def rate_ok(self) -> bool:
        now = time.time()
        with self._lock:
            while self._req and self._req[0] < now - RATE_WINDOW:
                self._req.popleft()
            if len(self._req) >= RATE_LIMIT:
                return False
            self._req.append(now)
            return True

    def audit(self, req: Request, action: str, rtype: str, rid: str, **kw: Any) -> None:
        self.store.audit(
            {
                "id": new_id("aud"),
                "created_at": utcnow(),
                "actor": "api",
                "actor_kind": "human",
                "action": action,
                "resource_type": rtype,
                "resource_id": rid,
                "correlation_id": getattr(req.state, "cid", ""),
                **kw,
            }
        )


def _path_product(path: str) -> str | None:
    """Extract product id from /api/v1/products/<pid>[/...] paths."""
    parts = path.split("/")
    try:
        i = parts.index("products")
        return parts[i + 1] if len(parts) > i + 1 and parts[i + 1] else None
    except ValueError:
        return None


def _path_workspace(path: str) -> str | None:
    """Extract workspace id from /api/v1/workspaces/<wid> paths."""
    parts = path.split("/")
    try:
        i = parts.index("workspaces")
        return parts[i + 1] if len(parts) > i + 1 and parts[i + 1] else None
    except ValueError:
        return None


def _principal_allows(cfg: dict[str, Any], token: str, workspace_id: str) -> bool:
    """Workspace scope check; empty principals = local single-user wildcard."""
    principals = cfg.get("principals") or []
    if not principals:
        return True
    for p in principals:
        if p.get("token") == token:
            return workspace_id in (p.get("workspaces") or [])
    return False


def _obsidian_vault() -> Path:
    raw = os.environ.get("FORGE_OBSIDIAN_VAULT", "").strip()
    if not raw:
        raise ForgeError("Obsidian vault is not configured", details={"code": "OBSIDIAN-NOT-CONFIGURED"})
    return Path(raw)


def _oidc_workspaces(claims: dict[str, Any] | None) -> set[str]:
    """Return the explicit workspace boundary from a verified OIDC claim.

    OIDC mode is multi-tenant by definition: a valid identity without an
    explicit workspace claim must not become an all-workspaces wildcard.
    """
    if not claims:
        return set()
    raw = claims.get("workspaces") or claims.get("workspace_ids")
    if not isinstance(raw, (list, tuple, set)):
        return set()
    return {str(item) for item in raw if str(item).strip()}


_ROLE_ORDER = {"viewer": 0, "editor": 1, "admin": 2}


def _principal_role(cfg: dict[str, Any], token: str) -> str:
    for principal in cfg.get("principals") or []:
        if principal.get("token") == token:
            return str(principal.get("role") or "viewer")
    return "admin" if not cfg.get("principals") else "viewer"


def _oidc_role(claims: dict[str, Any] | None) -> str:
    if not claims:
        return "viewer"
    roles = claims.get("roles") or claims.get("role")
    if isinstance(roles, str):
        roles = [roles]
    if not isinstance(roles, (list, tuple, set)):
        return "viewer"
    return max((str(role) for role in roles), key=lambda role: _ROLE_ORDER.get(role, -1), default="viewer")


def create_app(home: Path | None = None) -> FastAPI:
    ctx = Ctx(home)
    app = FastAPI(title="Product Forge", version=__version__, docs_url=None, redoc_url=None)
    app.state.ctx = ctx

    # -- middleware -------------------------------------------------------

    @app.exception_handler(ForgeError)
    async def _forge_err(_req: Request, exc: ForgeError) -> JSONResponse:
        return JSONResponse(status_code=exc.http_status, content=envelope(error=exc.body()))

    @app.exception_handler(HTTPException)
    async def _http_err(_req: Request, exc: HTTPException) -> JSONResponse:
        code = "PF-NOT-FOUND" if exc.status_code == 404 else f"PF-HTTP-{exc.status_code}"
        err = {
            "code": code,
            "message": str(exc.detail),
            "severity": "error",
            "retryable": exc.status_code >= 500,
        }
        return JSONResponse(status_code=exc.status_code, content=envelope(error=err))

    @app.exception_handler(RequestValidationError)
    async def _validation_err(_req: Request, exc: RequestValidationError) -> JSONResponse:
        err = {
            "code": "PF-VALIDATION",
            "message": "request validation failed",
            "severity": "warning",
            "retryable": False,
            "details": {"errors": exc.errors()},
        }
        return JSONResponse(status_code=422, content=envelope(error=err))

    from starlette.exceptions import HTTPException as _StarletteHTTPException

    @app.exception_handler(_StarletteHTTPException)
    async def _starlette_http_err(_req: Request, exc: _StarletteHTTPException) -> JSONResponse:
        # route-miss (404) and method-miss raise the starlette base class —
        # without this they leak {"detail": ...} outside the envelope.
        code = "PF-NOT-FOUND" if exc.status_code == 404 else f"PF-HTTP-{exc.status_code}"
        err = {
            "code": code,
            "message": str(exc.detail),
            "severity": "error",
            "retryable": exc.status_code >= 500,
        }
        return JSONResponse(status_code=exc.status_code, content=envelope(error=err))

    @app.exception_handler(Exception)
    async def _exc(_req: Request, exc: Exception) -> JSONResponse:
        err = {"code": "PF-INTERNAL", "message": "internal error", "severity": "error", "retryable": True}
        return JSONResponse(status_code=500, content=envelope(error=err))

    @app.middleware("http")
    async def _guard(req: Request, call_next):  # type: ignore[no-untyped-def]
        req.state.cid = _cid()
        if req.url.path.startswith(API_PREFIX) and req.url.path != f"{API_PREFIX}/health":
            if not ctx.rate_ok():
                err = {
                    "code": "PF-RATE-LIMIT",
                    "message": "rate limit",
                    "severity": "warning",
                    "retryable": True,
                }
                return JSONResponse(status_code=429, content=envelope(error=err, cid=req.state.cid))
            # §3.2: every private route requires bearer — GETs included.
            # Only /health is public (it discloses forge_id/version only).
            auth = req.headers.get("authorization", "")
            token = auth.removeprefix("Bearer ").strip()
            oidc_claims = None
            if (ctx.cfg.get("oidc") or {}).get("enabled"):
                try:
                    oidc_claims = verify_oidc_token(token, ctx.cfg)
                except Exception:
                    oidc_claims = None
            oidc_enabled = bool((ctx.cfg.get("oidc") or {}).get("enabled"))
            valid_token = bool(oidc_claims) if oidc_enabled else ctx.tokens.check(token)
            if not valid_token:
                err = {
                    "code": "PF-UNAUTHORIZED",
                    "message": "invalid or missing token",
                    "severity": "error",
                    "retryable": False,
                }
                return JSONResponse(status_code=401, content=envelope(error=err, cid=req.state.cid))
            # §3.2 authorization: product routes are workspace-scoped per
            # principal (config.principals; empty = local single-user wildcard).
            pid = _path_product(req.url.path)
            wid = _path_workspace(req.url.path)
            req.state.oidc_claims = oidc_claims
            req.state.workspace_scope = _oidc_workspaces(oidc_claims) if oidc_enabled else None
            if pid:
                try:
                    ws = ctx.store.get("products", pid)["workspace_id"]
                except Exception:
                    ws = None  # missing product → 404 downstream, no leak
                claimed_workspaces = _oidc_workspaces(oidc_claims)
                scoped = ws in claimed_workspaces if oidc_enabled else True
                if ws and (not scoped or (not oidc_enabled and not _principal_allows(ctx.cfg, token, ws))):
                    err = {
                        "code": "PF-FORBIDDEN",
                        "message": "workspace not in principal scope",
                        "severity": "error",
                        "retryable": False,
                    }
                    return JSONResponse(status_code=403, content=envelope(error=err, cid=req.state.cid))
            if wid:
                allowed = (
                    wid in _oidc_workspaces(oidc_claims)
                    if oidc_enabled
                    else _principal_allows(ctx.cfg, token, wid)
                )
                if not allowed:
                    err = {
                        "code": "PF-FORBIDDEN",
                        "message": "workspace not in principal scope",
                        "severity": "error",
                        "retryable": False,
                    }
                    return JSONResponse(status_code=403, content=envelope(error=err, cid=req.state.cid))
            if req.method not in {"GET", "HEAD", "OPTIONS"}:
                role = _oidc_role(oidc_claims) if oidc_enabled else _principal_role(ctx.cfg, token)
                required = "admin" if req.url.path.endswith(("/auth/rotate", "/auth/revoke")) else "editor"
                if _ROLE_ORDER.get(role, -1) < _ROLE_ORDER[required]:
                    err = {
                        "code": "PF-FORBIDDEN",
                        "message": f"{required} role required",
                        "severity": "error",
                        "retryable": False,
                    }
                    return JSONResponse(status_code=403, content=envelope(error=err, cid=req.state.cid))
            if int(req.headers.get("content-length", 0)) > MAX_BODY:
                err = {
                    "code": "PF-PAYLOAD-TOO-LARGE",
                    "message": "payload too large",
                    "severity": "warning",
                    "retryable": False,
                }
                return JSONResponse(status_code=413, content=envelope(error=err, cid=req.state.cid))
        resp = await call_next(req)
        resp.headers["X-Correlation-Id"] = req.state.cid
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        return resp

    def _d(body: BaseModel) -> dict[str, Any]:
        return redact(body.model_dump(exclude_unset=True, by_alias=True))

    # -- platform ---------------------------------------------------------

    @app.get(f"{API_PREFIX}/health")
    def health() -> dict:
        return envelope(
            {
                "forge_id": FORGE_ID,
                "version": __version__,
                "status": "healthy",
                "uptime_s": round(time.time() - ctx.started, 2),
            }
        )

    @app.get(f"{API_PREFIX}/jobs")
    def jobs_list(status: str | None = None, product_id: str | None = None) -> dict:
        return envelope({"items": ctx.jobs.list(status, product_id), "recovered_on_boot": ctx.jobs_recovered})

    @app.post(f"{API_PREFIX}/jobs")
    def jobs_enqueue(body: JobIn, req: Request) -> dict:
        job = ctx.jobs.enqueue(
            body.kind, body.payload, body.product_id, body.idempotency_key, body.expires_at
        )
        ctx.audit(req, "job.enqueue", "job", job["id"], product_id=body.product_id or "")
        return envelope(job)

    @app.post(f"{API_PREFIX}/jobs/{{jid}}/cancel")
    def jobs_cancel(jid: str, req: Request) -> dict:
        job = ctx.jobs.cancel(jid)
        ctx.audit(req, "job.cancel", "job", jid)
        return envelope(job)

    @app.post(f"{API_PREFIX}/jobs/drain")
    def jobs_drain(limit: int = 10) -> dict:
        ran = []
        for _ in range(limit):
            job = ctx.jobs.run_next()
            if job is None:
                break
            ran.append({"id": job["id"], "status": job["status"]})
        return envelope({"ran": ran})

    @app.get(f"{API_PREFIX}/delegates")
    def delegates_list() -> dict:
        from ..delegates.catalog import catalog

        return envelope({"delegates": catalog(ctx.cfg)})

    @app.post(f"{API_PREFIX}/delegates/{{did}}/call")
    def delegate_call(did: str, body: DelegateCallIn, req: Request) -> dict:
        from ..agents.routing import record_usage
        from ..delegates.runner import call

        result = call(ctx.cfg, ctx.store, body.product_id, did, body.workflow, body.args or [])
        ctx.audit(
            req, "delegate.call", "delegate", did, product_id=body.product_id or "", workflow=body.workflow
        )
        record_usage(ctx.store, body.product_id or "global", {"tool_calls": 1})
        return envelope(result)

    @app.get(f"{API_PREFIX}/agent-templates")
    def agent_templates() -> dict:
        from ..agents.tools import list_templates

        return envelope({"items": list_templates()})

    @app.get(f"{API_PREFIX}/capabilities")
    def capabilities() -> dict:
        caps = [
            {"id": "workspaces", "state": "supported"},
            {"id": "products", "state": "supported"},
            {"id": "knowledge.sources", "state": "supported"},
            {"id": "knowledge.entities", "state": "supported"},
            {"id": "agents.definitions", "state": "supported"},
            {"id": "analytics.sources", "state": "supported"},
            {"id": "analytics.queries", "state": "unverified"},
            {"id": "dashboards", "state": "supported"},
            {"id": "planning.initiatives", "state": "supported"},
            {"id": "planning.decisions", "state": "supported"},
            {"id": "portal", "state": "unverified"},
            {"id": "mcp", "state": "unverified"},
            {"id": "llm", "state": "unverified"},
        ]
        return envelope({"forge_id": FORGE_ID, "capabilities": caps})

    @app.post(f"{API_PREFIX}/auth/rotate")
    def rotate(req: Request) -> dict:
        ctx.tokens.rotate()
        ctx.audit(req, "auth.rotate", "token", "api")
        return envelope({"rotated": True, "token_preview": ctx.tokens.preview})

    @app.post(f"{API_PREFIX}/auth/revoke")
    def revoke(req: Request) -> dict:
        ctx.tokens.revoke()
        ctx.audit(req, "auth.revoke", "token", "api")
        return envelope({"revoked": True, "token_preview": ctx.tokens.preview})

    # -- workspaces --------------------------------------------------------

    @app.post(f"{API_PREFIX}/workspaces", status_code=201)
    def create_ws(body: WorkspaceIn, req: Request) -> dict:
        ws = Workspace(id=new_id("ws"), **body.model_dump())
        ctx.store.put("workspaces", ws)
        ctx.audit(req, "workspace.create", "workspace", ws.id, workspace_id=ws.id)
        return envelope(ws.model_dump(mode="json", by_alias=True))

    @app.get(f"{API_PREFIX}/workspaces")
    def list_ws(req: Request, limit: int = 100, offset: int = 0) -> dict:
        scope = getattr(req.state, "workspace_scope", None)
        items = ctx.store.list("workspaces", limit=limit, offset=offset)
        if scope is not None:
            items = [item for item in items if item.get("id") in scope]
        return envelope({"items": items})

    @app.get(f"{API_PREFIX}/workspaces/{{wid}}")
    def get_ws(wid: str) -> dict:
        return envelope(ctx.store.get("workspaces", wid))

    # -- local workspace context discovery ---------------------------------

    @app.get(f"{API_PREFIX}/workspace/discovery")
    def workspace_discovery() -> dict:
        """Metadata-only discovery for the workspace hosting this API."""
        return envelope(discover_workspace(Path.cwd()))

    @app.get(f"{API_PREFIX}/workspace/discovery/preview")
    def workspace_discovery_preview(path: str) -> dict:
        try:
            root = discover_workspace(Path.cwd())["workspace"]["path"]
            return envelope(preview_workspace_document(root, path))
        except WorkspaceDiscoveryError as exc:
            raise ValidationError(str(exc), details={"code": "PF-WORKSPACE-DOCUMENT"}) from exc

    @app.patch(f"{API_PREFIX}/workspaces/{{wid}}")
    def patch_ws(wid: str, body: WorkspaceIn, req: Request) -> dict:
        doc = ctx.store.get("workspaces", wid)
        doc.update(_d(body))
        ws = Workspace.model_validate(doc)
        ctx.store.put("workspaces", ws)
        ctx.audit(req, "workspace.update", "workspace", wid, workspace_id=wid)
        return envelope(ws.model_dump(mode="json", by_alias=True))

    # -- products ------------------------------------------------------------

    @app.post(f"{API_PREFIX}/products", status_code=201)
    def create_product(body: ProductIn, req: Request) -> dict:
        ctx.store.get("workspaces", body.workspace_id)  # 404 if missing
        p = Product(id=new_id("prd"), status="active", **body.model_dump())
        ctx.store.put("products", p)
        ctx.audit(req, "product.create", "product", p.id, product_id=p.id, workspace_id=p.workspace_id)
        return envelope(p.model_dump(mode="json", by_alias=True))

    @app.get(f"{API_PREFIX}/products")
    def list_products(
        req: Request, workspace_id: str | None = None, limit: int = 100, offset: int = 0
    ) -> dict:
        scope = getattr(req.state, "workspace_scope", None)
        if scope is not None and workspace_id and workspace_id not in scope:
            return envelope({"items": []})
        items = ctx.store.list("products", workspace_id=workspace_id, limit=limit, offset=offset)
        if scope is not None:
            items = [item for item in items if item.get("workspace_id") in scope]
        return envelope({"items": items})

    @app.get(f"{API_PREFIX}/products/{{pid}}")
    def get_product(pid: str) -> dict:
        return envelope(ctx.store.get("products", pid))

    @app.patch(f"{API_PREFIX}/products/{{pid}}")
    def patch_product(pid: str, body: ScopedIn, req: Request) -> dict:
        from ..errors import ValidationError

        doc = ctx.store.get("products", pid)
        allowed = {"name", "description", "domain", "tags", "stakeholders", "status"}
        data = {k: v for k, v in body.model_dump(exclude_unset=True).items() if k in allowed}
        if not data:
            raise ValidationError("at least one product field is required")
        doc.update(data)
        product = Product.model_validate(doc)
        ctx.store.put("products", product)
        ctx.audit(req, "product.update", "product", pid, product_id=pid, workspace_id=product.workspace_id)
        return envelope(product.model_dump(mode="json", by_alias=True))

    @app.delete(f"{API_PREFIX}/products/{{pid}}")
    def delete_product(pid: str, req: Request) -> dict:
        product = ctx.store.get("products", pid)
        ctx.store.delete("products", pid)
        ctx.audit(
            req,
            "product.delete",
            "product",
            pid,
            product_id=pid,
            workspace_id=product.get("workspace_id", ""),
        )
        return envelope({"deleted": True, "id": pid})

    @app.get(f"{API_PREFIX}/products/{{pid}}/context")
    def product_context(pid: str) -> dict:
        p = ctx.store.get("products", pid)
        ctx_pkg = {
            "schema": "productforge/ProductContextPackage/v1",
            "product": p,
            "sources": ctx.store.list("knowledge_sources", product_id=pid, limit=200),
            "entities": ctx.store.list("entities", product_id=pid, limit=200),
            "agents": ctx.store.list("agents", product_id=pid, limit=100),
            "data_sources": ctx.store.list("data_sources", product_id=pid, limit=100),
            "generated_at": utcnow(),
        }
        return envelope(ctx_pkg)

    # -- session context authorization (forge/ProductAgentSessionContext/v2) --

    def _context_state(rec: dict[str, Any]) -> str:
        if rec.get("status") == "revoked":
            return "revoked"
        exp = rec.get("expires_at_ts")
        if exp is not None and exp <= time.time():
            return "expired"
        return "active"

    @app.post(f"{API_PREFIX}/context/authorize", status_code=201)
    def context_authorize(body: ContextAuthorizeIn, req: Request) -> dict:
        """Issue a server-validated ProductAgentSessionContext/v2.

        Validates that the product exists, the workspace exists and
        matches, the workspace is in the caller's principal scope, and
        resolves permissions server-side — client-supplied ids are never
        trusted on their own."""
        from ..errors import NotFoundError, PermissionDeniedError, ValidationError

        p = ctx.store.get("products", body.product_id)  # 404 if missing
        ws = str(p.get("workspace_id") or "")
        if body.workspace_id and body.workspace_id != ws:
            raise ValidationError("workspace_id does not match product workspace")
        try:
            ctx.store.get("workspaces", ws)  # exists?
        except Exception as exc:
            raise NotFoundError(f"workspace {ws} not found") from exc
        token = req.headers.get("authorization", "").removeprefix("Bearer ").strip()
        claims = getattr(req.state, "oidc_claims", None)
        in_scope = (
            ws in _oidc_workspaces(claims)
            if (ctx.cfg.get("oidc") or {}).get("enabled")
            else _principal_allows(ctx.cfg, token, ws)
        )
        if not in_scope:
            raise PermissionDeniedError("workspace not in principal scope")
        if p.get("status") not in (None, "active"):
            raise ValidationError(f"product status {p.get('status')!r} cannot be authorized")
        now = time.time()
        cid = new_id("ctx")
        issued = utcnow()
        exp_ts = now + body.ttl_s
        principal = str((claims or {}).get("sub") or body.principal)
        rec: dict[str, Any] = {
            "id": cid,
            "schema": "forge/ProductAgentSessionContext/v2",
            "principal": principal,
            "workspace_id": ws,
            "product_id": body.product_id,
            "provider": body.provider,
            "session_id": body.session_id,
            "agent_profile": body.agent_profile,
            # permissions resolved server-side from product policy;
            # products without explicit grants get the safe defaults —
            # never a client-supplied allowlist.
            "allowed_knowledge": list(p.get("allowed_knowledge") or []),
            "allowed_datasets": list(p.get("allowed_datasets") or []),
            "allowed_metrics": list(p.get("allowed_metrics") or []),
            "allowed_apis": list(p.get("allowed_apis") or []),
            "allowed_tools": list(p.get("allowed_tools") or ["chat"]),
            "policy_version": "forge/PolicyBundle/1",
            "context_version": 1,
            "issued_at": issued,
            "issued_at_ts": now,
            "expires_at": utcnow(),
            "expires_at_ts": exp_ts,
            "revocation_ref": cid,
            "status": "active",
        }
        from datetime import datetime

        rec["expires_at"] = datetime.fromtimestamp(exp_ts, tz=UTC).isoformat()
        ctx.store.put_doc("session_contexts", rec)
        ctx.audit(
            req,
            "context.authorize",
            "session_context",
            cid,
            product_id=body.product_id,
            workspace_id=ws,
            actor_name=body.principal,
        )
        out = dict(rec)
        out["state"] = "active"
        return envelope(out)

    @app.get(f"{API_PREFIX}/context/{{cid}}")
    def context_get(cid: str) -> dict:
        rec = dict(ctx.store.get("session_contexts", cid))  # 404
        rec["state"] = _context_state(rec)
        return envelope(rec)

    @app.post(f"{API_PREFIX}/context/{{cid}}/revoke")
    def context_revoke(cid: str, req: Request) -> dict:
        rec = dict(ctx.store.get("session_contexts", cid))
        rec["status"] = "revoked"
        rec["revoked_at"] = utcnow()
        ctx.store.put_doc("session_contexts", rec)
        ctx.audit(req, "context.revoke", "session_context", cid, product_id=rec.get("product_id") or "")
        rec["state"] = "revoked"
        return envelope(rec)

    # -- generic collection factory -------------------------------------------

    def _crud(path: str, collection: str, model: type, in_fields: set[str]) -> None:
        @app.post(f"{API_PREFIX}/products/{{pid}}/{path}", status_code=201)
        def _create(pid: str, body: ScopedIn, req: Request, p=path, c=collection, m=model) -> dict:  # type: ignore[misc]
            product = ctx.store.get("products", pid)
            data = {k: v for k, v in body.model_dump(by_alias=True).items() if k in in_fields}
            data["product_id"] = pid
            if "workspace_id" in m.model_fields:
                data["workspace_id"] = product["workspace_id"]
            if m is Task and not data.get("board_id"):
                boards = ctx.store.list("boards", product_id=pid, limit=1)
                if boards:
                    data["board_id"] = boards[0]["id"]
                else:
                    board = Board(
                        id=new_id("brd"),
                        workspace_id=product["workspace_id"],
                        product_id=pid,
                        name=f"{product['name']} board",
                    )
                    ctx.store.put("boards", board)
                    data["board_id"] = board.id
            ent = m(id=new_id(p.rstrip("s")[:3]), **data)
            ctx.store.put(c, ent)
            ctx.audit(
                req,
                f"{p}.create",
                c,
                ent.id,
                product_id=pid,
                workspace_id=ctx.store.get("products", pid).get("workspace_id"),
            )
            return envelope(ent.model_dump(mode="json", by_alias=True))

        @app.get(f"{API_PREFIX}/products/{{pid}}/{path}")
        def _list(pid: str, p=path, c=collection) -> dict:  # type: ignore[misc]
            ctx.store.get("products", pid)
            return envelope({"items": ctx.store.list(c, product_id=pid)})

        @app.get(f"{API_PREFIX}/products/{{pid}}/{path}/{{rid}}")
        def _get(pid: str, rid: str, c=collection) -> dict:  # type: ignore[misc]
            doc = ctx.store.get(c, rid)
            if doc.get("product_id") != pid:
                from ..errors import NotFoundError

                raise NotFoundError(f"{c}/{rid} not in product {pid}")
            return envelope(doc)

        @app.patch(f"{API_PREFIX}/products/{{pid}}/{path}/{{rid}}")
        def _patch(pid: str, rid: str, body: ScopedIn, req: Request, p=path, c=collection, m=model) -> dict:  # type: ignore[misc]
            from ..errors import NotFoundError, ValidationError

            doc = ctx.store.get(c, rid)
            if doc.get("product_id") != pid:
                raise NotFoundError(f"{c}/{rid} not in product {pid}")
            data = {k: v for k, v in body.model_dump(exclude_unset=True).items() if k in in_fields}
            if not data:
                raise ValidationError("at least one entity field is required")
            doc.update(data)
            ent = m.model_validate(doc)
            ctx.store.put(c, ent)
            ctx.audit(req, f"{p}.update", c, rid, product_id=pid)
            return envelope(ent.model_dump(mode="json", by_alias=True))

        @app.delete(f"{API_PREFIX}/products/{{pid}}/{path}/{{rid}}")
        def _delete(pid: str, rid: str, req: Request, p=path, c=collection) -> dict:  # type: ignore[misc]
            from ..errors import NotFoundError

            doc = ctx.store.get(c, rid)
            if doc.get("product_id") != pid:
                raise NotFoundError(f"{c}/{rid} not in product {pid}")
            ctx.store.delete(c, rid)
            ctx.audit(req, f"{p}.delete", c, rid, product_id=pid)
            return envelope({"deleted": True, "id": rid})

    _crud(
        "sources",
        "knowledge_sources",
        KnowledgeSource,
        {"name", "type", "locator", "classification", "metadata"},
    )
    _crud(
        "agents",
        "agents",
        AgentDefinition,
        {"name", "mission", "template", "knowledge_scope", "tools_allowed", "policies"},
    )
    _crud(
        "data-sources",
        "data_sources",
        DataSource,
        {"name", "connector", "locator", "dialect", "catalog_allowlist"},
    )
    _crud("dashboards", "dashboards", Dashboard, {"name", "description", "widgets", "filters"})
    _crud("initiatives", "initiatives", Initiative, {"title", "hypothesis", "priority_score"})
    _crud(
        "tasks",
        "tasks",
        Task,
        {
            "board_id",
            "column_id",
            "title",
            "description",
            "type",
            "priority",
            "assignee",
            "labels",
            "due_date",
            "estimate",
            "position",
            "parent_id",
            "initiative_id",
            "dependencies",
            "acceptance_criteria",
            "session_refs",
            "archived",
            "version",
            "comments",
            "activities",
        },
    )
    _crud("decisions", "decisions", Decision, {"title", "context", "decision", "alternatives"})
    _crud(
        "experiments",
        "experiments",
        Experiment,
        {"title", "hypothesis", "design", "success_metrics", "guardrails", "baseline", "status", "results"},
    )
    _crud("meetings", "meetings", Meeting, {"title", "transcript"})
    _crud("notebooks", "notebooks", Notebook, {"title"})

    @app.get(f"{API_PREFIX}/products/{{pid}}/board")
    def product_board(pid: str) -> dict:
        product = ctx.store.get("products", pid)
        boards = ctx.store.list("boards", product_id=pid, limit=20)
        board = boards[0] if boards else None
        if board is None:
            board = Board(
                id=new_id("brd"),
                workspace_id=product["workspace_id"],
                product_id=pid,
                name=f"{product['name']} board",
            )
            ctx.store.put("boards", board)
        tasks = ctx.store.list("tasks", product_id=pid, limit=1000)
        board_doc = board.model_dump(mode="json", by_alias=True) if isinstance(board, Board) else board
        return envelope({"board": board_doc, "tasks": tasks})

    @app.post(f"{API_PREFIX}/products/{{pid}}/board", status_code=201)
    def create_product_board(pid: str, body: ScopedIn, req: Request) -> dict:
        product = ctx.store.get("products", pid)
        if ctx.store.list("boards", product_id=pid, limit=1):
            raise ConflictError("product already has a board")
        board = Board(
            id=new_id("brd"),
            workspace_id=product["workspace_id"],
            product_id=pid,
            name=str(body.name if hasattr(body, "name") else "Board"),
        )
        ctx.store.put("boards", board)
        ctx.audit(req, "board.create", "boards", board.id, product_id=pid)
        return envelope(board.model_dump(mode="json", by_alias=True))

    @app.post(f"{API_PREFIX}/products/{{pid}}/tasks/{{tid}}/move")
    def move_task(pid: str, tid: str, body: ScopedIn, req: Request) -> dict:
        doc = ctx.store.get("tasks", tid)
        if doc.get("product_id") != pid:
            raise NotFoundError("task does not belong to product")
        expected = getattr(body, "expected_version", None)
        if expected is not None and int(expected) != int(doc.get("version", 1)):
            raise ConflictError("task changed; reload before moving")
        column_id = str(getattr(body, "column_id", "") or "")
        if not column_id:
            raise ValidationError("column_id is required")
        doc["column_id"] = column_id
        doc["position"] = int(getattr(body, "position", doc.get("position", 0)) or 0)
        doc["version"] = int(doc.get("version", 1)) + 1
        doc["activities"] = [
            *(doc.get("activities") or []),
            {"action": "moved", "column_id": column_id, "at": utcnow(), "actor": "local"},
        ]
        ent = Task.model_validate(doc)
        ctx.store.put("tasks", ent)
        ctx.audit(req, "task.move", "tasks", tid, product_id=pid, details={"column_id": column_id})
        return envelope(ent.model_dump(mode="json", by_alias=True))

    @app.post(f"{API_PREFIX}/products/{{pid}}/tasks/{{tid}}/comments", status_code=201)
    def task_comment(pid: str, tid: str, body: ScopedIn, req: Request) -> dict:
        doc = ctx.store.get("tasks", tid)
        if doc.get("product_id") != pid:
            raise NotFoundError("task does not belong to product")
        text = str(getattr(body, "text", "") or "").strip()
        if not text:
            raise ValidationError("comment text is required")
        comment = {"id": new_id("cmt"), "author": "local", "text": text, "created_at": utcnow()}
        doc["comments"] = [*(doc.get("comments") or []), comment]
        doc["version"] = int(doc.get("version", 1)) + 1
        ctx.store.put("tasks", Task.model_validate(doc))
        ctx.audit(req, "task.comment", "tasks", tid, product_id=pid)
        return envelope(comment)

    @app.post(f"{API_PREFIX}/products/{{pid}}/notebooks/{{nid}}/blocks", status_code=201)
    def notebook_add_block(pid: str, nid: str, body: dict[str, Any], req: Request) -> dict:
        from ..intel.notebooks import add_block

        nb = ctx.store.get("notebooks", nid)
        if nb.get("product_id") != pid:
            raise NotFoundError("notebook not in product")
        try:
            blk = add_block(nb, body.get("kind", "markdown"), body.get("content", ""), body.get("source_id"))
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        ctx.store.put_doc("notebooks", nb)
        ctx.audit(req, "notebooks.block-add", "notebooks", nid, product_id=pid)
        return envelope(blk)

    @app.post(f"{API_PREFIX}/products/{{pid}}/notebooks/{{nid}}/blocks/{{bid}}/run")
    def notebook_run_block(pid: str, nid: str, bid: str, req: Request) -> dict:
        from ..analytics.engine import execute_query, validate_query
        from ..intel.notebooks import run_sql_block

        nb = ctx.store.get("notebooks", nid)
        if nb.get("product_id") != pid:
            raise NotFoundError("notebook not in product")
        block = next((b for b in nb.get("blocks", []) if b["id"] == bid), None)
        if not block:
            raise NotFoundError("block not found")
        if block["kind"] != "sql":
            block["version"] += 1
            ctx.store.put_doc("notebooks", nb)
            return envelope({"ran": False, "status": "markdown-rendered", "block_version": block["version"]})
        dialect = "sqlite"
        if block.get("source_id"):
            import contextlib

            with contextlib.suppress(Exception):
                dialect = ctx.store.get("data_sources", block["source_id"]).get("dialect") or "sqlite"
        res = run_sql_block(
            block,
            lambda st: validate_query(st, dialect),
            lambda sid, st: execute_query(ctx.store, pid, sid, st),
        )
        ctx.store.put_doc("notebooks", nb)
        ctx.audit(
            req,
            "notebooks.block-run",
            "notebooks",
            nid,
            product_id=pid,
            details={"block": bid, "status": res.get("status")},
        )
        return envelope(res)

    @app.get(f"{API_PREFIX}/products/{{pid}}/notebooks/{{nid}}/render")
    def notebook_render(pid: str, nid: str) -> dict:
        from ..intel.notebooks import render

        nb = ctx.store.get("notebooks", nid)
        if nb.get("product_id") != pid:
            raise NotFoundError("notebook not in product")
        return envelope(render(nb))

    @app.post(f"{API_PREFIX}/products/{{pid}}/experiments/{{eid}}/conclude")
    def experiment_conclude(pid: str, eid: str, body: dict[str, Any], req: Request) -> dict:
        from ..intel.experiments import conclude_experiment

        exp = ctx.store.get("experiments", eid)
        if exp.get("product_id") != pid:
            raise NotFoundError("experiment not in product")
        upd = conclude_experiment(exp, body.get("results") or {}, body.get("verdict", ""))
        exp.update(upd)
        ctx.store.put_doc("experiments", exp)
        ctx.audit(req, "experiments.conclude", "experiments", eid, product_id=pid)
        refs = []
        if body.get("record_decision"):
            dec = Decision(
                id=new_id("dec"),
                product_id=pid,
                title=f"Experiment outcome: {exp['title']}",
                context=exp.get("hypothesis", ""),
                decision=upd["outcome"],
                evidence=[f"experiment:{eid}"],
            )
            ctx.store.put("decisions", dec)
            refs.append(dec.id)
        return envelope({**upd, "decision_refs": refs})

    @app.get(f"{API_PREFIX}/products/{{pid}}/decisions/{{did}}/completeness")
    def decision_completeness(pid: str, did: str) -> dict:
        from ..intel.experiments import decision_completeness

        dec = ctx.store.get("decisions", did)
        if dec.get("product_id") != pid:
            raise NotFoundError("decision not in product")
        return envelope(decision_completeness(dec))

    @app.post(f"{API_PREFIX}/products/{{pid}}/meetings/{{mid}}/extract")
    def meeting_extract(pid: str, mid: str, req: Request) -> dict:
        from ..intel.experiments import extract_drafts

        mtg = ctx.store.get("meetings", mid)
        if mtg.get("product_id") != pid:
            raise NotFoundError("meeting not in product")
        mtg["draft_items"] = extract_drafts(mtg.get("transcript") or "")
        mtg["status"] = "draft"
        ctx.store.put_doc("meetings", mtg)
        ctx.audit(req, "meetings.extract", "meetings", mid, product_id=pid)
        return envelope(
            {
                "meeting_id": mid,
                "status": "draft",
                "draft_items": mtg["draft_items"],
                "note": "drafts only — publish requires human review",
            }
        )

    @app.post(f"{API_PREFIX}/products/{{pid}}/meetings/{{mid}}/publish")
    def meeting_publish(pid: str, mid: str, body: dict[str, Any], req: Request) -> dict:
        mtg = ctx.store.get("meetings", mid)
        if mtg.get("product_id") != pid:
            raise NotFoundError("meeting not in product")
        if not body.get("reviewed"):
            raise ReviewRequiredError("human review required: resubmit with reviewed=true")
        refs: list[str] = []
        for item in body.get("items") or mtg.get("draft_items") or []:
            if item.get("kind") == "decision":
                dec = Decision(
                    id=new_id("dec"),
                    product_id=pid,
                    title=item["text"][:80],
                    decision=item["text"],
                    evidence=[f"meeting:{mid}:line{item.get('line')}"],
                )
                ctx.store.put("decisions", dec)
                refs.append(dec.id)
            elif item.get("kind") == "action":
                ini = Initiative(
                    id=new_id("ini"),
                    product_id=pid,
                    title=item["text"][:80],
                    evidence=[f"meeting:{mid}:line{item.get('line')}"],
                )
                ctx.store.put("initiatives", ini)
                refs.append(ini.id)
        mtg["status"] = "published"
        mtg["published_refs"] = refs
        ctx.store.put_doc("meetings", mtg)
        ctx.audit(req, "meetings.publish", "meetings", mid, product_id=pid, details={"refs": refs})
        return envelope({"meeting_id": mid, "status": "published", "published_refs": refs})

    # -- knowledge (Cycle 3) ---------------------------------------------------

    @app.post(f"{API_PREFIX}/products/{{pid}}/knowledge/query")
    def kn_query(pid: str, body: QueryIn) -> dict:
        ctx.store.get("products", pid)
        hits = ctx.store.search_fts(pid, body.question, limit=body.limit)
        citations = [
            {
                "chunk_id": h["id"],
                "document_id": h["document_id"],
                "snippet": h["snip"],
                "title": ctx.store.doc_title(h["document_id"]),
            }
            for h in hits
        ]
        from ..gateway.synthesis import synthesize

        synth = synthesize(ctx.store, pid, body.question, citations, ctx.cfg)
        return envelope(
            {
                "question": body.question,
                "citations": citations,
                "answer": synth.get("text"),
                "synthesis": (
                    "ok"
                    if synth["status"] == "ok"
                    else f"unavailable:{synth.get('reason', 'provider')}"
                    if synth["status"] == "unavailable"
                    else f"error:{synth.get('error', 'unknown')}"
                ),
                "synthesis_meta": {k: v for k, v in synth.items() if k not in ("text", "status")},
            }
        )

    @app.post(f"{API_PREFIX}/products/{{pid}}/knowledge/extract")
    def kn_extract(pid: str, req: Request) -> dict:
        from ..knowledge.extract import build_relations, extract_entities

        ctx.store.get("products", pid)
        chunks = ctx.store.list_chunks(pid)
        ents = extract_entities(pid, chunks)
        for e in ents:
            ctx.store.put("entities", e)
        rels = build_relations(pid, ents, chunks)
        for r in rels:
            ctx.store.put("relations", r)
        ctx.audit(req, "knowledge.extract", "product", pid, product_id=pid)
        return envelope(
            {
                "entities": len(ents),
                "relations": len(rels),
                "kinds": {k: sum(1 for e in ents if e.kind.value == k) for k in {e.kind.value for e in ents}},
            }
        )

    @app.get(f"{API_PREFIX}/products/{{pid}}/graph")
    def kn_graph(pid: str, limit: int = 2000) -> dict:
        from ..knowledge.graph import product_graph

        ctx.store.get("products", pid)
        return envelope(product_graph(ctx.store, pid, limit))

    @app.get(f"{API_PREFIX}/products/{{pid}}/knowledge-health")
    def kn_health(pid: str) -> dict:
        from ..knowledge.graph import knowledge_health

        ctx.store.get("products", pid)
        return envelope(knowledge_health(ctx.store, pid))

    @app.post(f"{API_PREFIX}/products/{{pid}}/documents", status_code=201)
    def import_doc(pid: str, body: ScopedIn, req: Request) -> dict:
        from ..domain.models import Document, DocumentStatus
        from ..knowledge.ingest import chunk_text, sha256_text

        ctx.store.get("products", pid)
        text = str(body.model_dump().get("content", ""))
        if not text:
            from ..errors import ValidationError

            raise ValidationError("document content is required")
        doc = Document(
            id=new_id("doc"),
            product_id=pid,
            title=str(body.model_dump().get("title", "untitled")),
            content_hash=sha256_text(text),
            status=DocumentStatus.IMPORTED,
        )
        ctx.store.put("documents", doc)
        doc.chunk_count = ctx.store.put_chunks(doc.id, pid, chunk_text(text))
        doc.status = DocumentStatus.INDEXED
        ctx.store.put("documents", doc)
        ctx.audit(req, "document.import", "documents", doc.id, product_id=pid)
        return envelope(doc.model_dump(mode="json", by_alias=True))

    @app.get(f"{API_PREFIX}/products/{{pid}}/documents")
    def list_docs(pid: str) -> dict:
        ctx.store.get("products", pid)
        return envelope({"items": ctx.store.list("documents", product_id=pid)})

    @app.get(f"{API_PREFIX}/products/{{pid}}/documents/search")
    def search_docs(pid: str, q: str = "", limit: int = 20) -> dict:
        """Search indexed product documents without returning document bodies."""
        ctx.store.get("products", pid)
        safe_limit = max(1, min(limit, 100))
        hits = ctx.store.search_fts(pid, q, safe_limit) if q.strip() else []
        items = []
        for hit in hits:
            doc = ctx.store.get("documents", hit["document_id"])
            metadata = doc.get("metadata") or {}
            items.append(
                {
                    "document_id": hit["document_id"],
                    "chunk_id": hit["id"],
                    "seq": hit["seq"],
                    "title": doc.get("title", hit["document_id"]),
                    "snippet": hit["snip"],
                    "source": metadata.get("source"),
                    "version": metadata.get("version", 1),
                }
            )
        return envelope({"schema": "productforge/DocumentSearch/v1", "items": items})

    @app.get(f"{API_PREFIX}/products/{{pid}}/knowledge/search")
    def search_knowledge(pid: str, q: str = "", limit: int = 20) -> dict:
        """Search body-free document and knowledge-graph projections."""
        from ..knowledge.search import search_knowledge as search

        ctx.store.get("products", pid)
        return envelope(search(ctx.store, pid, q, limit))

    @app.get(f"{API_PREFIX}/products/{{pid}}/documents/{{did}}")
    def get_doc(pid: str, did: str) -> dict:
        """Return one document explorer payload without exposing other products."""
        try:
            doc = ctx.store.get("documents", did)
        except KeyError as exc:
            from ..errors import NotFoundError

            raise NotFoundError("document not found") from exc
        if doc.get("product_id") != pid:
            from ..errors import NotFoundError

            raise NotFoundError("document not in product")
        chunks = [chunk for chunk in ctx.store.list_chunks(pid) if chunk.get("document_id") == did]
        return envelope(
            {
                "schema": "productforge/DocumentExplorer/v1",
                "document": doc,
                "content": {"chunks": chunks, "chunk_count": len(chunks)},
                "source": (doc.get("metadata") or {}).get("source"),
                "versions": explorer_versions(ctx.store, pid, doc),
                "relations": [],
            }
        )

    @app.get(f"{API_PREFIX}/products/{{pid}}/documents/url/preview")
    def preview_url_doc(pid: str, url: str, extractor: str = "stdlib") -> dict:
        """Fetch a bounded, non-mutating URL preview after SSRF validation."""
        ctx.store.get("products", pid)
        try:
            captured = fetch_url_document(url, extractor=extractor)
        except UrlCaptureError as exc:
            raise UrlCaptureForgeError(str(exc), details={"reason_code": exc.code, **exc.details}) from exc
        return envelope(
            {k: v for k, v in captured.items() if k != "content"} | {"preview": captured["content"]}
        )

    @app.post(f"{API_PREFIX}/products/{{pid}}/documents/from-workspace", status_code=201)
    def import_workspace_doc(pid: str, body: ScopedIn, req: Request) -> dict:
        """Import one explicitly selected local context file idempotently."""
        from ..domain.models import Document, DocumentStatus
        from ..errors import ValidationError
        from ..knowledge.ingest import chunk_text

        product = ctx.store.get("products", pid)
        raw_path = str(body.model_dump().get("path", "")).strip()
        if not raw_path:
            raise ValidationError("path is required")
        try:
            root = discover_workspace(Path.cwd())["workspace"]["path"]
            imported = import_workspace_document(root, raw_path)
        except WorkspaceDiscoveryError as exc:
            raise ValidationError(str(exc), details={"code": "PF-WORKSPACE-DOCUMENT"}) from exc
        existing = [
            doc
            for doc in ctx.store.list("documents", product_id=pid)
            if (doc.get("metadata") or {}).get("workspace_path") == imported["path"]
            and doc.get("content_hash") == imported["content_hash"]
        ]
        if existing:
            return envelope(
                {
                    **existing[0],
                    "state": "already_imported",
                    "source_path": imported["path"],
                    "source_kind": imported["kind"],
                }
            )
        metadata, _ = prepare_version(
            ctx.store,
            pid,
            {
                "source": "workspace",
                "workspace_path": imported["path"],
                "classification": imported["kind"],
                "size": imported["size"],
            },
        )
        doc = Document(
            id=new_id("doc"),
            product_id=pid,
            title=str(body.model_dump().get("title") or imported["title"]),
            content_hash=imported["content_hash"],
            status=DocumentStatus.IMPORTED,
            metadata=metadata,
        )
        ctx.store.put("documents", doc)
        doc.chunk_count = ctx.store.put_chunks(doc.id, pid, chunk_text(imported["content"]))
        doc.status = DocumentStatus.INDEXED
        ctx.store.put("documents", doc)
        ctx.audit(
            req,
            "workspace.document.import",
            "documents",
            doc.id,
            product_id=pid,
            workspace_id=product.get("workspace_id", ""),
        )
        return envelope(
            {
                **doc.model_dump(mode="json", by_alias=True),
                "state": "imported",
                "source_path": imported["path"],
                "source_kind": imported["kind"],
            }
        )

    @app.post(f"{API_PREFIX}/products/{{pid}}/documents/from-url", status_code=201)
    def import_url_doc(pid: str, body: ScopedIn, req: Request) -> dict:
        """Import one explicitly confirmed public URL with provenance."""
        from ..domain.models import Document, DocumentStatus
        from ..errors import ValidationError
        from ..knowledge.ingest import chunk_text

        product = ctx.store.get("products", pid)
        payload = body.model_dump()
        if str(payload.get("confirm", "")) != "import":
            raise ValidationError("confirm=import is required")
        raw_url = str(payload.get("url", "")).strip()
        if not raw_url:
            raise ValidationError("url is required")
        try:
            captured = fetch_url_document(raw_url, extractor=str(payload.get("extractor") or "stdlib"))
        except UrlCaptureError as exc:
            raise UrlCaptureForgeError(str(exc), details={"reason_code": exc.code, **exc.details}) from exc
        existing = [
            doc
            for doc in ctx.store.list("documents", product_id=pid)
            if (doc.get("metadata") or {}).get("source_url") == captured["url"]
            and doc.get("content_hash") == captured["content_hash"]
        ]
        if existing:
            return envelope(
                {
                    **existing[0],
                    "state": "already_imported",
                    "source_url": captured["url"],
                    "source_kind": "url",
                }
            )
        metadata, _ = prepare_version(
            ctx.store,
            pid,
            {
                "source": "url",
                "source_url": captured["url"],
                "content_type": captured["content_type"],
                "extractor": captured["extractor"],
                "size": captured["size"],
                "metrics": captured["metrics"],
                "warnings": captured["warnings"],
                "provenance": captured["provenance"],
            },
        )
        doc = Document(
            id=new_id("doc"),
            product_id=pid,
            title=str(payload.get("title") or captured["title"]),
            content_hash=captured["content_hash"],
            status=DocumentStatus.IMPORTED,
            metadata=metadata,
        )
        ctx.store.put("documents", doc)
        doc.chunk_count = ctx.store.put_chunks(doc.id, pid, chunk_text(captured["content"]))
        doc.status = DocumentStatus.INDEXED
        ctx.store.put("documents", doc)
        ctx.audit(
            req,
            "url.document.import",
            "documents",
            doc.id,
            product_id=pid,
            workspace_id=product.get("workspace_id", ""),
        )
        return envelope(
            {
                **doc.model_dump(mode="json", by_alias=True),
                "state": "imported",
                "source_url": captured["url"],
                "source_kind": "url",
                "capture": {k: v for k, v in captured.items() if k != "content"},
            }
        )

    @app.get(f"{API_PREFIX}/products/{{pid}}/documents/obsidian/preview")
    def preview_obsidian_doc(pid: str, path: str) -> dict:
        ctx.store.get("products", pid)
        try:
            imported = import_vault_document(_obsidian_vault(), path)
        except ObsidianVaultError as exc:
            raise ForgeError(str(exc), details={"code": exc.code}) from exc
        return envelope(
            {k: v for k, v in imported.items() if k != "content"} | {"preview": imported["content"]}
        )

    @app.post(f"{API_PREFIX}/products/{{pid}}/documents/from-obsidian", status_code=201)
    def import_obsidian_doc(pid: str, body: ScopedIn, req: Request) -> dict:
        from ..domain.models import Document, DocumentStatus
        from ..errors import ValidationError
        from ..knowledge.ingest import chunk_text

        product = ctx.store.get("products", pid)
        payload = body.model_dump()
        if str(payload.get("confirm", "")) != "import":
            raise ValidationError("confirm=import is required")
        raw_path = str(payload.get("path", "")).strip()
        if not raw_path:
            raise ValidationError("path is required")
        try:
            imported = import_vault_document(_obsidian_vault(), raw_path)
        except ObsidianVaultError as exc:
            raise ForgeError(str(exc), details={"code": exc.code}) from exc
        existing = [
            doc
            for doc in ctx.store.list("documents", product_id=pid)
            if (doc.get("metadata") or {}).get("obsidian_path") == imported["path"]
            and doc.get("content_hash") == imported["content_hash"]
        ]
        if existing:
            return envelope(
                {
                    **existing[0],
                    "state": "already_imported",
                    "source_path": imported["path"],
                    "source_kind": "obsidian",
                }
            )
        metadata, _ = prepare_version(
            ctx.store,
            pid,
            {
                "source": "obsidian",
                "obsidian_path": imported["path"],
                "size": imported["size"],
                "provenance": imported["provenance"],
            },
        )
        doc = Document(
            id=new_id("doc"),
            product_id=pid,
            title=str(payload.get("title") or imported["title"]),
            content_hash=imported["content_hash"],
            status=DocumentStatus.IMPORTED,
            metadata=metadata,
        )
        ctx.store.put("documents", doc)
        doc.chunk_count = ctx.store.put_chunks(doc.id, pid, chunk_text(imported["content"]))
        doc.status = DocumentStatus.INDEXED
        ctx.store.put("documents", doc)
        ctx.audit(
            req,
            "obsidian.document.import",
            "documents",
            doc.id,
            product_id=pid,
            workspace_id=product.get("workspace_id", ""),
        )
        return envelope(
            {
                **doc.model_dump(mode="json", by_alias=True),
                "state": "imported",
                "source_path": imported["path"],
                "source_kind": "obsidian",
            }
        )

    @app.post(f"{API_PREFIX}/products/{{pid}}/documents/to-obsidian")
    def export_obsidian_doc(pid: str, body: ScopedIn, req: Request) -> dict:
        from ..errors import ValidationError

        product = ctx.store.get("products", pid)
        payload = body.model_dump()
        if str(payload.get("confirm", "")) != "export":
            raise ValidationError("confirm=export is required")
        raw_path = str(payload.get("path", "")).strip()
        content = str(payload.get("content", ""))
        if not raw_path or not content:
            raise ValidationError("path and content are required")
        try:
            exported = export_vault_document(
                _obsidian_vault(),
                raw_path,
                content,
                baseline_hash=payload.get("baseline_hash"),
                classification=str(payload.get("classification") or "internal"),
                source=str(payload.get("source") or "product-forge"),
            )
        except ObsidianVaultError as exc:
            raise ForgeError(str(exc), details={"code": exc.code}) from exc
        ctx.audit(
            req,
            "obsidian.document.export",
            "obsidian",
            exported["path"],
            product_id=pid,
            workspace_id=product.get("workspace_id", ""),
        )
        return envelope(exported)

    @app.post(f"{API_PREFIX}/products/{{pid}}/documents/obsidian/sync-plan")
    def plan_obsidian_sync(pid: str, body: ScopedIn) -> dict:
        if ctx.store.get("products", pid) is None:
            raise NotFoundError(f"product {pid} not found")
        payload = body.model_dump()
        raw_path = str(payload.get("path", "")).strip()
        content = str(payload.get("content", ""))
        if not raw_path or not content:
            raise ValidationError("path and content are required")
        try:
            plan = plan_vault_sync(
                _obsidian_vault(),
                raw_path,
                content,
                baseline_hash=payload.get("baseline_hash"),
                classification=str(payload.get("classification") or "internal"),
                source=str(payload.get("source") or "product-forge"),
            )
        except ObsidianVaultError as exc:
            raise ForgeError(str(exc), details={"code": exc.code}) from exc
        return envelope(plan)

    # -- agents runtime (Cycle 4) ---------------------------------------------

    def _agent(pid: str, aid: str) -> AgentDefinition:
        doc = ctx.store.get("agents", aid)
        if doc.get("product_id") != pid:
            from ..errors import NotFoundError

            raise NotFoundError(f"agent {aid} not in product {pid}")
        return AgentDefinition.model_validate(doc)

    @app.post(f"{API_PREFIX}/products/{{pid}}/agents/{{aid}}/run")
    def agent_run(pid: str, aid: str, body: RunIn, req: Request) -> dict:
        from ..agents.runtime import run_agent

        agent = _agent(pid, aid)
        run = run_agent(ctx.store, agent, body.input, cfg=ctx.cfg)
        ctx.audit(req, "agent.run", "agent_runs", run["id"], product_id=pid)
        return envelope(run)

    @app.get(f"{API_PREFIX}/products/{{pid}}/agents/{{aid}}/runs")
    def agent_runs(pid: str, aid: str) -> dict:
        _agent(pid, aid)
        runs = [r for r in ctx.store.list("agent_runs", product_id=pid) if r.get("agent_id") == aid]
        return envelope({"items": runs})

    @app.post(f"{API_PREFIX}/products/{{pid}}/agents/{{aid}}/runs/{{rid}}/cancel")
    def agent_run_cancel(pid: str, aid: str, rid: str, req: Request) -> dict:
        from ..agents.runtime import cancel_run

        _agent(pid, aid)
        run = cancel_run(ctx.store, rid)
        ctx.audit(req, "agent.run.cancel", "agent_runs", rid, product_id=pid)
        return envelope(run)

    @app.post(f"{API_PREFIX}/products/{{pid}}/agents/{{aid}}/eval")
    def agent_eval(pid: str, aid: str, req: Request, body: ScopedIn | None = None) -> dict:
        from ..agents.evals import run_evals

        agent = _agent(pid, aid)
        cases = body.model_dump().get("cases") if body else None
        report = run_evals(ctx.store, agent, cases)
        agent.eval_summary = {
            "score": report["score"],
            "passed": report["passed"],
            "total": report["total"],
            "at": utcnow(),
        }
        ctx.store.put("agents", agent)
        ctx.audit(req, "agent.eval", "agents", aid, product_id=pid)
        return envelope(report)

    @app.post(f"{API_PREFIX}/products/{{pid}}/agents/{{aid}}/publish")
    def agent_publish(pid: str, aid: str, req: Request) -> dict:
        from ..agents.policy import publish_gate
        from ..errors import UnsafeOperationError

        agent = _agent(pid, aid)
        gate = publish_gate(agent)
        score = (agent.eval_summary or {}).get("score", 0)
        if not agent.tools_allowed:
            raise UnsafeOperationError("agent has no tools_allowed — configure permissions first")
        if score < float(gate["eval_gate"]):
            raise UnsafeOperationError(
                f"eval score {score} below publish gate {gate['eval_gate']} (risk tier {gate['tier']})"
            )
        if gate["approval_required"] and not agent.policies.get("allow_destructive"):
            raise UnsafeOperationError(
                "high-risk agent (destructive/unknown tools) requires "
                "policies.allow_destructive=true before publish"
            )
        agent.status = agent.status.PUBLISHED
        agent.version += 1
        ctx.store.put("agents", agent)
        ctx.audit(req, "agent.publish", "agents", aid, product_id=pid)
        return envelope(agent.model_dump(mode="json", by_alias=True))

    @app.post(f"{API_PREFIX}/products/{{pid}}/agents/{{aid}}/archive")
    def agent_archive(pid: str, aid: str, req: Request) -> dict:
        agent = _agent(pid, aid)
        agent.status = agent.status.ARCHIVED
        ctx.store.put("agents", agent)
        ctx.audit(req, "agent.archive", "agents", aid, product_id=pid)
        return envelope(agent.model_dump(mode="json", by_alias=True))

    # -- analytics (Cycle 5) ---------------------------------------------------

    @app.post(f"{API_PREFIX}/products/{{pid}}/queries/validate")
    def q_validate(pid: str, body: ValidateIn) -> dict:
        from ..analytics.engine import validate_query

        ctx.store.get("products", pid)
        return envelope(validate_query(body.statement, body.dialect))

    @app.post(f"{API_PREFIX}/products/{{pid}}/queries/compile")
    def q_compile(pid: str, body: CompileIn) -> dict:
        from ..analytics.engine import compile_spec

        ctx.store.get("products", pid)
        sql = compile_spec(body.spec)
        return envelope({"sql": sql, "spec": body.spec})

    @app.get(f"{API_PREFIX}/products/{{pid}}/health")
    def product_health(pid: str) -> dict:
        from ..intel.health import compute_health

        ctx.store.get("products", pid)
        return envelope(compute_health(ctx.store, pid))

    @app.get(f"{API_PREFIX}/products/{{pid}}/evidence-graph")
    def evidence_graph(pid: str) -> dict:
        from ..intel.health import evidence_graph

        ctx.store.get("products", pid)
        return envelope(evidence_graph(ctx.store, pid))

    @app.get(f"{API_PREFIX}/products/{{pid}}/metrics")
    def metrics_list(pid: str) -> dict:
        ctx.store.get("products", pid)
        return envelope({"items": ctx.store.list("metrics", product_id=pid)})

    @app.post(f"{API_PREFIX}/products/{{pid}}/metrics")
    def metrics_put(pid: str, body: dict[str, Any], req: Request) -> dict:
        from ..analytics.metrics import put_metric

        ctx.store.get("products", pid)
        doc = put_metric(ctx.store, pid, body)
        ctx.audit(req, "metric.put", "metrics", doc["id"], product_id=pid)
        return envelope(doc)

    @app.post(f"{API_PREFIX}/products/{{pid}}/metrics/resolve")
    def metrics_resolve(pid: str, body: QueryIn) -> dict:
        from ..analytics.metrics import resolve

        ctx.store.get("products", pid)
        return envelope(resolve(ctx.store, pid, body.question))

    @app.post(f"{API_PREFIX}/products/{{pid}}/queries/nl")
    def q_nl(pid: str, body: NlIn) -> dict:
        from ..analytics.engine import compile_spec, nl_to_sql
        from ..analytics.metrics import metric_sql, resolve

        ctx.store.get("products", pid)
        # §6.2: resolve catalog metric FIRST — agents never invent KPI formulas
        mres = resolve(ctx.store, pid, body.question)
        if mres["status"] == "matched":
            m = mres["matched"][0]["metric"]
            if m.get("source_id"):
                ds = ctx.store.get("data_sources", m["source_id"])
                tables = ds.get("catalog_allowlist") or ds.get("tables") or []
                if tables:
                    sql = metric_sql(m, tables[0])
                    return envelope(
                        {
                            "ok": True,
                            "sql": sql,
                            "metric": {"id": m["id"], "name": m["name"]},
                            "via": "semantic-catalog",
                        }
                    )
        tables: list[str] = []
        if body.source_id:
            ds = ctx.store.get("data_sources", body.source_id)
            tables = ds.get("catalog_allowlist", [])
        res = nl_to_sql(body.question, tables)
        if res.get("ok"):
            res["sql"] = compile_spec(res["spec"])
            res["via"] = "deterministic-nl"
        else:
            res["metric_resolution"] = mres  # unknown-metric stays explicit
        return envelope(res)

    @app.post(f"{API_PREFIX}/products/{{pid}}/queries/execute")
    def q_execute(pid: str, body: ExecuteIn, req: Request) -> dict:
        from ..analytics.engine import compile_spec, execute_query

        ctx.store.get("products", pid)
        statement = body.statement or (compile_spec(body.spec) if body.spec else None)
        if not statement:
            from ..errors import ValidationError

            raise ValidationError("statement or spec required")
        run = execute_query(
            ctx.store, pid, body.source_id, statement, row_limit=body.row_limit, timeout_s=body.timeout_s
        )
        ctx.audit(req, "query.execute", "query_runs", run["id"], product_id=pid)
        return envelope(run)

    @app.post(f"{API_PREFIX}/products/{{pid}}/queries/{{qid}}/cancel")
    def q_cancel(pid: str, qid: str, req: Request) -> dict:
        from ..analytics.engine import cancel_query

        ok = cancel_query(qid)
        ctx.audit(req, "query.cancel", "query_runs", qid, product_id=pid)
        return envelope({"cancelled": ok, "query_id": qid})

    @app.get(f"{API_PREFIX}/products/{{pid}}/queries")
    def q_list(pid: str) -> dict:
        ctx.store.get("products", pid)
        return envelope({"items": ctx.store.list("query_runs", product_id=pid)})

    @app.get(f"{API_PREFIX}/products/{{pid}}/queries/{{qid}}")
    def q_get(pid: str, qid: str) -> dict:
        run = ctx.store.get("query_runs", qid)
        if run.get("product_id") != pid:
            from ..errors import NotFoundError

            raise NotFoundError(f"query {qid} not in product {pid}")
        return envelope(run)

    @app.patch(f"{API_PREFIX}/products/{{pid}}/queries/{{qid}}")
    def q_patch(pid: str, qid: str, body: ScopedIn, req: Request) -> dict:
        from ..errors import NotFoundError, ValidationError

        run = ctx.store.get("query_runs", qid)
        if run.get("product_id") != pid:
            raise NotFoundError(f"query {qid} not in product {pid}")
        data = {
            k: v
            for k, v in body.model_dump(exclude_unset=True).items()
            if k in {"statement", "status", "error", "truncated"}
        }
        if not data:
            raise ValidationError("at least one query field is required")
        run.update(data)
        ctx.store.put_doc("query_runs", run)
        ctx.audit(req, "query.update", "query_runs", qid, product_id=pid)
        return envelope(run)

    @app.delete(f"{API_PREFIX}/products/{{pid}}/queries/{{qid}}")
    def q_delete(pid: str, qid: str, req: Request) -> dict:
        from ..errors import NotFoundError

        run = ctx.store.get("query_runs", qid)
        if run.get("product_id") != pid:
            raise NotFoundError(f"query {qid} not in product {pid}")
        ctx.store.delete("query_runs", qid)
        ctx.audit(req, "query.delete", "query_runs", qid, product_id=pid)
        return envelope({"deleted": True, "id": qid})

    @app.get(f"{API_PREFIX}/products/{{pid}}/data-sources/{{sid}}/schema")
    def ds_schema(pid: str, sid: str) -> dict:
        from ..analytics.connectors import connector_for

        ds = ctx.store.get("data_sources", sid)
        if ds.get("product_id") != pid:
            from ..errors import NotFoundError

            raise NotFoundError(f"data source {sid} not in product {pid}")
        from pathlib import Path

        return envelope(connector_for(ds, [Path(ds.get("locator", ".")).parent]).schema())

    @app.post(f"{API_PREFIX}/products/{{pid}}/data-sources/{{sid}}/verify")
    def ds_verify(pid: str, sid: str, req: Request) -> dict:
        from ..analytics.connectors import connector_for
        from ..domain.models import DataSource

        doc = ctx.store.get("data_sources", sid)
        if doc.get("product_id") != pid:
            from ..errors import NotFoundError

            raise NotFoundError(f"data source {sid} not in product {pid}")
        ds = DataSource.model_validate(doc)
        try:
            from pathlib import Path

            result = connector_for(doc, [Path(doc.get("locator", ".")).parent]).verify()
            ds.status = ds.status.HEALTHY
        except Exception as e:
            ds.status = ds.status.ERROR
            result = {"status": "error", "error": str(e)[:200]}
        ds.last_verified_at = utcnow()
        ctx.store.put("data_sources", ds)
        ctx.audit(req, "source.verify", "data_sources", sid, product_id=pid)
        return envelope(result)

    # -- dashboards (Cycle 6) --------------------------------------------------

    @app.post(f"{API_PREFIX}/products/{{pid}}/dashboards/{{did}}/render")
    def dash_render(pid: str, did: str, req: Request) -> dict:
        from ..dashboards.render import render_dashboard

        dash = ctx.store.get("dashboards", did)
        if dash.get("product_id") != pid:
            from ..errors import NotFoundError

            raise NotFoundError(f"dashboard {did} not in product {pid}")
        result = render_dashboard(ctx.store, pid, dash)
        ctx.audit(req, "dashboard.render", "dashboards", did, product_id=pid)
        return envelope(result)

    # -- planning (Cycle 7) ------------------------------------------------------

    @app.post(f"{API_PREFIX}/products/{{pid}}/initiatives/{{iid}}/prioritize")
    def initiative_prioritize(pid: str, iid: str, req: Request, body: ScopedIn | None = None) -> dict:
        from ..planning.prioritize import score_initiative

        doc = ctx.store.get("initiatives", iid)
        if doc.get("product_id") != pid:
            from ..errors import NotFoundError

            raise NotFoundError(f"initiative {iid} not in product {pid}")
        factors = body.model_dump() if body else {}
        res = score_initiative(doc, factors.get("factors", {}))
        doc["priority_score"] = res["score"]
        doc.setdefault("metadata", {})["prioritization"] = res
        from ..domain.models import Initiative

        ent = Initiative.model_validate(doc)
        ctx.store.put("initiatives", ent)
        ctx.audit(req, "initiative.prioritize", "initiatives", iid, product_id=pid)
        return envelope(res)

    @app.post(f"{API_PREFIX}/products/{{pid}}/initiatives/{{iid}}/prd")
    def initiative_prd(pid: str, iid: str, req: Request) -> dict:
        from ..planning.prd import generate_prd

        doc = ctx.store.get("initiatives", iid)
        if doc.get("product_id") != pid:
            from ..errors import NotFoundError

            raise NotFoundError(f"initiative {iid} not in product {pid}")
        prd = generate_prd(ctx.store, pid, doc)
        ctx.audit(req, "initiative.prd", "initiatives", iid, product_id=pid)
        return envelope(prd)

    @app.get(f"{API_PREFIX}/products/{{pid}}/roadmap")
    def roadmap(pid: str) -> dict:
        from ..planning.roadmap import build_roadmap

        ctx.store.get("products", pid)
        return envelope(build_roadmap(ctx.store, pid))

    # -- cloud intelligence (Cycle 8) ------------------------------------------

    @app.post(f"{API_PREFIX}/products/{{pid}}/cloud/inventory")
    def cloud_inventory(pid: str, body: ScopedIn, req: Request) -> dict:
        ctx.store.get("products", pid)
        p = body.model_dump()
        provider, service = p.get("provider"), p.get("service")
        try:
            if provider == "aws":
                from ..integrations import aws

                fn = {
                    "glue": lambda: aws.glue_catalog(p.get("database"), p.get("region")),
                    "quicksight": lambda: aws.quicksight_inventory(p["account_id"], p.get("region")),
                    "cost": lambda: aws.cost_summary(int(p.get("days", 30)), p.get("region")),
                }
            elif provider == "azure":
                from ..integrations import azure

                fn = {
                    "kql-verify": lambda: azure.KQLConnector(p["workspace_id"]).verify(),
                    "powerbi": lambda: azure.powerbi_inventory(p.get("token")),
                    "fabric": lambda: azure.fabric_inventory(p["workspace_id"], p.get("token")),
                }
            else:
                from ..errors import ValidationError

                raise ValidationError(f"provider must be aws|azure, got {provider}")
            if service not in fn:
                from ..errors import ValidationError

                raise ValidationError(f"service must be one of {sorted(fn)}")
            result = fn[service]()
        except ForgeError:
            raise
        ctx.audit(req, "cloud.inventory", "products", pid, product_id=pid)
        return envelope(result)

    # -- api & data-product intelligence (Cycle 9) ------------------------------

    @app.post(f"{API_PREFIX}/products/{{pid}}/apis/import", status_code=201)
    def api_import(pid: str, body: ScopedIn, req: Request) -> dict:
        from ..domain.models import EntityKind, KnowledgeEntity
        from ..integrations.apispec import load_spec, parse_asyncapi, parse_openapi

        ctx.store.get("products", pid)
        p = body.model_dump()
        spec = load_spec(p.get("spec") or p.get("spec_yaml") or "")
        try:
            parsed = parse_openapi(spec)
        except Exception:
            parsed = parse_asyncapi(spec)
        rec = {
            "id": new_id("api"),
            "schema": "productforge/ApiSpec/v1",
            "product_id": pid,
            "name": p.get("name") or parsed.get("title", "api"),
            "kind": parsed["kind"],
            "version": parsed.get("version"),
            "surface": parsed,
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }
        ctx.store.put_doc("api_specs", rec, name=rec["name"])
        n = 0
        for op in parsed.get("operations", []):
            ent = KnowledgeEntity(
                id=new_id("ent"),
                product_id=pid,
                kind=EntityKind.API,
                name=f"{op['method']} {op['path']}",
                description=op.get("summary", ""),
                confidence=0.95,
                provisional=False,
                attributes={"operation_id": op.get("operation_id"), "api_spec_id": rec["id"]},
            )
            ctx.store.put("entities", ent)
            n += 1
        ctx.audit(req, "api.import", "api_specs", rec["id"], product_id=pid)
        return envelope({"api_spec_id": rec["id"], "kind": parsed["kind"], "entities_created": n})

    @app.get(f"{API_PREFIX}/products/{{pid}}/apis")
    def api_list(pid: str) -> dict:
        ctx.store.get("products", pid)
        return envelope({"items": ctx.store.list("api_specs", product_id=pid)})

    @app.post(f"{API_PREFIX}/products/{{pid}}/apis/{{aid}}/diff")
    def api_diff(pid: str, aid: str, body: ScopedIn, req: Request) -> dict:
        from ..integrations.apispec import diff_openapi, load_spec

        rec = ctx.store.get("api_specs", aid)
        if rec.get("product_id") != pid:
            from ..errors import NotFoundError

            raise NotFoundError(f"api {aid} not in product {pid}")
        old_doc = {
            "openapi": rec["surface"].get("version"),
            "info": {"title": rec["name"]},
            "paths": _surface_to_paths(rec["surface"]),
            "components": {
                "schemas": {
                    k: {
                        "type": v["type"],
                        "required": v["required"],
                        "properties": {p_: {} for p_ in v["properties"]},
                    }
                    for k, v in rec["surface"]["schemas"].items()
                }
            },
        }
        new_spec = load_spec(body.model_dump().get("spec") or {})
        report = diff_openapi(old_doc, new_spec)
        ctx.audit(req, "api.diff", "api_specs", aid, product_id=pid)
        return envelope(report)

    @app.post(f"{API_PREFIX}/products/{{pid}}/contracts", status_code=201)
    def contract_create(pid: str, body: ScopedIn, req: Request) -> dict:
        ctx.store.get("products", pid)
        p = body.model_dump()
        rec = {
            "id": new_id("ctr"),
            "schema": "productforge/DataContract/v1",
            "product_id": pid,
            "name": p.get("name", "contract"),
            "fields": p.get("fields", []),
            "quality": p.get("quality", []),
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }
        ctx.store.put_doc("contracts", rec, name=rec["name"])
        ctx.audit(req, "contract.create", "contracts", rec["id"], product_id=pid)
        return envelope(rec)

    @app.post(f"{API_PREFIX}/products/{{pid}}/contracts/{{cid}}/validate")
    def contract_validate(pid: str, cid: str, body: ScopedIn) -> dict:
        from ..integrations.datacontract import validate_payload

        rec = ctx.store.get("contracts", cid)
        if rec.get("product_id") != pid:
            from ..errors import NotFoundError

            raise NotFoundError(f"contract {cid} not in product {pid}")
        return envelope(validate_payload(rec, body.model_dump().get("payload", {})))

    @app.get(f"{API_PREFIX}/products/{{pid}}/impact/{{eid}}")
    def impact(pid: str, eid: str) -> dict:
        from ..integrations.datacontract import impact_analysis

        ctx.store.get("products", pid)
        return envelope(impact_analysis(ctx.store, pid, eid))

    # -- product operations (Cycle 10) -------------------------------------------

    @app.post(f"{API_PREFIX}/products/{{pid}}/watches", status_code=201)
    def watch_create(pid: str, body: ScopedIn, req: Request) -> dict:
        from ..operations.watches import create_watch

        ctx.store.get("products", pid)
        w = create_watch(ctx.store, pid, body.model_dump())
        ctx.audit(req, "watch.create", "watches", w["id"], product_id=pid)
        return envelope(w)

    @app.get(f"{API_PREFIX}/products/{{pid}}/watches")
    def watch_list(pid: str) -> dict:
        ctx.store.get("products", pid)
        return envelope({"items": ctx.store.list("watches", product_id=pid)})

    @app.post(f"{API_PREFIX}/products/{{pid}}/watches/{{wid}}/run")
    def watch_run(pid: str, wid: str, req: Request) -> dict:
        from ..operations.watches import evaluate_watch

        w = ctx.store.get("watches", wid)
        if w.get("product_id") != pid:
            from ..errors import NotFoundError

            raise NotFoundError(f"watch {wid} not in product {pid}")
        res = evaluate_watch(ctx.store, w)
        ctx.audit(req, "watch.run", "watches", wid, product_id=pid)
        return envelope(res)

    @app.post(f"{API_PREFIX}/products/{{pid}}/watches/run-due")
    def watch_run_due(pid: str, req: Request) -> dict:
        from ..operations.watches import run_due

        ctx.store.get("products", pid)
        res = run_due(ctx.store, pid)
        ctx.audit(req, "watch.run-due", "products", pid, product_id=pid)
        return envelope(res)

    @app.get(f"{API_PREFIX}/products/{{pid}}/alerts")
    def alert_list(pid: str) -> dict:
        ctx.store.get("products", pid)
        return envelope({"items": ctx.store.list("alerts", product_id=pid)})

    @app.post(f"{API_PREFIX}/products/{{pid}}/alerts/{{alid}}/{{action}}")
    def alert_transition(pid: str, alid: str, action: str, req: Request) -> dict:
        a = ctx.store.get("alerts", alid)
        if a.get("product_id") != pid:
            from ..errors import NotFoundError

            raise NotFoundError(f"alert {alid} not in product {pid}")
        if action not in {"ack", "resolve", "reopen"}:
            from ..errors import ValidationError

            raise ValidationError("action must be ack|resolve|reopen")
        a["state"] = {"ack": "acknowledged", "resolve": "resolved", "reopen": "open"}[action]
        a["updated_at"] = utcnow()
        ctx.store.put_doc("alerts", a, status=a["state"])
        ctx.audit(req, f"alert.{action}", "alerts", alid, product_id=pid)
        return envelope(a)

    @app.post(f"{API_PREFIX}/products/{{pid}}/reports/executive", status_code=201)
    def report_exec(pid: str, req: Request) -> dict:
        from ..operations.reports import generate_executive

        ctx.store.get("products", pid)
        rec = generate_executive(ctx.store, pid)
        ctx.audit(req, "report.generate", "reports", rec["id"], product_id=pid)
        return envelope(rec)

    @app.get(f"{API_PREFIX}/products/{{pid}}/reports")
    def report_list(pid: str) -> dict:
        ctx.store.get("products", pid)
        return envelope({"items": ctx.store.list("reports", product_id=pid)})

    @app.post(f"{API_PREFIX}/products/{{pid}}/approvals", status_code=201)
    def approval_create(pid: str, body: ScopedIn, req: Request) -> dict:
        from ..operations.approvals import request_approval

        ctx.store.get("products", pid)
        p = body.model_dump()
        rec = request_approval(ctx.store, pid, p.get("action", ""), p.get("payload", {}), requester="api")
        ctx.audit(req, "approval.request", "approvals", rec["id"], product_id=pid)
        return envelope(rec)

    @app.post(f"{API_PREFIX}/products/{{pid}}/approvals/{{apid}}/{{decision}}")
    def approval_decide(pid: str, apid: str, decision: str, req: Request) -> dict:
        from ..operations.approvals import decide

        rec = ctx.store.get("approvals", apid)
        if rec.get("product_id") != pid:
            from ..errors import NotFoundError

            raise NotFoundError(f"approval {apid} not in product {pid}")
        rec = decide(ctx.store, apid, decision == "approve")
        ctx.audit(req, f"approval.{decision}", "approvals", apid, product_id=pid)
        return envelope(rec)

    @app.get(f"{API_PREFIX}/products/{{pid}}/approvals")
    def approval_list(pid: str) -> dict:
        ctx.store.get("products", pid)
        return envelope({"items": ctx.store.list("approvals", product_id=pid)})

    @app.post(f"{API_PREFIX}/products/{{pid}}/task-proposals", status_code=201)
    def task_proposal_create(pid: str, body: ScopedIn, req: Request) -> dict:
        from ..operations.proposals import create_proposal

        ctx.store.get("products", pid)
        values = body.model_dump()
        rec = create_proposal(
            ctx.store,
            pid,
            list(values.get("tasks") or []),
            source=str(values.get("source") or "chat"),
            session_id=str(values.get("session_id") or ""),
            idempotency_key=values.get("idempotency_key"),
        )
        ctx.audit(req, "task-proposal.create", "task_proposals", rec["id"], product_id=pid)
        return envelope(rec)

    @app.get(f"{API_PREFIX}/products/{{pid}}/task-proposals")
    def task_proposal_list(pid: str) -> dict:
        ctx.store.get("products", pid)
        return envelope({"items": ctx.store.list("task_proposals", product_id=pid)})

    @app.post(f"{API_PREFIX}/products/{{pid}}/task-proposals/{{proposal_id}}/approve")
    def task_proposal_approve(pid: str, proposal_id: str, body: ScopedIn, req: Request) -> dict:
        from ..operations.proposals import approve_proposal, revise_proposal

        ctx.store.get("products", pid)
        proposal = ctx.store.get("task_proposals", proposal_id)
        if proposal.get("product_id") != pid:
            raise NotFoundError("proposal does not belong to product")
        values = body.model_dump()
        if values.get("tasks") is not None:
            revise_proposal(ctx.store, proposal_id, list(values["tasks"]))
        if values.get("approved", True) is False:
            proposal["state"] = "rejected"
            proposal["updated_at"] = utcnow()
            rec = ctx.store.put_doc("task_proposals", proposal, status="rejected")
        else:
            rec = approve_proposal(
                ctx.store, proposal_id, reviewer="api", idempotency_key=values.get("idempotency_key")
            )
        ctx.audit(req, "task-proposal.approve", "task_proposals", proposal_id, product_id=pid)
        return envelope(rec)

    # -- advanced agentic (Cycle 11) ---------------------------------------------

    @app.post(f"{API_PREFIX}/products/{{pid}}/workflows/run")
    def workflow_run(pid: str, body: ScopedIn, req: Request) -> dict:
        from ..agents.workflows import run_workflow

        ctx.store.get("products", pid)
        rec = run_workflow(ctx.store, pid, body.model_dump())
        ctx.audit(req, "workflow.run", "workflow_runs", rec["id"], product_id=pid)
        return envelope(rec)

    @app.get(f"{API_PREFIX}/products/{{pid}}/workflows")
    def workflow_list(pid: str) -> dict:
        ctx.store.get("products", pid)
        return envelope({"items": ctx.store.list("workflow_runs", product_id=pid)})

    @app.get(f"{API_PREFIX}/products/{{pid}}/routing")
    def routing_info(pid: str, task_class: str = "synthesis") -> dict:
        from ..agents.routing import route

        ctx.store.get("products", pid)
        return envelope(route(task_class, ctx.cfg.get("gateway_profile", "balanced")))

    @app.get(f"{API_PREFIX}/products/{{pid}}/budget")
    def budget(pid: str) -> dict:
        ctx.store.get("products", pid)
        return envelope({"items": ctx.store.list("budget_ledger", product_id=pid)})

    @app.get(f"{API_PREFIX}/audit")
    def audit_log(product_id: str | None = None, limit: int = 100) -> dict:
        return envelope({"items": ctx.store.list("audit_events", product_id=product_id, limit=limit)})

    return app
