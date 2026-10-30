"""HTTP API — forge/PortalApi/1 envelope, bearer auth, audit.

Every response uses the shared envelope: {schema, correlation_id, data|error}.
Mutations require the local bearer token (productforge api token --show).
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .. import API_PREFIX, ENVELOPE_SCHEMA, FORGE_ID, __version__
from ..config import db_path, home_dir, load_config
from ..domain.models import (
    AgentDefinition,
    Dashboard,
    DataSource,
    Decision,
    Initiative,
    KnowledgeSource,
    Product,
    Workspace,
    new_id,
    utcnow,
)
from ..errors import ForgeError
from ..security import TokenStore, redact
from ..store.sqlite import Store

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


def _surface_to_paths(surface: dict[str, Any]) -> dict[str, Any]:
    """Rebuild an OpenAPI paths dict from a stored parsed surface."""
    paths: dict[str, Any] = {}
    for op in surface.get("operations", []):
        paths.setdefault(op["path"], {})[op["method"].lower()] = {
            "operationId": op.get("operation_id"),
            "summary": op.get("summary", ""),
            "parameters": [{"name": p["name"], "in": p["in"], "required": p["required"],
                            "schema": {"type": p.get("type")}} for p in op.get("params", [])],
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
        err = {"code": f"HTTP-{exc.status_code}", "message": str(exc.detail),
               "severity": "error", "retryable": exc.status_code >= 500}
        return JSONResponse(status_code=exc.status_code, content=envelope(error=err))

    @app.exception_handler(Exception)
    async def _exc(_req: Request, exc: Exception) -> JSONResponse:
        err = {"code": "PF-INTERNAL", "message": "internal error",
               "severity": "error", "retryable": True}
        return JSONResponse(status_code=500, content=envelope(error=err))

    @app.middleware("http")
    async def _guard(req: Request, call_next):  # type: ignore[no-untyped-def]
        req.state.cid = _cid()
        if req.url.path.startswith(API_PREFIX) and req.url.path != f"{API_PREFIX}/health":
            if not ctx.rate_ok():
                err = {"code": "PF-RATE-LIMIT", "message": "rate limit",
                       "severity": "warning", "retryable": True}
                return JSONResponse(status_code=429, content=envelope(error=err, cid=req.state.cid))
            if req.method in {"POST", "PUT", "PATCH", "DELETE"}:
                auth = req.headers.get("authorization", "")
                if not ctx.tokens.check(auth.removeprefix("Bearer ").strip()):
                    err = {"code": "PF-UNAUTHORIZED", "message": "invalid or missing token",
                           "severity": "error", "retryable": False}
                    return JSONResponse(status_code=401, content=envelope(error=err, cid=req.state.cid))
            if int(req.headers.get("content-length", 0)) > MAX_BODY:
                err = {"code": "PF-PAYLOAD-TOO-LARGE", "message": "payload too large",
                       "severity": "warning", "retryable": False}
                return JSONResponse(status_code=413, content=envelope(error=err, cid=req.state.cid))
        resp = await call_next(req)
        resp.headers["X-Correlation-Id"] = req.state.cid
        resp.headers["Cache-Control"] = "no-store"
        return resp

    def _d(body: BaseModel) -> dict[str, Any]:
        return redact(body.model_dump(exclude_unset=True, by_alias=True))

    # -- platform ---------------------------------------------------------

    @app.get(f"{API_PREFIX}/health")
    def health() -> dict:
        return envelope({"forge_id": FORGE_ID, "version": __version__,
                         "status": "healthy", "uptime_s": round(time.time() - ctx.started, 2)})

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
    def list_ws(limit: int = 100, offset: int = 0) -> dict:
        return envelope({"items": ctx.store.list("workspaces", limit=limit, offset=offset)})

    @app.get(f"{API_PREFIX}/workspaces/{{wid}}")
    def get_ws(wid: str) -> dict:
        return envelope(ctx.store.get("workspaces", wid))

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
        ctx.audit(req, "product.create", "product", p.id,
                  product_id=p.id, workspace_id=p.workspace_id)
        return envelope(p.model_dump(mode="json", by_alias=True))

    @app.get(f"{API_PREFIX}/products")
    def list_products(workspace_id: str | None = None, limit: int = 100, offset: int = 0) -> dict:
        return envelope({"items": ctx.store.list("products", workspace_id=workspace_id,
                                                 limit=limit, offset=offset)})

    @app.get(f"{API_PREFIX}/products/{{pid}}")
    def get_product(pid: str) -> dict:
        return envelope(ctx.store.get("products", pid))

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

    # -- generic collection factory -------------------------------------------

    def _crud(path: str, collection: str, model: type, in_fields: set[str]) -> None:
        @app.post(f"{API_PREFIX}/products/{{pid}}/{path}", status_code=201)
        def _create(pid: str, body: ScopedIn, req: Request, p=path, c=collection, m=model) -> dict:  # type: ignore[misc]
            ctx.store.get("products", pid)
            data = {k: v for k, v in body.model_dump(by_alias=True).items() if k in in_fields}
            data["product_id"] = pid
            ent = m(id=new_id(p.rstrip("s")[:3]), **data)
            ctx.store.put(c, ent)
            ctx.audit(req, f"{p}.create", c, ent.id, product_id=pid,
                      workspace_id=ctx.store.get("products", pid).get("workspace_id"))
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

    _crud("sources", "knowledge_sources", KnowledgeSource,
          {"name", "type", "locator", "classification", "metadata"})
    _crud("agents", "agents", AgentDefinition,
          {"name", "mission", "template", "knowledge_scope", "tools_allowed", "policies"})
    _crud("data-sources", "data_sources", DataSource,
          {"name", "connector", "locator", "dialect", "catalog_allowlist"})
    _crud("dashboards", "dashboards", Dashboard, {"name", "description", "widgets", "filters"})
    _crud("initiatives", "initiatives", Initiative, {"title", "hypothesis", "priority_score"})
    _crud("decisions", "decisions", Decision, {"title", "context", "decision", "alternatives"})

    # -- knowledge (Cycle 3) ---------------------------------------------------

    @app.post(f"{API_PREFIX}/products/{{pid}}/knowledge/query")
    def kn_query(pid: str, body: QueryIn) -> dict:
        ctx.store.get("products", pid)
        hits = ctx.store.search_fts(pid, body.question, limit=body.limit)
        return envelope({"question": body.question,
                         "citations": [{"chunk_id": h["id"], "document_id": h["document_id"],
                                        "snippet": h["snip"], "title": ctx.store.doc_title(h["document_id"])}
                                       for h in hits],
                         "answer": None,
                         "synthesis": "unavailable:no-llm-provider"})

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
        return envelope({"entities": len(ents), "relations": len(rels),
                         "kinds": {k: sum(1 for e in ents if e.kind.value == k)
                                   for k in {e.kind.value for e in ents}}})

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
        doc = Document(id=new_id("doc"), product_id=pid,
                       title=str(body.model_dump().get("title", "untitled")),
                       content_hash=sha256_text(text), status=DocumentStatus.IMPORTED)
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
        run = run_agent(ctx.store, agent, body.input)
        ctx.audit(req, "agent.run", "agent_runs", run["id"], product_id=pid)
        return envelope(run)

    @app.get(f"{API_PREFIX}/products/{{pid}}/agents/{{aid}}/runs")
    def agent_runs(pid: str, aid: str) -> dict:
        _agent(pid, aid)
        runs = [r for r in ctx.store.list("agent_runs", product_id=pid)
                if r.get("agent_id") == aid]
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
        cases = (body.model_dump().get("cases") if body else None)
        report = run_evals(ctx.store, agent, cases)
        agent.eval_summary = {"score": report["score"], "passed": report["passed"],
                              "total": report["total"], "at": utcnow()}
        ctx.store.put("agents", agent)
        ctx.audit(req, "agent.eval", "agents", aid, product_id=pid)
        return envelope(report)

    @app.post(f"{API_PREFIX}/products/{{pid}}/agents/{{aid}}/publish")
    def agent_publish(pid: str, aid: str, req: Request) -> dict:
        from ..errors import UnsafeOperationError

        agent = _agent(pid, aid)
        score = (agent.eval_summary or {}).get("score", 0)
        if not agent.tools_allowed:
            raise UnsafeOperationError("agent has no tools_allowed — configure permissions first")
        if score < 0.5:
            raise UnsafeOperationError(f"eval score {score} below publish gate 0.5")
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

    @app.patch(f"{API_PREFIX}/products/{{pid}}/agents/{{aid}}")
    def agent_patch(pid: str, aid: str, body: ScopedIn, req: Request) -> dict:
        agent = _agent(pid, aid)
        data = body.model_dump(exclude_unset=True)
        for k in ("mission", "tools_allowed", "knowledge_scope", "policies", "name"):
            if k in data:
                setattr(agent, k, data[k])
        ctx.store.put("agents", agent)
        ctx.audit(req, "agent.update", "agents", aid, product_id=pid)
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

    @app.post(f"{API_PREFIX}/products/{{pid}}/queries/nl")
    def q_nl(pid: str, body: NlIn) -> dict:
        from ..analytics.engine import compile_spec, nl_to_sql

        ctx.store.get("products", pid)
        tables: list[str] = []
        if body.source_id:
            ds = ctx.store.get("data_sources", body.source_id)
            tables = ds.get("catalog_allowlist", [])
        res = nl_to_sql(body.question, tables)
        if res.get("ok"):
            res["sql"] = compile_spec(res["spec"])
        return envelope(res)

    @app.post(f"{API_PREFIX}/products/{{pid}}/queries/execute")
    def q_execute(pid: str, body: ExecuteIn, req: Request) -> dict:
        from ..analytics.engine import compile_spec, execute_query

        ctx.store.get("products", pid)
        statement = body.statement or (compile_spec(body.spec) if body.spec else None)
        if not statement:
            from ..errors import ValidationError
            raise ValidationError("statement or spec required")
        run = execute_query(ctx.store, pid, body.source_id, statement,
                            row_limit=body.row_limit, timeout_s=body.timeout_s)
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

    @app.get(f"{API_PREFIX}/products/{{pid}}/data-sources/{{sid}}/schema")
    def ds_schema(pid: str, sid: str) -> dict:
        from ..analytics.connectors import connector_for

        ds = ctx.store.get("data_sources", sid)
        if ds.get("product_id") != pid:
            from ..errors import NotFoundError
            raise NotFoundError(f"data source {sid} not in product {pid}")
        return envelope(connector_for(ds).schema())

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
            result = connector_for(doc).verify()
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
        factors = (body.model_dump() if body else {})
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

                fn = {"glue": lambda: aws.glue_catalog(p.get("database"), p.get("region")),
                      "quicksight": lambda: aws.quicksight_inventory(p["account_id"], p.get("region")),
                      "cost": lambda: aws.cost_summary(int(p.get("days", 30)), p.get("region"))}
            elif provider == "azure":
                from ..integrations import azure

                fn = {"kql-verify": lambda: azure.KQLConnector(p["workspace_id"]).verify(),
                      "powerbi": lambda: azure.powerbi_inventory(p.get("token")),
                      "fabric": lambda: azure.fabric_inventory(p["workspace_id"], p.get("token"))}
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
        rec = {"id": new_id("api"), "schema": "productforge/ApiSpec/v1",
               "product_id": pid, "name": p.get("name") or parsed.get("title", "api"),
               "kind": parsed["kind"], "version": parsed.get("version"),
               "surface": parsed, "created_at": utcnow(), "updated_at": utcnow()}
        ctx.store.put_doc("api_specs", rec, name=rec["name"])
        n = 0
        for op in parsed.get("operations", []):
            ent = KnowledgeEntity(id=new_id("ent"), product_id=pid, kind=EntityKind.API,
                                  name=f"{op['method']} {op['path']}",
                                  description=op.get("summary", ""), confidence=0.95,
                                  provisional=False,
                                  attributes={"operation_id": op.get("operation_id"),
                                              "api_spec_id": rec["id"]})
            ctx.store.put("entities", ent)
            n += 1
        ctx.audit(req, "api.import", "api_specs", rec["id"], product_id=pid)
        return envelope({"api_spec_id": rec["id"], "kind": parsed["kind"],
                         "entities_created": n})

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
        old_doc = {"openapi": rec["surface"].get("version"),
                   "info": {"title": rec["name"]},
                   "paths": _surface_to_paths(rec["surface"]),
                   "components": {"schemas": {k: {"type": v["type"], "required": v["required"],
                                                  "properties": {p_: {} for p_ in v["properties"]}}
                                              for k, v in rec["surface"]["schemas"].items()}}}
        new_spec = load_spec(body.model_dump().get("spec") or {})
        report = diff_openapi(old_doc, new_spec)
        ctx.audit(req, "api.diff", "api_specs", aid, product_id=pid)
        return envelope(report)

    @app.post(f"{API_PREFIX}/products/{{pid}}/contracts", status_code=201)
    def contract_create(pid: str, body: ScopedIn, req: Request) -> dict:
        ctx.store.get("products", pid)
        p = body.model_dump()
        rec = {"id": new_id("ctr"), "schema": "productforge/DataContract/v1",
               "product_id": pid, "name": p.get("name", "contract"),
               "fields": p.get("fields", []), "quality": p.get("quality", []),
               "created_at": utcnow(), "updated_at": utcnow()}
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
        rec = request_approval(ctx.store, pid, p.get("action", ""),
                               p.get("payload", {}), requester="api")
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
