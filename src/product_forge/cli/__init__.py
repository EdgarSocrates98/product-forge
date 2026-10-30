"""productforge CLI — typer app: install/status/doctor/api/workspace/product/knowledge/agent/mcp."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import typer

from .. import FORGE_ID, __version__
from ..config import db_path, home_dir, load_config, save_config
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
def install(yes: bool = typer.Option(False, "--yes"), scope: str = typer.Option("user", "--scope")) -> None:
    """Initialize Product Forge home, config and database."""
    home = home_dir(scope if scope in ("user", "project") else "user")  # type: ignore[arg-type]
    home.mkdir(parents=True, exist_ok=True)
    (home / "state" / "objects").mkdir(parents=True, exist_ok=True)
    cfg = load_config(home)
    save_config(cfg, home)
    st = _store()
    st.close()
    tok = TokenStore(home / str(cfg["api"]["token_file"]))
    _out({"installed": True, "home": str(home), "version": __version__,
          "api_token_preview": tok.preview})


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
                         "snippet": h["snip"]} for h in hits],
          "note": "retrieval-only; enable an LLM provider for synthesized answers"})
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


# -- mcp ------------------------------------------------------------------

@mcp_app.command("serve")
def mcp_serve() -> None:
    """Start the MCP server (stdio). Requires product-forge[mcp]."""
    try:
        from ..mcp.server import serve
    except ImportError:
        typer.echo("mcp extra not installed: pip install product-forge[mcp]", err=True)
        raise typer.Exit(1) from None
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
