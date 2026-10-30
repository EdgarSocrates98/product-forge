"""productforge CLI — typer app: install/status/doctor/api/workspace/product/knowledge/agent/mcp."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import typer

from .. import FORGE_ID, __version__
from ..config import db_path, home_dir, load_config
from ..domain.models import utcnow
from ..security import TokenStore
from ..store.sqlite import Store

app = typer.Typer(name="productforge", no_args_is_help=True,
                  help="Product Forge — Product Intelligence & Agentic Workspace")
ws_app = typer.Typer(help="Workspace management")
prd_app = typer.Typer(help="Product management")
kn_app = typer.Typer(help="Knowledge operations")
ag_app = typer.Typer(help="Agent registry")
api_app = typer.Typer(help="Local HTTP API")
mcp_app = typer.Typer(help="MCP server")
app.add_typer(ws_app, name="workspace")
app.add_typer(prd_app, name="product")
app.add_typer(kn_app, name="knowledge")
app.add_typer(ag_app, name="agent")
app.add_typer(api_app, name="api")
app.add_typer(mcp_app, name="mcp")


def _out(obj: Any) -> None:
    typer.echo(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def _store() -> Store:
    home = home_dir()
    return Store(db_path(home, load_config(home)))


@app.command()
def version() -> None:
    """Print version."""
    typer.echo(__version__)


@app.command()
def install(yes: bool = typer.Option(False, "--yes"),
            scope: str = typer.Option("user", "--scope",
                                      help="user | project"),
            profile: str = typer.Option("recommended", "--profile",
                                        help="minimal | recommended | full"),
            host: str = typer.Option("all", "--host",
                                     help="claude,devin,codex,copilot | all | none"),
            root: str = typer.Option(None, "--root"),
            components: str = typer.Option(None, "--components",
                                           help="csv: skills,agents,mcp,tui,graph-studio"),
            dry_run: bool = typer.Option(False, "--dry-run")) -> None:
    """Install Product Forge — governed by the forge installkit.

    Same engine as spark-forge-aws: profile-gated assets, ledger-tracked
    ownership, AGENTS.md marker block, .mcp.json registration. ``--dry-run``
    prints the plan; real writes need ``--yes``.
    """
    from ..install import lifecycle

    hosts = () if host in ("none", "") else (
        ("all",) if host == "all" else tuple(h.strip() for h in host.split(",")))
    comps = tuple(c.strip() for c in components.split(",")) if components else None
    try:
        doc = lifecycle.install(
            scope=scope, profile=profile, hosts=hosts,
            root=Path(root) if root else None, components=comps,
            dry_run=dry_run, yes=yes)
    except Exception as e:
        code = getattr(e, "code", "PF-INSTALL")
        _out({"installed": False, "error": {"code": code, "message": str(e)}})
        raise typer.Exit(1) from e
    _out(doc)


@app.command()
def repair(scope: str = typer.Option("project", "--scope"),
           root: str = typer.Option(None, "--root"),
           dry_run: bool = typer.Option(False, "--dry-run")) -> None:
    """Re-assert drifted managed files (missing/modified ledger entries)."""
    from ..install import lifecycle

    _out(lifecycle.repair(scope=scope, root=Path(root) if root else None,
                          dry_run=dry_run))


@app.command()
def update(yes: bool = typer.Option(False, "--yes"),
           scope: str = typer.Option("project", "--scope"),
           profile: str = typer.Option("recommended", "--profile"),
           host: str = typer.Option("all", "--host"),
           root: str = typer.Option(None, "--root"),
           dry_run: bool = typer.Option(False, "--dry-run")) -> None:
    """Re-apply the install (idempotent — unchanged assets untouched)."""
    from ..install import lifecycle

    hosts = ("all",) if host == "all" else tuple(h.strip() for h in host.split(","))
    try:
        _out(lifecycle.update(scope=scope, profile=profile, hosts=hosts,
                              root=Path(root) if root else None,
                              yes=yes, dry_run=dry_run))
    except Exception as e:
        _out({"updated": False, "error": str(e)})
        raise typer.Exit(1) from e


@app.command()
def uninstall(scope: str = typer.Option("project", "--scope"),
              root: str = typer.Option(None, "--root"),
              purge_state: bool = typer.Option(False, "--purge-state")) -> None:
    """Remove only ledger-owned files; user/adopted files survive."""
    from ..install import lifecycle

    _out(lifecycle.uninstall(scope=scope, root=Path(root) if root else None,
                             purge_state=purge_state))


@app.command()
def status() -> None:
    """Show installation and state status."""
    home = home_dir()
    cfg = load_config(home)
    db = db_path(home, cfg)
    _out({
        "forge_id": FORGE_ID,
        "version": __version__,
        "home": str(home),
        "home_exists": home.exists(),
        "db": str(db),
        "db_exists": db.exists(),
        "profile": cfg.get("install_profile"),
        "gateway_profile": cfg.get("gateway_profile"),
        "llm_provider": cfg.get("llm", {}).get("provider"),
    })


@app.command()
def doctor() -> None:
    """Environment health diagnostics — read-only."""
    import importlib.util

    home = home_dir()
    checks = []
    for name, ok, detail in [
        ("python>=3.11", sys.version_info >= (3, 11), sys.version.split()[0]),
        ("home", home.exists() or True, str(home)),
        ("pydantic", importlib.util.find_spec("pydantic") is not None, "required"),
        ("typer", importlib.util.find_spec("typer") is not None, "required"),
        ("fastapi", importlib.util.find_spec("fastapi") is not None, "extra: api"),
        ("uvicorn", importlib.util.find_spec("uvicorn") is not None, "extra: api"),
        ("mcp", importlib.util.find_spec("mcp") is not None, "extra: mcp"),
        ("sqlglot", importlib.util.find_spec("sqlglot") is not None, "extra: analytics"),
        ("duckdb", importlib.util.find_spec("duckdb") is not None, "extra: analytics"),
        ("theforge", importlib.util.find_spec("theforge") is not None, "control plane"),
    ]:
        checks.append({"check": name, "ok": ok, "detail": detail})
    _out({"forge_id": FORGE_ID, "version": __version__, "checks": checks,
          "ok": all(c["ok"] for c in checks if c["check"] in {"python>=3.11", "pydantic", "typer"})})


# -- api -----------------------------------------------------------------

@api_app.command("serve")
def api_serve(
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(0),
) -> None:
    """Run the local HTTP API (uvicorn)."""
    try:
        import uvicorn
    except ImportError:
        typer.echo("uvicorn not installed: pip install product-forge[api]", err=True)
        raise typer.Exit(1) from None
    from ..api.app import create_app

    uvicorn.run(create_app(), host=host, port=port, log_level="warning")


@api_app.command("token")
def api_token(show: bool = typer.Option(False, "--show"), rotate: bool = False) -> None:
    """Show (preview) or rotate the local API token."""
    home = home_dir()
    cfg = load_config(home)
    ts = TokenStore(home / str(cfg["api"]["token_file"]))
    if rotate:
        ts.rotate()
    out: dict[str, Any] = {"token_preview": ts.preview}
    if show:
        out["token"] = ts.token
    _out(out)


# -- workspace -------------------------------------------------------------

@ws_app.command("create")
def ws_create(name: str, description: str = "") -> None:
    from ..domain.models import Workspace, new_id

    st = _store()
    w = Workspace(id=new_id("ws"), name=name, description=description)
    st.put("workspaces", w)
    st.close()
    _out(w.model_dump(mode="json", by_alias=True))


@ws_app.command("list")
def ws_list() -> None:
    st = _store()
    _out(st.list("workspaces"))
    st.close()


# -- product ---------------------------------------------------------------

@prd_app.command("create")
def prd_create(workspace_id: str, name: str, description: str = "", domain: str = "") -> None:
    from ..domain.models import Product, new_id

    st = _store()
    st.get("workspaces", workspace_id)
    p = Product(id=new_id("prd"), workspace_id=workspace_id, name=name,
                description=description, domain=domain, status="active")
    st.put("products", p)
    st.close()
    _out(p.model_dump(mode="json", by_alias=True))


@prd_app.command("list")
def prd_list(workspace_id: str | None = None) -> None:
    st = _store()
    _out(st.list("products", workspace_id=workspace_id))
    st.close()


@prd_app.command("context")
def prd_context(product_id: str) -> None:
    st = _store()
    p = st.get("products", product_id)
    _out({"schema": "productforge/ProductContextPackage/v1", "product": p,
          "sources": st.list("knowledge_sources", product_id=product_id),
          "entities": st.list("entities", product_id=product_id),
          "agents": st.list("agents", product_id=product_id),
          "data_sources": st.list("data_sources", product_id=product_id)})
    st.close()


# -- knowledge -------------------------------------------------------------

@kn_app.command("import")
def kn_import(product_id: str, file: Path) -> None:
    """Import a text/markdown document and index chunks (FTS5)."""
    from ..domain.models import Document, DocumentStatus, new_id
    from ..knowledge.ingest import chunk_text, sha256_text

    st = _store()
    st.get("products", product_id)
    raw = file.read_text(encoding="utf-8", errors="replace")
    doc = Document(id=new_id("doc"), product_id=product_id, title=file.name,
                   content_hash=sha256_text(raw), status=DocumentStatus.IMPORTED)
    st.put("documents", doc)
    chunks = chunk_text(raw)
    doc.chunk_count = st.put_chunks(doc.id, product_id, chunks)
    doc.status = DocumentStatus.INDEXED
    st.put("documents", doc)
    st.close()
    _out({"document_id": doc.id, "chunks": doc.chunk_count, "status": doc.status})


@kn_app.command("query")
def kn_query(product_id: str, question: str, limit: int = 5) -> None:
    """Retrieve grounded chunks with citations (FTS5 retrieval, no LLM)."""
    st = _store()
    st.get("products", product_id)
    hits = st.search_fts(product_id, question, limit=limit)
    _out({"question": question, "hits": hits,
          "answer": None,
          "citations": [{"chunk_id": h["id"], "document_id": h["document_id"],
                         "snippet": h["snip"], "title": st.doc_title(h["document_id"])}
                        for h in hits],
          "note": "retrieval-only; enable an LLM provider for synthesized answers"})
    st.close()


@kn_app.command("extract")
def kn_extract(product_id: str) -> None:
    """Extract provisional entities + relations from indexed chunks."""
    from ..knowledge.extract import build_relations, extract_entities

    st = _store()
    st.get("products", product_id)
    chunks = st.list_chunks(product_id)
    if not chunks:
        _out({"error": "no indexed chunks — run knowledge import first", "entities": 0})
        st.close()
        return
    ents = extract_entities(product_id, chunks)
    for e in ents:
        st.put("entities", e)
    rels = build_relations(product_id, ents, chunks)
    for r in rels:
        st.put("relations", r)
    st.close()
    _out({"entities": len(ents), "relations": len(rels),
          "kinds": {k: sum(1 for e in ents if e.kind.value == k)
                    for k in {e.kind.value for e in ents}}})


@kn_app.command("graph")
def kn_graph(product_id: str, limit: int = 2000) -> None:
    """Project the product knowledge graph."""
    from ..knowledge.graph import product_graph

    st = _store()
    _out(product_graph(st, product_id, limit))
    st.close()


@kn_app.command("health")
def kn_health(product_id: str) -> None:
    """Knowledge coverage and freshness score for a product."""
    from ..knowledge.graph import knowledge_health

    st = _store()
    _out(knowledge_health(st, product_id))
    st.close()


# -- agent -----------------------------------------------------------------

@ag_app.command("create")
def ag_create(product_id: str, name: str, mission: str = "", template: str = "custom") -> None:
    from ..domain.models import AgentDefinition, new_id

    st = _store()
    st.get("products", product_id)
    a = AgentDefinition(id=new_id("agt"), product_id=product_id, name=name,
                        mission=mission, template=template)
    st.put("agents", a)
    st.close()
    _out(a.model_dump(mode="json", by_alias=True))


@ag_app.command("list")
def ag_list(product_id: str) -> None:
    st = _store()
    _out(st.list("agents", product_id=product_id))
    st.close()


def _load_agent(st: Store, agent_id: str) -> Any:
    from ..domain.models import AgentDefinition

    return AgentDefinition.model_validate(st.get("agents", agent_id))


@ag_app.command("run")
def ag_run(agent_id: str, text: str) -> None:
    """Execute an agent run (deterministic template + policy checks)."""
    from ..agents.runtime import run_agent

    st = _store()
    _out(run_agent(st, _load_agent(st, agent_id), text, actor="cli"))
    st.close()


@ag_app.command("eval")
def ag_eval(agent_id: str) -> None:
    """Run the default eval suite and persist the score."""
    from ..agents.evals import run_evals

    st = _store()
    agent = _load_agent(st, agent_id)
    rep = run_evals(st, agent)
    agent.eval_summary = {"score": rep["score"], "passed": rep["passed"],
                          "total": rep["total"], "at": utcnow()}
    st.put("agents", agent)
    _out(rep)
    st.close()


@ag_app.command("publish")
def ag_publish(agent_id: str) -> None:
    from ..errors import UnsafeOperationError

    st = _store()
    agent = _load_agent(st, agent_id)
    score = (agent.eval_summary or {}).get("score", 0)
    if not agent.tools_allowed or score < 0.5:
        st.close()
        raise UnsafeOperationError("publish gate: tools_allowed set + eval score >= 0.5 required")
    agent.status = agent.status.PUBLISHED
    agent.version += 1
    st.put("agents", agent)
    _out(agent.model_dump(mode="json", by_alias=True))
    st.close()


@ag_app.command("templates")
def ag_templates() -> None:
    """List native agent templates (§6.3 roster) with skill mapping."""
    from ..agents.tools import list_templates

    _out({"items": list_templates()})


# -- analytics -------------------------------------------------------------

q_app = typer.Typer(help="Analytics: validate, compile, execute queries")
src_app = typer.Typer(help="Analytical data sources")
app.add_typer(q_app, name="query")
app.add_typer(src_app, name="source")


@q_app.command("validate")
def q_validate(statement: str, dialect: str = "sql") -> None:
    """Validate a statement for read-only safety (sqlglot)."""
    from ..analytics.engine import validate_query

    _out(validate_query(statement, dialect))


@q_app.command("exec")
def q_exec(product_id: str, source_id: str, statement: str) -> None:
    """Validate + execute a read-only query against a registered source."""
    from ..analytics.engine import execute_query

    st = _store()
    _out(execute_query(st, product_id, source_id, statement))
    st.close()


@q_app.command("list")
def q_list(product_id: str) -> None:
    st = _store()
    _out(st.list("query_runs", product_id=product_id))
    st.close()


@q_app.command("compile")
def q_compile(spec: str) -> None:
    """Compile a QuerySpec JSON (visual builder contract) to SQL."""
    from ..analytics.engine import compile_spec

    _out({"sql": compile_spec(json.loads(spec))})


@src_app.command("register")
def src_register(product_id: str, name: str, connector: str, locator: str = "",
                 dialect: str = "sql") -> None:
    from ..domain.models import ConnectorType, DataSource, new_id

    st = _store()
    st.get("products", product_id)
    ds = DataSource(id=new_id("src"), product_id=product_id, name=name,
                    connector=ConnectorType(connector), locator=locator,
                    dialect=dialect, read_only=True)
    st.put("data_sources", ds)
    st.close()
    _out(ds.model_dump(mode="json", by_alias=True))


@src_app.command("schema")
def src_schema(product_id: str, source_id: str) -> None:
    from ..analytics.connectors import connector_for

    st = _store()
    _out(connector_for(st.get("data_sources", source_id)).schema())
    st.close()


@src_app.command("verify")
def src_verify(product_id: str, source_id: str) -> None:
    from ..analytics.connectors import connector_for
    from ..domain.models import DataSource

    st = _store()
    ds = DataSource.model_validate(st.get("data_sources", source_id))
    try:
        res = connector_for(ds.model_dump(mode="json")).verify()
        ds.status = ds.status.HEALTHY
    except Exception as e:
        ds.status = ds.status.ERROR
        res = {"status": "error", "error": str(e)[:200]}
    ds.last_verified_at = utcnow()
    st.put("data_sources", ds)
    st.close()
    _out(res)


# -- dashboards + planning --------------------------------------------------

dash_app = typer.Typer(help="Dashboards")
plan_app = typer.Typer(help="Planning: initiatives, PRD, roadmap")
app.add_typer(dash_app, name="dashboard")
app.add_typer(plan_app, name="plan")


@dash_app.command("create")
def dash_create(product_id: str, name: str, widgets: str = "[]") -> None:
    from ..domain.models import Dashboard, new_id

    st = _store()
    st.get("products", product_id)
    d = Dashboard(id=new_id("dsh"), product_id=product_id, name=name,
                  widgets=json.loads(widgets))
    st.put("dashboards", d)
    st.close()
    _out(d.model_dump(mode="json", by_alias=True))


@dash_app.command("render")
def dash_render(product_id: str, dashboard_id: str) -> None:
    from ..dashboards.render import render_dashboard

    st = _store()
    dash = st.get("dashboards", dashboard_id)
    _out(render_dashboard(st, product_id, dash))
    st.close()


@plan_app.command("prioritize")
def plan_prioritize(initiative_id: str, factors: str = "{}") -> None:
    from ..domain.models import Initiative
    from ..planning.prioritize import score_initiative

    st = _store()
    doc = st.get("initiatives", initiative_id)
    res = score_initiative(doc, json.loads(factors).get("factors", {}))
    doc["priority_score"] = res["score"]
    st.put("initiatives", Initiative.model_validate(doc))
    _out(res)
    st.close()


@plan_app.command("prd")
def plan_prd(initiative_id: str) -> None:
    from ..planning.prd import generate_prd

    st = _store()
    doc = st.get("initiatives", initiative_id)
    _out(generate_prd(st, doc["product_id"], doc))
    st.close()


@plan_app.command("roadmap")
def plan_roadmap(product_id: str) -> None:
    from ..planning.roadmap import build_roadmap

    st = _store()
    _out(build_roadmap(st, product_id))
    st.close()


# -- mcp ------------------------------------------------------------------

@mcp_app.command("serve")
def mcp_serve(transport: str = typer.Option("stdio", "--transport",
                                          help="stdio | http"),
              host: str = typer.Option("127.0.0.1", "--host"),
              port: int = typer.Option(8471, "--port")) -> None:
    """Start the MCP server — stdio (default) or streamable-HTTP at POST /mcp.

    HTTP mode requires the local bearer token (same as the API).
    """
    try:
        from ..mcp.server import serve, serve_http
    except ImportError:
        typer.echo("mcp extra not installed: pip install product-forge[mcp]", err=True)
        raise typer.Exit(1) from None
    if transport == "http":
        serve_http(host=host, port=port)
    else:
        serve()


# -- portal ----------------------------------------------------------------

@app.command()
def portal(port: int = typer.Option(0), no_open: bool = typer.Option(False, "--no-open")) -> None:
    """Serve the Forge Portal (127.0.0.1) with the Product Forge adapter."""
    from .._forge_portal import serve as portal_serve
    from ..portal.adapter import ProductForgePortal

    portal_serve(ProductForgePortal(), port=port, open_url=not no_open)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
