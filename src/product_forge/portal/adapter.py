"""PortalAdapter for the vendored _forge_portal server.

Ops paths are RELATIVE (server strips /api/v1). Mutating ops are
enforced confirm+rate-limited by the shared server. The adapter maps
every op to real Store calls — nothing fabricates state.
"""

from __future__ import annotations

from typing import Any

from .. import FORGE_ID, __version__
from .._forge_portal import Operation, PortalAdapter, RequestContext
from ..config import db_path, home_dir, load_config
from ..domain.models import Product, Workspace, new_id
from ..store.sqlite import Store


def _store() -> Store:
    home = home_dir()
    return Store(db_path(home, load_config(home)))


def _q1(ctx: RequestContext, key: str) -> str | None:
    vals = ctx.query.get(key)
    return vals[0] if vals else None


class ProductForgePortal(PortalAdapter):
    """Product Forge adapter — workspaces, products, context package."""

    forge_id = FORGE_ID
    forge_name = "Product Forge"
    forge_version = __version__
    cli = "productforge"
    theme = "product-forge"
    federated = True

    def __init__(self) -> None:
        super().__init__()
        self.register(Operation("GET", "/workspaces", self._ws_list))
        self.register(Operation("POST", "/workspaces", self._ws_create, mutating=True, confirm="create"))
        self.register(Operation("GET", "/products", self._products))
        self.register(Operation("POST", "/products", self._product_create, mutating=True, confirm="create"))
        self.register(Operation("GET", "/products/{pid}", self._product_get))
        self.register(Operation("GET", "/products/{pid}/context", self._product_context))
        self.register(Operation("GET", "/products/{pid}/agents", self._agents))
        self.register(Operation("POST", "/products/{pid}/knowledge/query", self._kn_query))
        self.register(Operation("GET", "/products/{pid}/graph", self._graph))
        self.register(Operation("GET", "/products/{pid}/knowledge-health", self._kn_health))
        self.register(Operation("POST", "/products/{pid}/queries/execute", self._q_exec,
                                mutating=True, confirm="execute"))
        self.register(Operation("POST", "/products/{pid}/agents/{aid}/run", self._agent_run,
                                mutating=True, confirm="run"))
        self.register(Operation("GET", "/products/{pid}/roadmap", self._roadmap))
        self.register(Operation("GET", "/products/{pid}/alerts", self._alerts))
        self.register(Operation("GET", "/audit", self._audit))

    # -- capability surface -------------------------------------------------

    def capabilities(self) -> list[dict[str, Any]]:
        return [
            {"id": "workspaces", "state": "supported"},
            {"id": "products", "state": "supported"},
            {"id": "context", "state": "supported"},
            {"id": "audit", "state": "supported"},
            {"id": "knowledge", "state": "unverified"},
            {"id": "agents", "state": "unverified"},
            {"id": "analytics", "state": "unverified"},
            {"id": "dashboards", "state": "unverified"},
            {"id": "planning", "state": "unverified"},
        ]

    def nav(self) -> list[dict[str, Any]]:
        return [
            {"id": "home", "label_key": "nav.home", "route": "/"},
            {"id": "workspaces", "label_key": "nav.workspaces", "route": "/workspaces"},
            {"id": "products", "label_key": "nav.products", "route": "/products"},
            {"id": "knowledge", "label_key": "nav.knowledge", "route": "/knowledge"},
            {"id": "agents", "label_key": "nav.agents", "route": "/agents"},
            {"id": "analytics", "label_key": "nav.analytics", "route": "/analytics"},
            {"id": "dashboards", "label_key": "nav.dashboards", "route": "/dashboards"},
            {"id": "planning", "label_key": "nav.planning", "route": "/planning"},
            {"id": "settings", "label_key": "nav.settings", "route": "/settings"},
        ]

    def health(self) -> dict[str, Any]:
        return {"forge_id": FORGE_ID, "version": __version__, "status": "healthy"}

    # -- ops ------------------------------------------------------------------

    def _ws_list(self, ctx: RequestContext) -> dict[str, Any]:
        st = _store()
        try:
            return {"items": st.list("workspaces")}
        finally:
            st.close()

    def _ws_create(self, ctx: RequestContext) -> dict[str, Any]:
        body = ctx.body or {}
        st = _store()
        try:
            ws = Workspace(id=new_id("ws"), name=body.get("name", "workspace"),
                           description=body.get("description", ""))
            st.put("workspaces", ws)
            ctx.emit("workspace.created", resource_id=ws.id)
            return ws.model_dump(mode="json", by_alias=True)
        finally:
            st.close()

    def _products(self, ctx: RequestContext) -> dict[str, Any]:
        st = _store()
        try:
            return {"items": st.list("products", workspace_id=_q1(ctx, "workspace_id"))}
        finally:
            st.close()

    def _product_get(self, ctx: RequestContext) -> dict[str, Any]:
        st = _store()
        try:
            return st.get("products", ctx.params["pid"])
        finally:
            st.close()

    def _product_create(self, ctx: RequestContext) -> dict[str, Any]:
        body = ctx.body or {}
        st = _store()
        try:
            st.get("workspaces", body["workspace_id"])
            fields = {k: v for k, v in body.items()
                      if k in {"workspace_id", "name", "description", "domain", "tags"}}
            p = Product(id=new_id("prd"), status="active", **fields)
            st.put("products", p)
            ctx.emit("product.created", resource_id=p.id)
            return p.model_dump(mode="json", by_alias=True)
        finally:
            st.close()

    def _product_context(self, ctx: RequestContext) -> dict[str, Any]:
        pid = ctx.params["pid"]
        st = _store()
        try:
            return {"schema": "productforge/ProductContextPackage/v1",
                    "product": st.get("products", pid),
                    "sources": st.list("knowledge_sources", product_id=pid, limit=200),
                    "entities": st.list("entities", product_id=pid, limit=200),
                    "agents": st.list("agents", product_id=pid, limit=100),
                    "data_sources": st.list("data_sources", product_id=pid, limit=100)}
        finally:
            st.close()

    def _agents(self, ctx: RequestContext) -> dict[str, Any]:
        st = _store()
        try:
            return {"items": st.list("agents", product_id=ctx.params["pid"])}
        finally:
            st.close()

    def _audit(self, ctx: RequestContext) -> dict[str, Any]:
        st = _store()
        try:
            return {"items": st.list("audit_events", limit=100)}
        finally:
            st.close()

    def _kn_query(self, ctx: RequestContext) -> dict[str, Any]:
        pid = ctx.params["pid"]
        question = (ctx.body or {}).get("question", "")
        st = _store()
        try:
            hits = st.search_fts(pid, question, limit=10)
            return {"question": question,
                    "citations": [{"chunk_id": h["id"], "document_id": h["document_id"],
                                   "snippet": h["snip"], "title": st.doc_title(h["document_id"])}
                                  for h in hits]}
        finally:
            st.close()

    def _graph(self, ctx: RequestContext) -> dict[str, Any]:
        from ..knowledge.graph import product_graph

        st = _store()
        try:
            return product_graph(st, ctx.params["pid"])
        finally:
            st.close()

    def _kn_health(self, ctx: RequestContext) -> dict[str, Any]:
        from ..knowledge.graph import knowledge_health

        st = _store()
        try:
            return knowledge_health(st, ctx.params["pid"])
        finally:
            st.close()

    def _q_exec(self, ctx: RequestContext) -> dict[str, Any]:
        from ..analytics.engine import compile_spec, execute_query

        body = ctx.body or {}
        statement = body.get("statement") or (
            compile_spec(body["spec"]) if body.get("spec") else None)
        st = _store()
        try:
            run = execute_query(st, ctx.params["pid"], body["source_id"], statement)
            ctx.emit("query.executed", resource_id=run["id"], status=run["status"])
            return run
        finally:
            st.close()

    def _agent_run(self, ctx: RequestContext) -> dict[str, Any]:
        from ..agents.runtime import run_agent
        from ..domain.models import AgentDefinition

        st = _store()
        try:
            agent = AgentDefinition.model_validate(st.get("agents", ctx.params["aid"]))
            run = run_agent(st, agent, (ctx.body or {}).get("input", ""), actor="portal")
            ctx.emit("agent.run", resource_id=run["id"], status=run["status"])
            return run
        finally:
            st.close()

    def _roadmap(self, ctx: RequestContext) -> dict[str, Any]:
        from ..planning.roadmap import build_roadmap

        st = _store()
        try:
            return build_roadmap(st, ctx.params["pid"])
        finally:
            st.close()

    def _alerts(self, ctx: RequestContext) -> dict[str, Any]:
        st = _store()
        try:
            return {"items": st.list("alerts", product_id=ctx.params["pid"])}
        finally:
            st.close()
