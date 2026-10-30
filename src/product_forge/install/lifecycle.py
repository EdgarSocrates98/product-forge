"""productforge install lifecycle — thin ForgeSpec wiring over the vendored
forge installkit (`product_forge._installkit`, canonical:
the-forge/scripts/installkit, byte-parity with sparkforge_aws._installkit).

The engine owns planning, ledger ownership, marker blocks, .mcp.json
registration, drift detection, repair and uninstall. This module only
declares what Product Forge is and which assets it ships.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import __version__
from .. import _installkit as kit

SCOPES = ("project", "user")
PROFILES = kit.PROFILES
HOSTS = kit.HOSTS

MARKER_BODY = """## Product Forge

Specialist Forge for product intelligence, analytics and agentic workspaces.

- CLI: `productforge` (status, doctor, workspace, product, knowledge, agent,
  query, source, dashboard, plan, api, mcp, portal).
- Knowledge: `productforge knowledge import|query <pid>` — FTS5 with citations.
- Agents: `productforge agent create|run|eval|publish` — eval-gated publishing.
- Analytics: `productforge source|query` — read-only SQL (sqlglot validated).
- MCP: `productforge mcp serve` exposes productforge_* tools to hosts.
- Skills: `skills/pf-*` — 16 domain skills (strategy, SQL, dashboards, APIs,
  cloud, governance, FinOps, reporting, knowledge, agent factory).
- API envelope: `forge/PortalApi/1` (schema + correlation_id + data|error).
"""


def _spec() -> kit.ForgeSpec:
    return kit.ForgeSpec(
        forge_id="product-forge",
        package="product_forge",
        distribution="product-forge",
        cli_name="productforge",
        python_spec=">=3.11",
        state_dir=".product-forge",
        mcp_command=("productforge", "mcp", "serve"),
        mcp_server_name="product-forge",
        mcp_verify_tool="productforge_status",
        render_assets=_render_assets,
        marker_body=MARKER_BODY,
        user_state_dir="~/.product-forge",
    )


def _skills_root() -> Path | None:
    """Bundled skills dir: wheel layout (product_forge/skills via
    force-include) or repo checkout (<repo>/skills)."""
    pkg = Path(__file__).resolve().parent.parent / "skills"
    if pkg.is_dir():
        return pkg
    repo = Path(__file__).resolve().parents[3] / "skills"
    return repo if repo.is_dir() else None


def _skill_files(root: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for skill_dir in sorted(root.glob("pf-*/")):
        for f in skill_dir.rglob("*"):
            if f.is_file():
                files[str(f.relative_to(root))] = f.read_bytes()
    return files


def _render_assets(ctx: kit.InstallContext) -> dict[str, bytes]:
    """Ship the pf-* skills into every selected host's skills dir."""
    assets: dict[str, bytes] = {}
    skills_root = _skills_root()
    if skills_root is None:
        return assets
    skill_files = _skill_files(skills_root)
    for host in ctx.hosts:
        for host_dir in kit._host_dirs(host, ctx.scope):
            rel_dir = host_dir.lstrip("~/") if ctx.scope == "user" else host_dir
            if not rel_dir.endswith("skills"):
                continue
            for rel, data in skill_files.items():
                assets[f"{rel_dir}/{rel}"] = data
    return assets


def _ctx(scope: str, profile: str, hosts: tuple[str, ...],
         root: Path | None, dry_run: bool,
         components: tuple[str, ...] | list[str] | None = None,
         cwd: Path | None = None) -> kit.InstallContext:
    if profile not in PROFILES:
        raise kit.InstallError(kit.E_PROFILE, f"profile {profile!r}; {PROFILES}")
    unknown = [h for h in hosts if h not in HOSTS]
    if unknown:
        raise kit.InstallError(kit.E_HOST, f"unknown hosts {unknown}; {HOSTS}")
    spec = _spec()
    target = kit.resolve_scope(spec, scope, cwd or Path.cwd(), root)
    return kit.InstallContext(
        spec=spec, scope=scope, root=target,
        state_dir=kit.state_dir_for(spec, scope, target),
        profile=profile, hosts=hosts, dry_run=dry_run,
        options=kit.component_options(profile, components))


def _source() -> dict[str, Any]:
    try:
        from importlib import metadata as ilm

        ilm.distribution("product-forge")
        return {"kind": "pypi", "name": "product-forge"}
    except Exception:
        return {"kind": "git-checkout", "path": str(Path(__file__).resolve().parents[3])}


def _register(spec: kit.ForgeSpec, root: Path) -> None:
    try:
        kit.register_installation(kit.manifest_for(
            spec, install_root=root, venv=None, version=__version__,
            source=_source(), shim=None))
    except kit.InstallError:
        pass


def install(*, scope: str = "user", profile: str = "recommended",
            hosts: tuple[str, ...] = ("all",), root: Path | None = None,
            components: tuple[str, ...] | None = None,
            dry_run: bool = False, yes: bool = False) -> dict[str, Any]:
    selected = tuple(HOSTS) if hosts == ("all",) else hosts
    ctx = _ctx(scope, profile, selected, root, dry_run, components)
    if ctx.dry_run:
        return kit.plan(ctx)
    with kit.acquire_lock(ctx.state_dir):
        result = kit.apply_install(ctx, approved=yes)
    _register(ctx.spec, ctx.root)
    result["app_home"] = _init_app_home()
    return result


def status(*, scope: str = "project", root: Path | None = None) -> dict[str, Any]:
    # HOSTS superset: render_assets is host-driven and repair needs canonical
    # content for any ledger entry, regardless of which hosts were installed.
    ctx = _ctx(scope, "recommended", tuple(HOSTS), root, False)
    return kit.status(ctx)


def doctor(*, scope: str = "project", root: Path | None = None,
           verify_mcp: bool = False) -> dict[str, Any]:
    ctx = _ctx(scope, "recommended", tuple(HOSTS), root, False)
    doc = kit.doctor(ctx)
    if verify_mcp:
        doc["mcp_verify"] = kit.mcp_verify(ctx.spec)
    return doc


def repair(*, scope: str = "project", root: Path | None = None,
           dry_run: bool = False) -> dict[str, Any]:
    ctx = _ctx(scope, "recommended", tuple(HOSTS), root, dry_run)
    with kit.acquire_lock(ctx.state_dir):
        return kit.repair(ctx)


def update(*, scope: str = "project", profile: str = "recommended",
           hosts: tuple[str, ...] = ("all",), root: Path | None = None,
           yes: bool = False, dry_run: bool = False) -> dict[str, Any]:
    selected = tuple(HOSTS) if hosts == ("all",) else hosts
    ctx = _ctx(scope, profile, selected, root, dry_run)
    if ctx.dry_run:
        return kit.plan(ctx)
    with kit.acquire_lock(ctx.state_dir):
        return kit.apply_install(ctx, approved=yes)


def uninstall(*, scope: str = "project", root: Path | None = None,
              purge_state: bool = False) -> dict[str, Any]:
    ctx = _ctx(scope, "recommended", (), root, False)
    with kit.acquire_lock(ctx.state_dir):
        return kit.uninstall(ctx, purge_state=purge_state)


def _init_app_home() -> dict[str, Any]:
    """The runtime home (config/db/token) — separate from the project install."""
    from ..config import db_path, home_dir, load_config, save_config
    from ..security import TokenStore
    from ..store.sqlite import Store

    home = home_dir("user")
    home.mkdir(parents=True, exist_ok=True)
    (home / "state" / "objects").mkdir(parents=True, exist_ok=True)
    cfg = load_config(home)
    save_config(cfg, home)
    Store(db_path(home, cfg)).close()
    tok = TokenStore(home / str(cfg["api"]["token_file"]))
    return {"home": str(home), "token_preview": tok.preview}
