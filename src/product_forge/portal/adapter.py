"""PortalAdapter for the vendored _forge_portal server.

Ops paths are RELATIVE (server strips /api/v1). Mutating ops are
enforced confirm+rate-limited by the shared server. The adapter maps
every op to real Store calls — nothing fabricates state.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .. import FORGE_ID, __version__
from .._forge_portal import (
    Operation,
    PortalAdapter,
    PortalError,
    RequestContext,
    SseResult,
    default_operations,
)
from ..config import db_path, home_dir, load_config
from ..domain.models import Board, Initiative, Product, Task, Workspace, new_id, utcnow
from ..store.sqlite import Store


def _store() -> Store:
    home = home_dir()
    return Store(db_path(home, load_config(home)))


def _q1(ctx: RequestContext, key: str) -> str | None:
    vals = ctx.query.get(key)
    return vals[0] if vals else None


def _record_audit(st: Store, ctx: RequestContext, action: str, resource_type: str,
                  resource_id: str, *, product_id: str | None = None,
                  workspace_id: str | None = None) -> None:
    """Persist the same mutation trail exposed by the Portal audit route."""
    st.audit({
        "id": new_id("aud"),
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "product_id": product_id,
        "workspace_id": workspace_id,
        "actor": "local",
        "correlation_id": ctx.correlation_id,
        "created_at": utcnow(),
    })


class _BridgeProxyOperation(Operation):
    """Match the typed same-origin Bridge gateway without exposing its port."""

    def __init__(self, method: str, handler: Any) -> None:
        super().__init__(method, "/bridge/**", handler)
        self.proxy_method = method

    def match(self, path: str) -> dict[str, str] | None:
        prefix = "/bridge/"
        if not path.startswith(prefix) or path in {prefix, "/bridge/bootstrap"}:
            return None
        return {"bridge_path": "/" + path[len(prefix):], "__method": self.proxy_method}


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
        # Keep the operation registry instance-local.  The vendored base class
        # intentionally stays minimal and its dataclass field is also exposed
        # as a class attribute for compatibility with the sibling forges.
        self.ops = list(default_operations(self))
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
        self.register(Operation("GET", "/agent/health", self._agent_health))
        self.register(Operation("GET", "/agent/providers", self._agent_providers))
        for method in ("GET", "POST"):
            self.register(_BridgeProxyOperation(method, self._bridge_proxy))
        self.register(Operation("POST", "/bridge/bootstrap", self._bridge_bootstrap,
                                mutating=True, confirm="bootstrap"))
        self.register(Operation("POST", "/agent/providers/claude/auth", self._claude_auth,
                                mutating=True, confirm="start"))
        self.register(Operation("GET", "/chat/sessions", self._chat_sessions))
        self.register(Operation("POST", "/chat/sessions", self._chat_create,
                                mutating=True, confirm="create"))
        self.register(Operation("POST", "/chat/sessions/{sid}/prompt", self._chat_prompt,
                                mutating=True, confirm="send"))
        self.register(Operation("POST", "/chat/sessions/{sid}/events", self._chat_events))
        self.register(Operation("DELETE", "/chat/sessions/{sid}", self._chat_close,
                                mutating=True, confirm="close"))
        self.register(Operation("POST", "/products/{pid}/queries/execute", self._q_exec,
                                mutating=True, confirm="execute"))
        self.register(Operation("POST", "/products/{pid}/agents/{aid}/run", self._agent_run,
                                mutating=True, confirm="run"))
        self.register(Operation("GET", "/products/{pid}/roadmap", self._roadmap))
        self.register(Operation("GET", "/products/{pid}/initiatives", self._initiatives))
        self.register(Operation("POST", "/products/{pid}/initiatives", self._initiative_create,
                                mutating=True, confirm="create"))
        self.register(Operation("POST", "/products/{pid}/initiatives/{iid}/prioritize",
                                self._initiative_prioritize, mutating=True, confirm="prioritize"))
        self.register(Operation("GET", "/products/{pid}/boards", self._board))
        self.register(Operation("GET", "/products/{pid}/board", self._board))
        self.register(Operation("POST", "/products/{pid}/tasks", self._task_create,
                               mutating=True, confirm="create"))
        self.register(Operation("GET", "/products/{pid}/tasks", self._tasks))
        self.register(Operation("POST", "/products/{pid}/tasks/{tid}/move",
                               self._task_move, mutating=True, confirm="move"))
        self.register(Operation("POST", "/products/{pid}/task-proposals",
                               self._task_proposal_create, mutating=True, confirm="create"))
        self.register(Operation("GET", "/products/{pid}/task-proposals",
                               self._task_proposal_list))
        self.register(Operation("POST", "/products/{pid}/task-proposals/{proposal_id}/approve",
                               self._task_proposal_decide, mutating=True, confirm="decide"))
        self.register(Operation("GET", "/notifications", self._notifications))
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
            {"id": "chat", "state": "unverified"},
            {"id": "agent-bridge", "state": "unverified"},
        ]

    def nav(self) -> list[dict[str, Any]]:
        return [
            {"id": "home", "label_key": "nav.home", "route": "/"},
            {"id": "workspaces", "label_key": "nav.workspaces", "route": "/workspaces"},
            {"id": "products", "label_key": "nav.products", "route": "/products"},
            {"id": "boards", "label_key": "nav.boards", "route": "/boards"},
            {"id": "roadmaps", "label_key": "nav.roadmaps", "route": "/roadmaps"},
            {"id": "knowledge", "label_key": "nav.knowledge", "route": "/knowledge"},
            {"id": "chat", "label_key": "nav.chat", "route": "/chat"},
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
            _record_audit(st, ctx, "workspace.create", "workspaces", ws.id,
                          workspace_id=ws.id)
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
            _record_audit(st, ctx, "product.create", "products", p.id,
                          product_id=p.id, workspace_id=p.workspace_id)
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

    def _initiatives(self, ctx: RequestContext) -> dict[str, Any]:
        st = _store()
        try:
            return {"items": st.list("initiatives", product_id=ctx.params["pid"], limit=500)}
        finally:
            st.close()

    def _initiative_create(self, ctx: RequestContext) -> dict[str, Any]:
        body = ctx.body or {}
        st = _store()
        try:
            st.get("products", ctx.params["pid"])
            item = Initiative(id=new_id("ini"), product_id=ctx.params["pid"],
                              title=str(body.get("title", "")).strip(),
                              hypothesis=str(body.get("hypothesis", "")),
                              status=str(body.get("status", "proposed")))
            if not item.title:
                raise ValueError("initiative title is required")
            st.put("initiatives", item)
            ctx.emit("initiative.created", resource_id=item.id)
            return item.model_dump(mode="json", by_alias=True)
        finally:
            st.close()

    def _initiative_prioritize(self, ctx: RequestContext) -> dict[str, Any]:
        from ..planning.prioritize import score_initiative
        st = _store()
        try:
            doc = st.get("initiatives", ctx.params["iid"])
            if doc.get("product_id") != ctx.params["pid"]:
                raise KeyError(ctx.params["iid"])
            result = score_initiative(doc, (ctx.body or {}).get("factors", {}))
            doc["priority_score"] = result["score"]
            doc["status"] = "prioritized"
            st.put("initiatives", Initiative.model_validate(doc))
            ctx.emit("initiative.prioritized", resource_id=ctx.params["iid"])
            return result
        finally:
            st.close()

    def _board(self, ctx: RequestContext) -> dict[str, Any]:
        st = _store()
        try:
            product = st.get("products", ctx.params["pid"])
            boards = st.list("boards", product_id=ctx.params["pid"], limit=20)
            board = boards[0] if boards else None
            if board is None:
                board = Board(id=new_id("brd"), workspace_id=product["workspace_id"],
                              product_id=ctx.params["pid"],
                              name=f"{product['name']} board")
                st.put("boards", board)
            tasks = st.list("tasks", product_id=ctx.params["pid"], limit=1000)
            columns = {str(c.get("id")): [] for c in board.get("columns", [])}
            for task in tasks:
                columns.setdefault(str(task.get("column_id", "backlog")), []).append(task)
            return {"schema": "productforge/Board/v1", "product_id": ctx.params["pid"],
                    "board": board, "columns": columns, "tasks": tasks,
                    "items": self._initiatives(ctx)["items"]}
        finally:
            st.close()

    def _tasks(self, ctx: RequestContext) -> dict[str, Any]:
        st = _store()
        try:
            return {"items": st.list("tasks", product_id=ctx.params["pid"], limit=1000)}
        finally:
            st.close()

    def _task_create(self, ctx: RequestContext) -> dict[str, Any]:
        body = ctx.body or {}
        st = _store()
        try:
            product = st.get("products", ctx.params["pid"])
            boards = st.list("boards", product_id=ctx.params["pid"], limit=1)
            board = boards[0] if boards else Board(
                id=new_id("brd"), workspace_id=product["workspace_id"],
                product_id=ctx.params["pid"], name=f"{product['name']} board")
            if not boards:
                st.put("boards", board)
            board_id = board.id if isinstance(board, Board) else board["id"]
            task = Task(id=new_id("tsk"), workspace_id=product["workspace_id"],
                        product_id=ctx.params["pid"], board_id=board_id,
                        title=str(body.get("title", "")).strip(),
                        description=str(body.get("description", "")),
                        column_id=str(body.get("column_id", "backlog")),
                        priority=str(body.get("priority", "medium")))
            if not task.title:
                raise ValueError("task title is required")
            st.put("tasks", task)
            _record_audit(st, ctx, "task.create", "tasks", task.id,
                          product_id=task.product_id, workspace_id=task.workspace_id)
            ctx.emit("task.created", resource_id=task.id)
            return task.model_dump(mode="json", by_alias=True)
        finally:
            st.close()

    def _task_move(self, ctx: RequestContext) -> dict[str, Any]:
        st = _store()
        try:
            doc = st.get("tasks", ctx.params["tid"])
            if doc.get("product_id") != ctx.params["pid"]:
                raise KeyError(ctx.params["tid"])
            expected = (ctx.body or {}).get("expected_version")
            if expected is not None and int(expected) != int(doc.get("version", 1)):
                raise ValueError("task changed; reload before moving")
            doc["column_id"] = str((ctx.body or {}).get("column_id", "backlog"))
            doc["position"] = int((ctx.body or {}).get("position", doc.get("position", 0)))
            doc["version"] = int(doc.get("version", 1)) + 1
            st.put("tasks", Task.model_validate(doc))
            ctx.emit("task.moved", resource_id=ctx.params["tid"],
                     column_id=doc["column_id"])
            return doc
        finally:
            st.close()

    def _task_proposal_create(self, ctx: RequestContext) -> dict[str, Any]:
        from ..operations.proposals import create_proposal

        body = ctx.body or {}
        st = _store()
        try:
            st.get("products", ctx.params["pid"])
            rec = create_proposal(
                st,
                ctx.params["pid"],
                list(body.get("tasks") or []),
                source=str(body.get("source") or "chat"),
                session_id=str(body.get("session_id") or ""),
                idempotency_key=body.get("idempotency_key"),
            )
            ctx.emit("task-proposal.created", resource_id=rec["id"])
            return rec
        finally:
            st.close()

    def _task_proposal_list(self, ctx: RequestContext) -> dict[str, Any]:
        st = _store()
        try:
            st.get("products", ctx.params["pid"])
            return {"items": st.list("task_proposals", product_id=ctx.params["pid"], limit=500)}
        finally:
            st.close()

    def _task_proposal_decide(self, ctx: RequestContext) -> dict[str, Any]:
        from ..operations.proposals import approve_proposal, revise_proposal

        body = ctx.body or {}
        st = _store()
        try:
            proposal = st.get("task_proposals", ctx.params["proposal_id"])
            if proposal.get("product_id") != ctx.params["pid"]:
                raise KeyError(ctx.params["proposal_id"])
            if body.get("tasks") is not None:
                proposal = revise_proposal(st, ctx.params["proposal_id"], list(body["tasks"]))
            if body.get("approved", True) is False:
                proposal["state"] = "rejected"
                proposal["updated_at"] = utcnow()
                rec = st.put_doc("task_proposals", proposal, status="rejected")
            else:
                rec = approve_proposal(
                    st,
                    ctx.params["proposal_id"],
                    reviewer="portal",
                    idempotency_key=body.get("idempotency_key"),
                )
            ctx.emit("task-proposal.decided", resource_id=ctx.params["proposal_id"],
                     approved=bool(body.get("approved", True)))
            return rec
        finally:
            st.close()

    def _notifications(self, ctx: RequestContext) -> dict[str, Any]:
        st = _store()
        try:
            return {"items": st.list("alerts", limit=100) + st.list("notifications", limit=100),
                    "delivery": "approval-gated-webhook-or-smtp"}
        finally:
            st.close()

    def _alerts(self, ctx: RequestContext) -> dict[str, Any]:
        st = _store()
        try:
            return {"items": st.list("alerts", product_id=ctx.params["pid"])}
        finally:
            st.close()

    @staticmethod
    def _bridge_request(path: str, *, method: str = "GET",
                        body: dict[str, Any] | None = None,
                        token_override: str = "") -> dict[str, Any]:
        base = os.environ.get("FORGE_BRIDGE_URL", "http://127.0.0.1:8471").rstrip("/")
        parsed = urllib.parse.urlsplit(base)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
            "127.0.0.1", "localhost", "::1"
        }:
            return {"state": "unavailable", "reason": "non_loopback_bridge_url"}
        token_file = Path(os.environ.get(
            "FORGE_BRIDGE_TOKEN_FILE", "~/.forge-bridge/pair.token"
        )).expanduser()
        headers = {"Accept": "application/json"}
        token = token_override
        if not token:
            try:
                token = token_file.read_text(encoding="utf-8").strip()
            except OSError:
                token = ""
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(  # noqa: S310 - URL validated above
            f"{base}{path}", data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=2) as response:  # noqa: S310 - loopback validated above
                payload = json.loads(response.read().decode("utf-8"))
                return payload if isinstance(payload, dict) else {"items": payload}
        except urllib.error.HTTPError as exc:
            try:
                detail = json.loads(exc.read().decode("utf-8"))
            except (OSError, ValueError):
                detail = {"message": str(exc)}
            return {"state": "error", "status": exc.code, "error": detail}
        except (OSError, ValueError, urllib.error.URLError) as exc:
            return {"state": "unavailable", "reason": type(exc).__name__}

    @staticmethod
    def _bridge_get(path: str) -> dict[str, Any]:
        return ProductForgePortal._bridge_request(path)

    def _bridge_proxy(self, ctx: RequestContext) -> dict[str, Any]:
        """Forward a Bridge contract through this process' same-origin API.

        The browser never receives the master pair token or the Bridge URL.
        The adapter adds the internal credential server-side and maps upstream
        failures to the PortalApi envelope through ``PortalError``.
        ``_method`` is accepted only for the small set of legacy UI actions
        that used PATCH/DELETE before the gateway existed.
        """
        body = dict(ctx.body or {})
        method = str(body.pop("_method", ctx.params.get("__method", "GET"))).upper()
        path = ctx.params["bridge_path"]
        allowed = ("/status", "/providers", "/diagnostics", "/mcp/doctor",
                   "/agent-sessions", "/approvals", "/files", "/intel")
        if not path.startswith(allowed) or path in {"/pair/exchange", "/pair/rotate"}:
            raise PortalError(
                "BRIDGE-GATEWAY-FORBIDDEN",
                "operation is not exposed by the Product Forge gateway",
                http=403,
            )
        gateway_token = getattr(self, "_gateway_bridge_token", "")
        if not gateway_token:
            raise PortalError(
                "BRIDGE-SESSION-REQUIRED",
                "Bridge gateway session is not initialized; retry bootstrap",
                http=503,
                retryable=True,
            )
        query = ""
        if ctx.query:
            allowed_query = {"after_seq", "limit"}
            pairs: list[tuple[str, str]] = []
            for key, values in ctx.query.items():
                if key not in allowed_query:
                    continue
                for value in values[:1]:
                    if key == "after_seq" and (not value.isdigit() or int(value) < 0):
                        raise PortalError(
                            "BRIDGE-BAD-CURSOR",
                            "after_seq must be a non-negative integer",
                            http=422,
                        )
                    pairs.append((key, value))
            if pairs:
                query = "?" + urllib.parse.urlencode(pairs)
        if method == "GET" and path.endswith("/stream"):
            last_event_id = ctx.handler.headers.get("Last-Event-ID", "").strip()
            if last_event_id and not last_event_id.isdigit():
                raise PortalError("BRIDGE-BAD-CURSOR", "Last-Event-ID must be numeric", http=422)
            if last_event_id and "after_seq" not in query:
                query = "?" + urllib.parse.urlencode({"after_seq": last_event_id})
            return self._bridge_stream(path + query, token_override=gateway_token)
        result = self._bridge_request(
            path,
            method=method,
            body=body or None,
            token_override=gateway_token,
        )
        status = result.get("status")
        if isinstance(status, int) and status >= 400:
            detail = result.get("error") or result
            raise PortalError(
                "BRIDGE-UPSTREAM",
                "Agent Bridge rejected the request",
                http=status if status in {400, 401, 403, 404, 409, 429, 500, 502, 503, 504} else 502,
                retryable=status in {408, 429, 500, 502, 503, 504},
                details=detail if isinstance(detail, dict) else None,
            )
        return result

    @staticmethod
    def _bridge_stream(path: str, *, token_override: str) -> SseResult:
        """Relay Bridge SSE frames through the canonical same-origin server.

        The Portal server owns the browser connection; this adapter owns the
        loopback connection to Bridge.  Events remain incremental and retain
        their native ``seq``/``id`` fields, so the Angular client can reconnect
        with its cursor instead of receiving one buffered JSON document.
        """
        base = os.environ.get("FORGE_BRIDGE_URL", "http://127.0.0.1:8471").rstrip("/")
        parsed = urllib.parse.urlsplit(base)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
            "127.0.0.1", "localhost", "::1"
        }:
            raise PortalError("BRIDGE-GATEWAY-FORBIDDEN", "bridge URL must be loopback", http=403)
        request = urllib.request.Request(  # noqa: S310 - loopback URL validated
            f"{base}{path}",
            headers={
                "Authorization": f"Bearer {token_override}",
                "Accept": "text/event-stream",
            },
        )
        try:
            response = urllib.request.urlopen(request, timeout=65)  # noqa: S310 - validated loopback
        except (OSError, urllib.error.URLError) as exc:
            raise PortalError(
                "BRIDGE-UPSTREAM",
                "Agent Bridge stream is unavailable",
                http=503,
                retryable=True,
                details={"reason": type(exc).__name__},
            ) from exc

        def events():
            current: dict[str, Any] = {}
            try:
                for raw in response:
                    line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                    if not line:
                        data = current.pop("data", None)
                        if data:
                            try:
                                event = json.loads(data)
                            except json.JSONDecodeError:
                                event = {"type": "bridge.raw", "payload": {"data": data}}
                            if isinstance(event, dict):
                                # Keep the native SSE cursor/type available to
                                # same-origin clients even when the upstream
                                # JSON payload does not repeat them.
                                sse_id = current.get("id")
                                sse_event = current.get("event")
                                if sse_id and "seq" not in event and sse_id.isdigit():
                                    event["seq"] = int(sse_id)
                                if sse_event and "type" not in event:
                                    event["type"] = sse_event
                                if sse_id:
                                    event["sse_id"] = sse_id
                                if sse_event:
                                    event["sse_event"] = sse_event
                                if "retry" in current:
                                    event["sse_retry"] = current["retry"]
                                yield event
                        current = {}
                        continue
                    if line.startswith(":"):
                        continue
                    key, _, value = line.partition(":")
                    value = value.lstrip()
                    if key == "data" and key in current:
                        current[key] += "\n" + value
                    else:
                        current[key] = value
            finally:
                response.close()

        return SseResult(events())

    def _agent_health(self, ctx: RequestContext) -> dict[str, Any]:
        return self._bridge_get("/status")

    def _agent_providers(self, ctx: RequestContext) -> dict[str, Any]:
        return self._bridge_get("/providers")

    def _bridge_bootstrap(self, ctx: RequestContext) -> dict[str, Any]:
        """Bring the managed Bridge into the gateway session.

        Pairing is deliberately server-side.  The browser receives a health
        result only; neither the master pair token, an internal URL nor a
        Bridge bearer token crosses the Portal boundary.
        """
        token_file = Path(os.environ.get(
            "FORGE_BRIDGE_TOKEN_FILE", "~/.forge-bridge/pair.token"
        )).expanduser()
        try:
            master = token_file.read_text(encoding="utf-8").strip()
        except OSError:
            return {"connected": False, "bridge": {"state": "unavailable", "reason": "pair_token_missing"}}
        if not master:
            return {"connected": False, "bridge": {"state": "unavailable", "reason": "pair_token_empty"}}
        result = self._bridge_request("/pair/exchange", method="POST", body={
            "pair_token": master,
            "device_name": "product-forge-portal",
            "scopes": ["agent"],
        })
        if "session_token" not in result:
            return {"connected": False, "bridge": result}
        # Keep this credential server-side for subsequent proxy calls.  The
        # short-lived exchanged token is held in process memory only.
        self._gateway_bridge_token = str(result["session_token"])
        return {
            "connected": True,
            "bridge": {"state": "ready", "capabilities": ["sessions", "streaming"]},
            "device": {"device_id": "gateway", "device_name": "Product Forge gateway",
                        "scopes": ["agent"], "created_at": 0, "expires_at": 0, "last_seen": 0},
        }

    def _claude_auth(self, ctx: RequestContext) -> dict[str, Any]:
        return self._bridge_request("/providers/claude-code/auth", method="POST",
                                    body=dict(ctx.body or {}))

    def _chat_sessions(self, ctx: RequestContext) -> dict[str, Any]:
        return self._bridge_get("/agent-sessions")

    def _chat_create(self, ctx: RequestContext) -> dict[str, Any]:
        body = dict(ctx.body or {})
        if not str(body.get("provider", "")).strip():
            raise PortalError(
                "PROVIDER-REQUIRED",
                "select an installed and authenticated AI provider before starting a chat",
                http=422,
                action="connect-provider",
            )
        return self._bridge_request("/agent-sessions", method="POST", body=body)

    def _chat_prompt(self, ctx: RequestContext) -> dict[str, Any]:
        return self._bridge_request(
            f"/agent-sessions/{ctx.params['sid']}/prompt",
            method="POST", body=dict(ctx.body or {}))

    def _chat_events(self, ctx: RequestContext) -> dict[str, Any]:
        return self._bridge_request(
            f"/agent-sessions/{ctx.params['sid']}/events",
            method="POST", body=dict(ctx.body or {}))

    def _chat_close(self, ctx: RequestContext) -> dict[str, Any]:
        return self._bridge_request(
            f"/agent-sessions/{ctx.params['sid']}", method="DELETE")
