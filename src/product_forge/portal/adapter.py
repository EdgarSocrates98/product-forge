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

from pydantic import ValidationError

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
from ..knowledge.obsidian import (
    ObsidianVaultError,
    export_vault_document,
    import_vault_document,
    list_obsidian_receipts,
    plan_vault_sync,
)
from ..knowledge.search import search_knowledge
from ..knowledge.url import UrlCaptureError, fetch_url_document
from ..knowledge.versions import explorer_versions, prepare_version
from ..store.sqlite import Store
from ..workspace.discovery import (
    WorkspaceDiscoveryError,
    discover_workspace,
    import_workspace_document,
    preview_workspace_document,
)


def _store() -> Store:
    home = home_dir()
    return Store(db_path(home, load_config(home)))


def _q1(ctx: RequestContext, key: str) -> str | None:
    vals = ctx.query.get(key)
    return vals[0] if vals else None


def _obsidian_vault() -> Path:
    raw = os.environ.get("FORGE_OBSIDIAN_VAULT", "").strip()
    if not raw:
        raise PortalError("OBSIDIAN-NOT-CONFIGURED", "Obsidian vault is not configured", http=422)
    return Path(raw)


def _require(st: Store, collection: str, key: str) -> dict[str, Any]:
    """Entity lookup that fails with a typed 404 instead of a generic 500.

    ``Store.get`` raises bare ``KeyError``; the vendored server maps any
    non-PortalError to ``PORTAL-INTERNAL``, so missing entities must be
    translated at the adapter boundary to keep ``not found`` honest.
    """
    try:
        return st.get(collection, key)
    except KeyError:
        raise PortalError(
            "PORTAL-NOT-FOUND",
            f"{collection} '{key}' not found",
            http=404,
        ) from None


def _translate_handler_errors(handler: Any) -> Any:
    """Map residual store/validation errors to typed envelope errors.

    Ops should prefer ``_require``/``ctx.require``; this guard is the safety
    net so a ``ValueError`` (bad int, model coercion) still lands as 422 and a
    stray ``KeyError`` as 404 — never as ``PORTAL-INTERNAL`` 500.
    """
    import functools

    @functools.wraps(handler)
    def wrapper(ctx: RequestContext) -> Any:
        try:
            return handler(ctx)
        except PortalError:
            raise
        except ValidationError as exc:
            raise PortalError(
                "PORTAL-VALIDATION",
                f"invalid document payload: {exc.errors()[0].get('msg', 'validation failed')}",
                http=422,
            ) from exc
        except ValueError as exc:
            raise PortalError(
                "PORTAL-VALIDATION",
                str(exc) or "invalid request payload",
                http=422,
            ) from exc
        except KeyError as exc:
            missing = exc.args[0] if exc.args else "?"
            raise PortalError(
                "PORTAL-NOT-FOUND",
                f"required field or resource not found: {missing}",
                http=404,
            ) from exc

    return wrapper


def _record_audit(
    st: Store,
    ctx: RequestContext,
    action: str,
    resource_type: str,
    resource_id: str,
    *,
    product_id: str | None = None,
    workspace_id: str | None = None,
) -> None:
    """Persist the same mutation trail exposed by the Portal audit route."""
    st.audit(
        {
            "id": new_id("aud"),
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "product_id": product_id,
            "workspace_id": workspace_id,
            "actor": "local",
            "correlation_id": ctx.correlation_id,
            "created_at": utcnow(),
        }
    )


class _BridgeProxyOperation(Operation):
    """Match the typed same-origin Bridge gateway without exposing its port."""

    def __init__(self, method: str, handler: Any) -> None:
        super().__init__(method, "/bridge/**", handler)
        self.proxy_method = method
        # Proxied POSTs can be agent turns (prompt/resume) that drain
        # synchronously on the Bridge — they need a real turn budget.
        if method == "POST":
            self.timeout = 300.0

    def match(self, path: str) -> dict[str, str] | None:
        prefix = "/bridge/"
        if not path.startswith(prefix) or path in {prefix, "/bridge/bootstrap"}:
            return None
        return {"bridge_path": "/" + path[len(prefix) :], "__method": self.proxy_method}


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
        # Wired by portal.runtime when the managed Bridge is supervised.
        # Without it, health() reports the honest `unverified` state.
        self.bridge_status: Any = None
        self.register(Operation("GET", "/workspaces", self._ws_list))
        self.register(Operation("POST", "/workspaces", self._ws_create, mutating=True, confirm="create"))
        self.register(Operation("GET", "/products", self._products))
        self.register(Operation("POST", "/products", self._product_create, mutating=True, confirm="create"))
        self.register(Operation("GET", "/products/{pid}", self._product_get))
        self.register(Operation("GET", "/products/{pid}/context", self._product_context))
        self.register(Operation("GET", "/products/{pid}/documents/search", self._document_search))
        self.register(Operation("GET", "/products/{pid}/knowledge/search", self._knowledge_search))
        self.register(Operation("GET", "/products/{pid}/documents/{did}", self._document_detail))
        self.register(Operation("GET", "/workspace/discovery", self._workspace_discovery))
        self.register(Operation("GET", "/workspace/discovery/preview", self._workspace_preview))
        self.register(
            Operation(
                "POST",
                "/products/{pid}/documents/from-workspace",
                self._workspace_document_import,
                mutating=True,
                confirm="import",
            )
        )
        self.register(Operation("GET", "/products/{pid}/documents/url/preview", self._url_preview))
        self.register(
            Operation(
                "POST",
                "/products/{pid}/documents/from-url",
                self._url_document_import,
                mutating=True,
                confirm="import",
            )
        )
        self.register(Operation("GET", "/products/{pid}/documents/obsidian/preview", self._obsidian_preview))
        self.register(Operation("GET", "/products/{pid}/documents/obsidian/history", self._obsidian_history))
        self.register(
            Operation(
                "POST",
                "/products/{pid}/documents/from-obsidian",
                self._obsidian_import,
                mutating=True,
                confirm="import",
            )
        )
        self.register(
            Operation(
                "POST",
                "/products/{pid}/documents/to-obsidian",
                self._obsidian_export,
                mutating=True,
                confirm="export",
            )
        )
        self.register(
            Operation(
                "POST",
                "/products/{pid}/documents/obsidian/sync-plan",
                self._obsidian_sync_plan,
            )
        )
        self.register(Operation("GET", "/products/{pid}/agents", self._agents))
        self.register(Operation("POST", "/products/{pid}/knowledge/query", self._kn_query))
        self.register(Operation("GET", "/products/{pid}/graph", self._graph))
        self.register(Operation("GET", "/products/{pid}/knowledge-health", self._kn_health))
        self.register(Operation("GET", "/agent/health", self._agent_health))
        self.register(Operation("GET", "/agent/providers", self._agent_providers))
        for method in ("GET", "POST"):
            self.register(_BridgeProxyOperation(method, self._bridge_proxy))
        self.register(
            Operation("POST", "/bridge/bootstrap", self._bridge_bootstrap, mutating=True, confirm="bootstrap")
        )
        self.register(
            Operation(
                "POST", "/agent/providers/claude/auth", self._claude_auth, mutating=True, confirm="start"
            )
        )
        self.register(Operation("GET", "/chat/sessions", self._chat_sessions))
        self.register(Operation("POST", "/chat/sessions", self._chat_create, mutating=True, confirm="create"))
        self.register(
            Operation("POST", "/chat/sessions/cleanup", self._chat_cleanup, mutating=True, confirm="cleanup")
        )
        self.register(Operation("GET", "/chat/sessions/{sid}/stream", self._chat_stream))
        self.register(
            Operation(
                "POST",
                "/chat/sessions/{sid}/prompt",
                self._chat_prompt,
                mutating=True,
                confirm="send",
                timeout=300.0,
            )
        )
        self.register(Operation("POST", "/chat/sessions/{sid}/events", self._chat_events))
        self.register(
            Operation(
                "POST", "/chat/sessions/{sid}/cancel", self._chat_cancel, mutating=True, confirm="cancel"
            )
        )
        self.register(
            Operation(
                "POST", "/chat/sessions/{sid}/approve", self._chat_approve, mutating=True, confirm="approve"
            )
        )
        self.register(
            Operation(
                "POST",
                "/chat/sessions/{sid}/resume",
                self._chat_resume,
                mutating=True,
                confirm="resume",
                timeout=120.0,
            )
        )
        # POST, not DELETE: the portal server only parses bodies (and thus
        # enforces `confirm`) on POST — a DELETE route would bypass the
        # mutation gate entirely.
        self.register(
            Operation("POST", "/chat/sessions/{sid}/close", self._chat_close, mutating=True, confirm="close")
        )
        self.register(
            Operation(
                "POST", "/products/{pid}/queries/execute", self._q_exec, mutating=True, confirm="execute"
            )
        )
        self.register(
            Operation(
                "POST", "/products/{pid}/agents/{aid}/run", self._agent_run, mutating=True, confirm="run"
            )
        )
        self.register(Operation("GET", "/products/{pid}/roadmap", self._roadmap))
        self.register(Operation("GET", "/products/{pid}/initiatives", self._initiatives))
        self.register(
            Operation(
                "POST",
                "/products/{pid}/initiatives",
                self._initiative_create,
                mutating=True,
                confirm="create",
            )
        )
        self.register(
            Operation(
                "POST",
                "/products/{pid}/initiatives/{iid}/prioritize",
                self._initiative_prioritize,
                mutating=True,
                confirm="prioritize",
            )
        )
        self.register(Operation("GET", "/products/{pid}/boards", self._board))
        self.register(Operation("GET", "/products/{pid}/board", self._board))
        self.register(
            Operation("POST", "/products/{pid}/tasks", self._task_create, mutating=True, confirm="create")
        )
        self.register(Operation("GET", "/products/{pid}/tasks", self._tasks))
        self.register(
            Operation(
                "POST", "/products/{pid}/tasks/{tid}/move", self._task_move, mutating=True, confirm="move"
            )
        )
        self.register(
            Operation(
                "POST",
                "/products/{pid}/task-proposals",
                self._task_proposal_create,
                mutating=True,
                confirm="create",
            )
        )
        self.register(Operation("GET", "/products/{pid}/task-proposals", self._task_proposal_list))
        self.register(
            Operation(
                "POST",
                "/products/{pid}/task-proposals/{proposal_id}/approve",
                self._task_proposal_decide,
                mutating=True,
                confirm="decide",
            )
        )
        self.register(Operation("GET", "/notifications", self._notifications))
        self.register(Operation("GET", "/products/{pid}/alerts", self._alerts))
        self.register(Operation("GET", "/audit", self._audit))

    def register(self, op: Operation) -> None:
        # Every op passes through the error translator so store/validation
        # failures become typed envelope errors instead of PORTAL-INTERNAL.
        op.handler = _translate_handler_errors(op.handler)
        super().register(op)

    # -- capability surface -------------------------------------------------

    def capabilities(self) -> list[dict[str, Any]]:
        bridge_state = (self.bridge_status() or {}).get("state") if self.bridge_status is not None else None
        chat_state = "unverified"
        agent_bridge = "unverified"
        if bridge_state == "running":
            chat_state = agent_bridge = "supported"
        elif bridge_state in {"restarting", "degraded", "starting"}:
            chat_state = agent_bridge = "degraded"
        elif bridge_state is not None:
            agent_bridge = bridge_state
        return [
            {"id": "workspaces", "state": "supported"},
            {"id": "products", "state": "supported"},
            {"id": "context", "state": "supported"},
            {"id": "workspace.discovery", "state": "supported"},
            {"id": "audit", "state": "supported"},
            {"id": "knowledge", "state": "unverified"},
            {"id": "agents", "state": "unverified"},
            {"id": "analytics", "state": "unverified"},
            {"id": "dashboards", "state": "unverified"},
            {"id": "planning", "state": "unverified"},
            {"id": "chat", "state": chat_state},
            {"id": "agent-bridge", "state": agent_bridge},
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
        bridge = self.bridge_status() if self.bridge_status is not None else {"state": "unverified"}
        return {"forge_id": FORGE_ID, "version": __version__, "status": "healthy", "bridge": bridge}

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
            ws = Workspace(
                id=new_id("ws"),
                name=ctx.require("name").strip(),
                description=str(body.get("description", "")),
            )
            st.put("workspaces", ws)
            _record_audit(st, ctx, "workspace.create", "workspaces", ws.id, workspace_id=ws.id)
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
            return _require(st, "products", ctx.params["pid"])
        finally:
            st.close()

    def _product_create(self, ctx: RequestContext) -> dict[str, Any]:
        body = dict(ctx.body or {})
        body["workspace_id"] = ctx.require("workspace_id")
        body["name"] = ctx.require("name")
        st = _store()
        try:
            _require(st, "workspaces", body["workspace_id"])
            fields = {
                k: v
                for k, v in body.items()
                if k in {"workspace_id", "name", "description", "domain", "tags"}
            }
            p = Product(id=new_id("prd"), status="active", **fields)
            st.put("products", p)
            _record_audit(
                st, ctx, "product.create", "products", p.id, product_id=p.id, workspace_id=p.workspace_id
            )
            ctx.emit("product.created", resource_id=p.id)
            return p.model_dump(mode="json", by_alias=True)
        finally:
            st.close()

    def _product_context(self, ctx: RequestContext) -> dict[str, Any]:
        pid = ctx.params["pid"]
        st = _store()
        try:
            return {
                "schema": "productforge/ProductContextPackage/v1",
                "product": _require(st, "products", pid),
                "sources": st.list("knowledge_sources", product_id=pid, limit=200),
                "entities": st.list("entities", product_id=pid, limit=200),
                "agents": st.list("agents", product_id=pid, limit=100),
                "data_sources": st.list("data_sources", product_id=pid, limit=100),
            }
        finally:
            st.close()

    def _document_detail(self, ctx: RequestContext) -> dict[str, Any]:
        st = _store()
        try:
            doc = _require(st, "documents", ctx.params["did"])
            if doc.get("product_id") != ctx.params["pid"]:
                raise PortalError("PORTAL-NOT-FOUND", "document not in product", http=404)
            chunks = [
                chunk
                for chunk in st.list_chunks(ctx.params["pid"])
                if chunk.get("document_id") == ctx.params["did"]
            ]
            return {
                "schema": "productforge/DocumentExplorer/v1",
                "document": doc,
                "content": {"chunks": chunks, "chunk_count": len(chunks)},
                "source": (doc.get("metadata") or {}).get("source"),
                "versions": explorer_versions(st, ctx.params["pid"], doc),
                "relations": [],
            }
        finally:
            st.close()

    def _document_search(self, ctx: RequestContext) -> dict[str, Any]:
        query = (_q1(ctx, "q") or "").strip()
        try:
            limit = max(1, min(int(_q1(ctx, "limit") or "20"), 100))
        except ValueError as exc:
            raise PortalError("PORTAL-VALIDATION", "limit must be an integer", http=422) from exc
        st = _store()
        try:
            pid = ctx.params["pid"]
            _require(st, "products", pid)
            hits = st.search_fts(pid, query, limit) if query else []
            items = []
            for hit in hits:
                doc = st.get("documents", hit["document_id"])
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
            return {"schema": "productforge/DocumentSearch/v1", "items": items}
        finally:
            st.close()

    def _knowledge_search(self, ctx: RequestContext) -> dict[str, Any]:
        query = (_q1(ctx, "q") or "").strip()
        try:
            limit = max(1, min(int(_q1(ctx, "limit") or "20"), 100))
        except ValueError as exc:
            raise PortalError("PORTAL-VALIDATION", "limit must be an integer", http=422) from exc
        st = _store()
        try:
            pid = ctx.params["pid"]
            _require(st, "products", pid)
            return search_knowledge(st, pid, query, limit)
        finally:
            st.close()

    def _workspace_start(self) -> Path:
        """Return the portal's local launch boundary, never a user-provided path."""
        return Path(self.workspace).expanduser() if self.workspace else Path.cwd()

    def _workspace_discovery(self, ctx: RequestContext) -> dict[str, Any]:
        """Discover projects and eligible context files without reading contents."""
        return discover_workspace(self._workspace_start())

    def _workspace_preview(self, ctx: RequestContext) -> dict[str, Any]:
        raw_path = _q1(ctx, "path")
        if not raw_path:
            raise PortalError("WORKSPACE-PATH-REQUIRED", "path query parameter is required", http=422)
        discovery = discover_workspace(self._workspace_start())
        try:
            return preview_workspace_document(discovery["workspace"]["path"], raw_path)
        except WorkspaceDiscoveryError as exc:
            raise PortalError("WORKSPACE-DOCUMENT-REFUSED", str(exc), http=422) from exc

    def _workspace_document_import(self, ctx: RequestContext) -> dict[str, Any]:
        """Import one explicitly selected workspace document into product knowledge."""
        pid = ctx.params["pid"]
        body = ctx.body or {}
        raw_path = str(body.get("path") or "").strip()
        if not raw_path:
            raise PortalError("WORKSPACE-PATH-REQUIRED", "path is required", http=422)
        st = _store()
        try:
            product = _require(st, "products", pid)
            root = discover_workspace(self._workspace_start())["workspace"]["path"]
            try:
                imported = import_workspace_document(root, raw_path)
            except WorkspaceDiscoveryError as exc:
                raise PortalError("WORKSPACE-DOCUMENT-REFUSED", str(exc), http=422) from exc
            existing = [
                doc
                for doc in st.list("documents", product_id=pid)
                if (doc.get("metadata") or {}).get("workspace_path") == imported["path"]
                and doc.get("content_hash") == imported["content_hash"]
            ]
            if existing:
                return {
                    **existing[0],
                    "state": "already_imported",
                    "source_path": imported["path"],
                    "source_kind": imported["kind"],
                }
            from ..domain.models import Document, DocumentStatus
            from ..knowledge.ingest import chunk_text

            title = str(body.get("title") or imported["title"])
            metadata, _ = prepare_version(
                st,
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
                title=title,
                content_hash=imported["content_hash"],
                status=DocumentStatus.IMPORTED,
                metadata=metadata,
            )
            st.put("documents", doc)
            doc.chunk_count = st.put_chunks(doc.id, pid, chunk_text(imported["content"]))
            doc.status = DocumentStatus.INDEXED
            st.put("documents", doc)
            _record_audit(
                st,
                ctx,
                "workspace.document.import",
                "documents",
                doc.id,
                product_id=pid,
                workspace_id=product.get("workspace_id"),
            )
            ctx.emit(
                "workspace.document.imported",
                resource_id=doc.id,
                product_id=pid,
                path=imported["path"],
                kind=imported["kind"],
            )
            return {
                **doc.model_dump(mode="json", by_alias=True),
                "state": "imported",
                "source_path": imported["path"],
                "source_kind": imported["kind"],
            }
        finally:
            st.close()

    def _url_preview(self, ctx: RequestContext) -> dict[str, Any]:
        raw_url = _q1(ctx, "url")
        extractor = _q1(ctx, "extractor") or "stdlib"
        if not raw_url:
            raise PortalError("URL-REQUIRED", "url query parameter is required", http=422)
        st = _store()
        try:
            _require(st, "products", ctx.params["pid"])
            captured = fetch_url_document(raw_url, extractor=extractor)
        except UrlCaptureError as exc:
            raise PortalError(exc.code, str(exc), http=422, details=exc.details) from exc
        finally:
            st.close()
        return {k: v for k, v in captured.items() if k != "content"} | {"preview": captured["content"]}

    def _url_document_import(self, ctx: RequestContext) -> dict[str, Any]:
        pid = ctx.params["pid"]
        body = ctx.body or {}
        raw_url = str(body.get("url") or "").strip()
        if not raw_url:
            raise PortalError("URL-REQUIRED", "url is required", http=422)
        st = _store()
        try:
            product = _require(st, "products", pid)
            try:
                captured = fetch_url_document(raw_url, extractor=str(body.get("extractor") or "stdlib"))
            except UrlCaptureError as exc:
                raise PortalError(exc.code, str(exc), http=422, details=exc.details) from exc
            existing = [
                doc
                for doc in st.list("documents", product_id=pid)
                if (doc.get("metadata") or {}).get("source_url") == captured["url"]
                and doc.get("content_hash") == captured["content_hash"]
            ]
            if existing:
                return {
                    **existing[0],
                    "state": "already_imported",
                    "source_url": captured["url"],
                    "source_kind": "url",
                }
            from ..domain.models import Document, DocumentStatus
            from ..knowledge.ingest import chunk_text

            metadata, _ = prepare_version(
                st,
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
                title=str(body.get("title") or captured["title"]),
                content_hash=captured["content_hash"],
                status=DocumentStatus.IMPORTED,
                metadata=metadata,
            )
            st.put("documents", doc)
            doc.chunk_count = st.put_chunks(doc.id, pid, chunk_text(captured["content"]))
            doc.status = DocumentStatus.INDEXED
            st.put("documents", doc)
            _record_audit(
                st,
                ctx,
                "url.document.import",
                "documents",
                doc.id,
                product_id=pid,
                workspace_id=product.get("workspace_id"),
            )
            ctx.emit("url.document.imported", resource_id=doc.id, product_id=pid, url=captured["url"])
            return {
                **doc.model_dump(mode="json", by_alias=True),
                "state": "imported",
                "source_url": captured["url"],
                "source_kind": "url",
                "capture": {k: v for k, v in captured.items() if k != "content"},
            }
        finally:
            st.close()

    def _obsidian_preview(self, ctx: RequestContext) -> dict[str, Any]:
        raw_path = _q1(ctx, "path")
        if not raw_path:
            raise PortalError("OBSIDIAN-PATH-REQUIRED", "path query parameter is required", http=422)
        try:
            imported = import_vault_document(_obsidian_vault(), raw_path)
        except ObsidianVaultError as exc:
            raise PortalError(exc.code, str(exc), http=422) from exc
        return {k: v for k, v in imported.items() if k != "content"} | {"preview": imported["content"]}

    def _obsidian_history(self, ctx: RequestContext) -> dict[str, Any]:
        raw_limit = _q1(ctx, "limit") or "50"
        try:
            limit = int(raw_limit)
        except ValueError as exc:
            raise PortalError("OBSIDIAN-HISTORY-LIMIT", "limit must be an integer", http=422) from exc
        try:
            items = list_obsidian_receipts(_obsidian_vault(), limit=limit)
        except ObsidianVaultError as exc:
            raise PortalError(exc.code, str(exc), http=422) from exc
        return {"schema": "theforge/ObsidianSyncHistory/v1", "items": items, "count": len(items)}

    def _obsidian_import(self, ctx: RequestContext) -> dict[str, Any]:
        pid = ctx.params["pid"]
        body = ctx.body or {}
        raw_path = str(body.get("path") or "").strip()
        if not raw_path:
            raise PortalError("OBSIDIAN-PATH-REQUIRED", "path is required", http=422)
        st = _store()
        try:
            product = _require(st, "products", pid)
            try:
                imported = import_vault_document(_obsidian_vault(), raw_path)
            except ObsidianVaultError as exc:
                raise PortalError(exc.code, str(exc), http=422) from exc
            existing = [
                doc
                for doc in st.list("documents", product_id=pid)
                if (doc.get("metadata") or {}).get("obsidian_path") == imported["path"]
                and doc.get("content_hash") == imported["content_hash"]
            ]
            if existing:
                return {
                    **existing[0],
                    "state": "already_imported",
                    "source_path": imported["path"],
                    "source_kind": "obsidian",
                }
            from ..domain.models import Document, DocumentStatus
            from ..knowledge.ingest import chunk_text

            metadata, _ = prepare_version(
                st,
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
                title=str(body.get("title") or imported["title"]),
                content_hash=imported["content_hash"],
                status=DocumentStatus.IMPORTED,
                metadata=metadata,
            )
            st.put("documents", doc)
            doc.chunk_count = st.put_chunks(doc.id, pid, chunk_text(imported["content"]))
            doc.status = DocumentStatus.INDEXED
            st.put("documents", doc)
            _record_audit(
                st,
                ctx,
                "obsidian.document.import",
                "documents",
                doc.id,
                product_id=pid,
                workspace_id=product.get("workspace_id"),
            )
            ctx.emit("obsidian.document.imported", resource_id=doc.id, product_id=pid, path=imported["path"])
            return {
                **doc.model_dump(mode="json", by_alias=True),
                "state": "imported",
                "source_path": imported["path"],
                "source_kind": "obsidian",
            }
        finally:
            st.close()

    def _obsidian_export(self, ctx: RequestContext) -> dict[str, Any]:
        pid = ctx.params["pid"]
        body = ctx.body or {}
        raw_path = str(body.get("path") or "").strip()
        content = str(body.get("content") or "")
        if not raw_path or not content:
            raise PortalError("OBSIDIAN-EXPORT-REQUIRED", "path and content are required", http=422)
        st = _store()
        try:
            product = _require(st, "products", pid)
            try:
                exported = export_vault_document(
                    _obsidian_vault(),
                    raw_path,
                    content,
                    baseline_hash=body.get("baseline_hash"),
                    classification=str(body.get("classification") or "internal"),
                    source=str(body.get("source") or "product-forge"),
                )
            except ObsidianVaultError as exc:
                raise PortalError(exc.code, str(exc), http=422) from exc
            _record_audit(
                st,
                ctx,
                "obsidian.document.export",
                "obsidian",
                exported["path"],
                product_id=pid,
                workspace_id=product.get("workspace_id"),
            )
            ctx.emit("obsidian.document.exported", resource_id=exported["path"], product_id=pid)
            return exported
        finally:
            st.close()

    def _obsidian_sync_plan(self, ctx: RequestContext) -> dict[str, Any]:
        body = ctx.body or {}
        raw_path = str(body.get("path") or "").strip()
        content = str(body.get("content") or "")
        if not raw_path or not content:
            raise PortalError("OBSIDIAN-PLAN-REQUIRED", "path and content are required", http=422)
        try:
            return plan_vault_sync(
                _obsidian_vault(),
                raw_path,
                content,
                baseline_hash=body.get("baseline_hash"),
                classification=str(body.get("classification") or "internal"),
                source=str(body.get("source") or "product-forge"),
            )
        except ObsidianVaultError as exc:
            raise PortalError(exc.code, str(exc), http=422) from exc

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
        question = ctx.require("question")
        st = _store()
        try:
            hits = st.search_fts(pid, question, limit=10)
            return {
                "question": question,
                "citations": [
                    {
                        "chunk_id": h["id"],
                        "document_id": h["document_id"],
                        "snippet": h["snip"],
                        "title": st.doc_title(h["document_id"]),
                    }
                    for h in hits
                ],
            }
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
        source_id = ctx.require("source_id")
        statement = body.get("statement") or (compile_spec(body["spec"]) if body.get("spec") else None)
        if not statement:
            raise PortalError(
                "PORTAL-VALIDATION",
                "either 'statement' or 'spec' is required to execute a query",
                http=422,
            )
        st = _store()
        try:
            run = execute_query(st, ctx.params["pid"], source_id, statement)
            ctx.emit("query.executed", resource_id=run["id"], status=run["status"])
            return run
        finally:
            st.close()

    def _agent_run(self, ctx: RequestContext) -> dict[str, Any]:
        from ..agents.runtime import run_agent
        from ..domain.models import AgentDefinition

        st = _store()
        try:
            agent = AgentDefinition.model_validate(_require(st, "agents", ctx.params["aid"]))
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
        title = ctx.require("title").strip()
        st = _store()
        try:
            _require(st, "products", ctx.params["pid"])
            item = Initiative(
                id=new_id("ini"),
                product_id=ctx.params["pid"],
                title=title,
                hypothesis=str(body.get("hypothesis", "")),
                status=str(body.get("status", "proposed")),
            )
            st.put("initiatives", item)
            ctx.emit("initiative.created", resource_id=item.id)
            return item.model_dump(mode="json", by_alias=True)
        finally:
            st.close()

    def _initiative_prioritize(self, ctx: RequestContext) -> dict[str, Any]:
        from ..planning.prioritize import score_initiative

        st = _store()
        try:
            doc = _require(st, "initiatives", ctx.params["iid"])
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
            product = _require(st, "products", ctx.params["pid"])
            boards = st.list("boards", product_id=ctx.params["pid"], limit=20)
            board = boards[0] if boards else None
            if board is None:
                board = Board(
                    id=new_id("brd"),
                    workspace_id=product["workspace_id"],
                    product_id=ctx.params["pid"],
                    name=f"{product['name']} board",
                )
                st.put("boards", board)
            tasks = st.list("tasks", product_id=ctx.params["pid"], limit=1000)
            columns = {str(c.get("id")): [] for c in board.get("columns", [])}
            for task in tasks:
                columns.setdefault(str(task.get("column_id", "backlog")), []).append(task)
            return {
                "schema": "productforge/Board/v1",
                "product_id": ctx.params["pid"],
                "board": board,
                "columns": columns,
                "tasks": tasks,
                "items": self._initiatives(ctx)["items"],
            }
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
        title = ctx.require("title").strip()
        st = _store()
        try:
            product = _require(st, "products", ctx.params["pid"])
            boards = st.list("boards", product_id=ctx.params["pid"], limit=1)
            board = (
                boards[0]
                if boards
                else Board(
                    id=new_id("brd"),
                    workspace_id=product["workspace_id"],
                    product_id=ctx.params["pid"],
                    name=f"{product['name']} board",
                )
            )
            if not boards:
                st.put("boards", board)
            board_id = board.id if isinstance(board, Board) else board["id"]
            task = Task(
                id=new_id("tsk"),
                workspace_id=product["workspace_id"],
                product_id=ctx.params["pid"],
                board_id=board_id,
                title=title,
                description=str(body.get("description", "")),
                column_id=str(body.get("column_id", "backlog")),
                priority=str(body.get("priority", "medium")),
            )
            st.put("tasks", task)
            _record_audit(
                st,
                ctx,
                "task.create",
                "tasks",
                task.id,
                product_id=task.product_id,
                workspace_id=task.workspace_id,
            )
            ctx.emit("task.created", resource_id=task.id)
            return task.model_dump(mode="json", by_alias=True)
        finally:
            st.close()

    def _task_move(self, ctx: RequestContext) -> dict[str, Any]:
        st = _store()
        try:
            doc = _require(st, "tasks", ctx.params["tid"])
            if doc.get("product_id") != ctx.params["pid"]:
                raise KeyError(ctx.params["tid"])
            expected = (ctx.body or {}).get("expected_version")
            if expected is not None and int(expected) != int(doc.get("version", 1)):
                raise ValueError("task changed; reload before moving")
            doc["column_id"] = str((ctx.body or {}).get("column_id", "backlog"))
            doc["position"] = int((ctx.body or {}).get("position", doc.get("position", 0)))
            doc["version"] = int(doc.get("version", 1)) + 1
            st.put("tasks", Task.model_validate(doc))
            ctx.emit("task.moved", resource_id=ctx.params["tid"], column_id=doc["column_id"])
            return doc
        finally:
            st.close()

    def _task_proposal_create(self, ctx: RequestContext) -> dict[str, Any]:
        from ..operations.proposals import create_proposal

        body = ctx.body or {}
        st = _store()
        try:
            _require(st, "products", ctx.params["pid"])
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
            proposal = _require(st, "task_proposals", ctx.params["proposal_id"])
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
            ctx.emit(
                "task-proposal.decided",
                resource_id=ctx.params["proposal_id"],
                approved=bool(body.get("approved", True)),
            )
            return rec
        finally:
            st.close()

    def _notifications(self, ctx: RequestContext) -> dict[str, Any]:
        st = _store()
        try:
            return {
                "items": st.list("alerts", limit=100) + st.list("notifications", limit=100),
                "delivery": "approval-gated-webhook-or-smtp",
            }
        finally:
            st.close()

    def _alerts(self, ctx: RequestContext) -> dict[str, Any]:
        st = _store()
        try:
            return {"items": st.list("alerts", product_id=ctx.params["pid"])}
        finally:
            st.close()

    def _gateway_token(self) -> str:
        """Return the short-lived gateway token, if the supervisor paired.

        The master pair token is intentionally only a bootstrap credential.
        All typed Portal operations must use the scoped gateway token so the
        Bridge records one consistent principal for create, read and stream.
        """
        return str(getattr(self, "_gateway_bridge_token", "") or "")

    def _bridge_call(
        self, path: str, *, method: str = "GET", body: dict[str, Any] | None = None, timeout: float = 2.0
    ) -> dict[str, Any]:
        """_bridge_request that fails honestly instead of returning an error dict.

        Read ops keep the ``{"state": "unavailable"|"error"}`` shape for the UI
        to render; mutating/typed ops must surface upstream failures as real
        envelope errors (HTTP status + typed code), never 200-wrapped.
        """
        result = ProductForgePortal._bridge_request(
            path, method=method, body=body, token_override=self._gateway_token(), timeout=timeout
        )
        status = result.get("status")
        if result.get("state") == "error" or (isinstance(status, int) and status >= 400):
            detail = result.get("error") or result
            http = status if status in {400, 401, 403, 404, 409, 422, 429} else 502
            raise PortalError(
                "BRIDGE-UPSTREAM",
                "Agent Bridge rejected the request",
                http=http,
                retryable=status in {408, 429, 500, 502, 503, 504},
                details=detail if isinstance(detail, dict) else None,
            )
        if result.get("state") == "unavailable":
            raise PortalError(
                "BRIDGE-UPSTREAM",
                "Agent Bridge is unavailable",
                http=503,
                retryable=True,
                details={"reason": result.get("reason")},
            )
        return result

    @staticmethod
    def _bridge_request(
        path: str,
        *,
        method: str = "GET",
        body: dict[str, Any] | None = None,
        token_override: str = "",
        timeout: float = 2.0,
    ) -> dict[str, Any]:
        base = os.environ.get("FORGE_BRIDGE_URL", "http://127.0.0.1:8471").rstrip("/")
        parsed = urllib.parse.urlsplit(base)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            return {"state": "unavailable", "reason": "non_loopback_bridge_url"}
        token_file = Path(
            os.environ.get("FORGE_BRIDGE_TOKEN_FILE", "~/.forge-bridge/pair.token")
        ).expanduser()
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
            f"{base}{path}", data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - loopback validated above
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

    def _bridge_get(self, path: str) -> dict[str, Any]:
        return ProductForgePortal._bridge_request(path, token_override=self._gateway_token())

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
        allowed = (
            "/status",
            "/providers",
            "/diagnostics",
            "/mcp/doctor",
            "/agent-sessions",
            "/approvals",
            "/files",
            "/intel",
        )
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
            # Provider discovery and diagnostics may inspect local CLIs and
            # credentials.  Two seconds is below the observed cold-start
            # latency on Windows and turns a healthy Bridge into a false
            # "unavailable" state.  Keep mutating/prompt calls bounded while
            # giving read-only discovery a realistic local budget.
            timeout=280.0
            if path.endswith("/prompt")
            else (15.0 if path in {"/status", "/providers", "/diagnostics", "/mcp/doctor"} else 5.0),
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
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
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
        except urllib.error.HTTPError as exc:
            try:
                detail = json.loads(exc.read().decode("utf-8"))
            except (OSError, ValueError):
                detail = {"status": exc.code}
            raise PortalError(
                "BRIDGE-UPSTREAM",
                "Agent Bridge stream is unavailable",
                http=exc.code if exc.code in {401, 403, 404, 409, 429, 503} else 503,
                retryable=exc.code in {408, 429, 500, 502, 503, 504},
                details=detail if isinstance(detail, dict) else {"status": exc.code},
            ) from exc
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
        upstream = self._bridge_get("/status")
        if self.bridge_status is not None:
            upstream["managed"] = self.bridge_status()
        return upstream

    def _agent_providers(self, ctx: RequestContext) -> dict[str, Any]:
        return self._bridge_get("/providers")

    def _bridge_bootstrap(self, ctx: RequestContext) -> dict[str, Any]:
        """Bring the managed Bridge into the gateway session.

        Pairing is deliberately server-side.  The browser receives a health
        result only; neither the master pair token, an internal URL nor a
        Bridge bearer token crosses the Portal boundary.
        """
        token_file = Path(
            os.environ.get("FORGE_BRIDGE_TOKEN_FILE", "~/.forge-bridge/pair.token")
        ).expanduser()
        try:
            master = token_file.read_text(encoding="utf-8").strip()
        except OSError:
            return {"connected": False, "bridge": {"state": "unavailable", "reason": "pair_token_missing"}}
        if not master:
            return {"connected": False, "bridge": {"state": "unavailable", "reason": "pair_token_empty"}}
        result = self._bridge_request(
            "/pair/exchange",
            method="POST",
            body={
                "pair_token": master,
                "device_name": "product-forge-portal",
                "scopes": ["agent"],
            },
        )
        if "session_token" not in result:
            return {"connected": False, "bridge": result}
        # Keep this credential server-side for subsequent proxy calls.  The
        # short-lived exchanged token is held in process memory only.
        self._gateway_bridge_token = str(result["session_token"])
        return {
            "connected": True,
            "bridge": {"state": "ready", "capabilities": ["sessions", "streaming"]},
            "device": {
                "device_id": "gateway",
                "device_name": "Product Forge gateway",
                "scopes": ["agent"],
                "created_at": 0,
                "expires_at": 0,
                "last_seen": 0,
            },
        }

    def _claude_auth(self, ctx: RequestContext) -> dict[str, Any]:
        return self._bridge_call(
            "/providers/claude-code/auth", method="POST", body=dict(ctx.body or {}), timeout=30.0
        )

    def _chat_sessions(self, ctx: RequestContext) -> dict[str, Any]:
        listing = self._bridge_get("/agent-sessions")
        items = listing.get("items")
        if isinstance(items, list):
            self._attach_product_names(items)
        return listing

    @staticmethod
    def _attach_product_names(items: list[Any]) -> None:
        """Enrich session items with the product name the meta points at.

        Best-effort and bounded: one lookup per distinct product id; absent or
        unreadable products simply leave the field out (honest absence).
        """
        names: dict[str, str | None] = {}
        st = _store()
        try:
            for item in items:
                if not isinstance(item, dict):
                    continue
                pid = (item.get("meta") or {}).get("product_id") or item.get("product_id")
                if not pid:
                    continue
                pid = str(pid)
                if pid not in names:
                    try:
                        names[pid] = st.get("products", pid).get("name")
                    except Exception:  # noqa: BLE001 - enrichment never fails the listing
                        names[pid] = None
                if names[pid]:
                    item["product_name"] = names[pid]
        finally:
            st.close()

    def _chat_create(self, ctx: RequestContext) -> dict[str, Any]:
        body = dict(ctx.body or {})
        if not str(body.get("provider", "")).strip():
            raise PortalError(
                "PROVIDER-REQUIRED",
                "select an installed and authenticated AI provider before starting a chat",
                http=422,
                action="connect-provider",
            )
        return self._bridge_call("/agent-sessions", method="POST", body=body, timeout=30.0)

    def _chat_stream(self, ctx: RequestContext) -> SseResult:
        """Typed SSE route for chat — delegates to the gateway proxy so cursor
        handling (``after_seq``/``Last-Event-ID``) and the server-side gateway
        token stay in exactly one place."""
        ctx.params["bridge_path"] = f"/agent-sessions/{ctx.params['sid']}/stream"
        ctx.params["__method"] = "GET"
        return self._bridge_proxy(ctx)

    def _chat_prompt(self, ctx: RequestContext) -> dict[str, Any]:
        body = dict(ctx.body or {})
        if not str(body.get("text", "")).strip():
            raise PortalError(
                "PROMPT-REQUIRED",
                "chat prompt text is required",
                http=422,
            )
        return self._bridge_call(
            f"/agent-sessions/{ctx.params['sid']}/prompt", method="POST", body=body, timeout=280.0
        )

    def _chat_cancel(self, ctx: RequestContext) -> dict[str, Any]:
        return self._bridge_call(
            f"/agent-sessions/{ctx.params['sid']}/cancel", method="POST", body={}, timeout=15.0
        )

    def _chat_approve(self, ctx: RequestContext) -> dict[str, Any]:
        body = dict(ctx.body or {})
        approval_id = str(body.get("approval_id", "")).strip()
        if not approval_id:
            raise PortalError(
                "APPROVAL-REQUIRED",
                "approval_id is required to decide an approval",
                http=422,
            )
        if not isinstance(body.get("approved"), bool):
            raise PortalError(
                "APPROVAL-REQUIRED",
                "approved must be true or false",
                http=422,
            )
        return self._bridge_call(
            f"/agent-sessions/{ctx.params['sid']}/approve",
            method="POST",
            timeout=15.0,
            body={"approval_id": approval_id, "approved": body["approved"]},
        )

    def _chat_resume(self, ctx: RequestContext) -> dict[str, Any]:
        body = dict(ctx.body or {})
        if not str(body.get("session_ref", "")).strip():
            raise PortalError(
                "SESSION-REF-REQUIRED",
                "session_ref is required to resume a chat session",
                http=422,
            )
        return self._bridge_call(
            f"/agent-sessions/{ctx.params['sid']}/resume", method="POST", body=body, timeout=90.0
        )

    def _chat_events(self, ctx: RequestContext) -> dict[str, Any]:
        return self._bridge_call(
            f"/agent-sessions/{ctx.params['sid']}/events",
            method="POST",
            body=dict(ctx.body or {}),
            timeout=15.0,
        )

    def _chat_cleanup(self, ctx: RequestContext) -> dict[str, Any]:
        """Archive bridge chat sessions that are no longer active.

        Orphaned sessions accumulate whenever a portal dies between prompt and
        close.  Closing is idempotent on the Bridge side (DELETE returns
        ``closed: false`` for an already-closed session and archives the meta
        record), so re-running cleanup is safe.  ``include_active: true`` also
        archives live sessions; the default keeps them.
        """
        include_active = bool((ctx.body or {}).get("include_active", False))
        listing = self._bridge_get("/agent-sessions")
        items = listing.get("items")
        if not isinstance(items, list):
            return {"state": "unavailable", "bridge": listing, "closed": [], "kept": [], "errors": []}
        closed: list[str] = []
        kept: list[str] = []
        errors: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            sid = str(item["id"])
            if item.get("state") == "active" and not include_active:
                kept.append(sid)
                continue
            result = self._bridge_request(
                f"/agent-sessions/{sid}", method="DELETE", token_override=self._gateway_token()
            )
            if result.get("archived"):
                closed.append(sid)
            else:
                errors.append({"id": sid, "result": result})
        ctx.emit("chat.sessions_cleaned", closed=len(closed))
        return {"closed": closed, "kept": kept, "errors": errors}

    def _chat_close(self, ctx: RequestContext) -> dict[str, Any]:
        return self._bridge_call(f"/agent-sessions/{ctx.params['sid']}", method="DELETE", timeout=15.0)
