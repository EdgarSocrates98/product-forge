"""productforge install lifecycle — thin ForgeSpec wiring over the vendored
forge installkit (`product_forge._installkit`, canonical:
the-forge/scripts/installkit, byte-parity with sparkforge_aws._installkit).

The engine owns planning, ledger ownership, marker blocks, .mcp.json
registration, drift detection, repair and uninstall. This module only
declares what Product Forge is and which assets it ships.

Consumer docs (AGENTS.md/CLAUDE.md/AGENT_PROTOCOL.md) and the shared
`.forge/context/` workspace registry are owned by the vendored
forge_context engine (`product_forge._forgecontext`) — this module wires
manifest + registration into install/uninstall/repair.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import __version__
from .. import _forgecontext as fctx
from .. import _installkit as kit

SCOPES = ("project", "workspace", "user")
PROFILES = kit.PROFILES
HOSTS = kit.HOSTS
GATEWAY_PROFILES = ("economy", "balanced", "deep")

FORGE_ID = "product-forge"


def _spec() -> kit.ForgeSpec:
    return kit.ForgeSpec(
        forge_id=FORGE_ID,
        package="product_forge",
        distribution="product-forge",
        cli_name="productforge",
        python_spec=">=3.11",
        state_dir=".product-forge",
        mcp_command=("productforge", "mcp", "serve"),
        mcp_server_name="product-forge",
        mcp_verify_tool="productforge_status",
        render_assets=_render_assets,
        # Consumer docs (AGENTS.md/CLAUDE.md/AGENT_PROTOCOL.md) belong to the
        # forge_context layer — `forge:<forge-id>` blocks + the consolidated
        # protocol, not `product-forge:managed` markers (same migration the
        # api-forge/spark-aws/platform-forge siblings made).
        marker_files=(),
        marker_body="",
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


def _bundle_files(root: Path, glob_pat: str) -> dict[str, bytes]:
    """{rel_path: bytes} for every file under matching dirs."""
    files: dict[str, bytes] = {}
    for d in sorted(root.glob(glob_pat)):
        for f in d.rglob("*"):
            if f.is_file():
                # Asset keys are posix rel paths — str() would leak the
                # OS separator into ledger keys on Windows (_safe_rel
                # rejects backslashes).
                files[f.relative_to(root).as_posix()] = f.read_bytes()
    return files


def _agents_root() -> Path | None:
    """Agent profiles dir. Wheel: force-included into product_forge/agents
    (alongside the runtime package — only *.md counts). Dev: repo-root
    agents/. The package itself holds no .md, so the .md check picks right."""
    pkg = Path(__file__).resolve().parent.parent / "agents"
    if pkg.is_dir() and any(pkg.rglob("*.md")):
        return pkg
    repo = Path(__file__).resolve().parents[3] / "agents"
    return repo if repo.is_dir() and any(repo.rglob("*.md")) else None


def _bundled_dir(name: str) -> Path | None:
    """`rules`/`evals`/`knowledge` are *content* bundles at the checkout
    root — never package code (a same-named package under
    ``src/product_forge`` is the runtime module, not a bundle)."""
    pkg = Path(__file__).resolve().parent.parent / name
    if pkg.is_dir() and not (pkg / "__init__.py").exists():
        return pkg
    repo = Path(__file__).resolve().parents[3] / name
    return repo if repo.is_dir() else None


def _render_assets(ctx: kit.InstallContext) -> dict[str, bytes]:
    """Ship pf-* skills into host skills dirs and agent profiles into host
    agents dirs — the installkit's `skill`/`agent` asset kinds gate both.
    Reference bundles (rules/evals/knowledge) land under
    ``<state_dir>/bundle/`` so installs stay self-contained."""
    assets: dict[str, bytes] = {}
    skills_root = _skills_root()
    skill_files = _bundle_files(skills_root, "pf-*/") if skills_root else {}
    agents_root = _agents_root()
    agent_files = {f.relative_to(agents_root).as_posix(): f.read_bytes()
                   for f in agents_root.rglob("*.md")} if agents_root else {}
    for host in ctx.hosts:
        for host_dir in kit._host_dirs(host, ctx.scope):
            rel_dir = host_dir.lstrip("~/") if ctx.scope == "user" else host_dir
            if rel_dir.endswith("skills"):
                for rel, data in skill_files.items():
                    assets[f"{rel_dir}/{rel}"] = data
            elif rel_dir.endswith("agents"):
                for rel, data in agent_files.items():
                    assets[f"{rel_dir}/{rel}"] = data
    # Forge reference bundles — carried with every install (rules catalog,
    # evals, knowledge seeds); runtime resolves them under the state dir.
    try:
        bundle_rel = ctx.state_dir.relative_to(ctx.root).as_posix()
    except ValueError:
        bundle_rel = ctx.spec.state_dir
    for name in ("rules", "evals", "knowledge"):
        root = _bundled_dir(name)
        if not root:
            continue
        for f in root.rglob("*"):
            if not f.is_file() or f.suffix in (".pyc", ".pyo") \
                    or "__pycache__" in f.parts:
                continue
            rel = f.relative_to(root).as_posix()
            assets[f"{bundle_rel}/bundle/{name}/{rel}"] = f.read_bytes()
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


def _bridge_install(*, dry_run: bool, yes: bool) -> dict[str, Any]:
    """Provision the vendored Agent Bridge runtime state
    (``~/.forge-bridge``: dirs, pair.token 0600, providers snapshot,
    ledger). The bridge ships inside product-forge, so its install runs
    in-process — `productforge install` IS the bridge install. A bridge
    failure degrades to ``unverified:*`` instead of crashing the
    forge install."""
    try:
        from forge_agent_bridge.install import lifecycle as bridge
        return bridge.install(scope="user", profile="recommended",
                              dry_run=dry_run, yes=yes)
    except Exception as exc:  # noqa: BLE001 - degraded, never fatal
        return {"forge": "forge-agent-bridge", "status": "unverified",
                "error": str(exc)}


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
            gateway_profile: str | None = None,
            dry_run: bool = False, yes: bool = False) -> dict[str, Any]:
    if gateway_profile is not None and gateway_profile not in GATEWAY_PROFILES:
        raise kit.InstallError(
            kit.E_PROFILE,
            f"gateway_profile {gateway_profile!r}; {GATEWAY_PROFILES}")
    selected = tuple(HOSTS) if hosts == ("all",) else hosts
    ctx = _ctx(scope, profile, selected, root, dry_run, components)
    if ctx.dry_run:
        doc = kit.plan(ctx)
        bridge_doc = _bridge_install(dry_run=True, yes=yes)
        doc["bridge"] = bridge_doc
        planned = doc.get("planned_files")
        if isinstance(planned, list):
            planned.extend(
                {"path": f"bridge:{s['component']} → {s['target']}",
                 "kind": "bridge", "action": s["action"]}
                for s in bridge_doc.get("plan", []))
        return doc
    with kit.acquire_lock(ctx.state_dir):
        result = kit.apply_install(ctx, approved=yes)
    _persist_components(ctx, gateway_profile)
    if result.get("status") == "completed":
        _register_context(ctx, result)
        _drop_stale_doc_entries(ctx)
    _register(ctx.spec, ctx.root)
    result["app_home"] = _init_app_home(gateway_profile)
    result["bridge"] = _bridge_install(dry_run=False, yes=yes)
    return result


def _persist_components(ctx: kit.InstallContext,
                        gateway_profile: str | None) -> None:
    """Wizard/CLI component + execution-profile selection — the runtime
    reads ``components.json`` under the state dir (same contract as
    spark-forge-aws)."""
    import json

    doc = dict(ctx.options)
    if gateway_profile:
        doc["gateway_profile"] = gateway_profile
    doc["profile"] = ctx.profile
    ctx.state_dir.mkdir(parents=True, exist_ok=True)
    (ctx.state_dir / "components.json").write_text(
        json.dumps(doc, indent=2), encoding="utf-8")


def status(*, scope: str = "project", root: Path | None = None) -> dict[str, Any]:
    # HOSTS superset: render_assets is host-driven and repair needs canonical
    # content for any ledger entry, regardless of which hosts were installed.
    ctx = _ctx(scope, "recommended", tuple(HOSTS), root, False)
    return kit.status(ctx)


def doctor(*, scope: str = "project", root: Path | None = None,
           verify_mcp: bool = False) -> dict[str, Any]:
    ctx = _ctx(scope, "recommended", tuple(HOSTS), root, False)
    doc = kit.doctor(ctx)
    try:
        from forge_agent_bridge.install import lifecycle as _bridge_lc
        doc["bridge"] = _bridge_lc.doctor(scope="user")
    except Exception as exc:  # noqa: BLE001 - honest degraded state
        doc["bridge"] = {"status": "unverified", "error": str(exc)}
    doc["portal"] = _portal_composition()
    if verify_mcp:
        doc["mcp_verify"] = kit.mcp_verify(ctx.spec)
    return doc


def _portal_composition() -> dict[str, Any]:
    """Reconcile the last portal composition manifest with live processes.

    ``stale`` means the manifest still claims ``running`` but the recorded
    portal pid is gone (terminal killed, crash).  Absent manifests and
    unreadable state are named states, not failures.
    """
    try:
        from ..config import home_dir
        from ..portal import runtime as _rt
        manifest = _rt._read_manifest(_rt._manifest_path(home_dir()))
    except Exception as exc:  # noqa: BLE001 - honest degraded state
        return {"state": "unverified", "error": str(exc)}
    if not isinstance(manifest, dict):
        return {"state": "unavailable:no_composition"}
    portal_alive = _rt._pid_alive(int(manifest.get("portal", {}).get("pid", 0) or 0))
    bridge_pid = int(manifest.get("bridge", {}).get("pid", 0) or 0)
    state = str(manifest.get("state", "unknown"))
    stale = state == "running" and not portal_alive
    return {
        "state": "stale" if stale else state,
        "portal_alive": portal_alive,
        "bridge_alive": _rt._pid_alive(bridge_pid),
        "url": manifest.get("portal", {}).get("url"),
        "bridge_state": manifest.get("bridge", {}).get("state"),
        "bridge_restarts": manifest.get("bridge", {}).get("restarts", 0),
        "lifecycle_log": manifest.get("lifecycle_log"),
        "stale": stale,
    }


def repair(*, scope: str = "project", root: Path | None = None,
           dry_run: bool = False) -> dict[str, Any]:
    ctx = _ctx(scope, "recommended", tuple(HOSTS), root, dry_run)
    with kit.acquire_lock(ctx.state_dir):
        receipt = kit.repair(ctx)
        if dry_run:
            return receipt
        # Registry de contexto (recuperacao §9.2): refaz journal encalhado,
        # reclaim de lock velho, rebuild de registry+ROUTING.md — so quando
        # `.forge/context/` ja existe (repair nunca cria residuo num root
        # pristino).
        if (ctx.root / fctx.CONTEXT_DIR).exists():
            try:
                out_ctx = fctx.repair_context(ctx.root)
                receipt["repaired"].extend(f"context:{w}" for w in out_ctx["written"])
                rec = out_ctx.get("recovered")
                receipt.setdefault("checks", []).append(
                    {
                        "id": "context-registry",
                        "status": "PASS",
                        "detail": (
                            f"{out_ctx['status']} ({len(out_ctx['written'])} writes)"
                            + (f"; recovered {rec['op']}:{rec['forge_id']}" if rec else "")
                            + ("; stale lock reclaimed" if out_ctx.get("lock_recovered") else "")
                        ),
                    }
                )
            except fctx.ContextError as exc:
                receipt["skipped"].append(f"context:{exc.kind}")
                receipt.setdefault("checks", []).append(
                    {
                        "id": "context-registry",
                        "status": "BLOCKED",
                        "detail": f"{exc.kind}: {exc.detail}",
                    }
                )
        # Blocos `forge:*` dos consumer docs: re-assert deterministico a
        # partir dos manifests em `.forge/context/` — conteudo do usuario
        # fora dos marcadores nunca e tocado.
        try:
            out_docs = fctx.repair_docs(ctx.root, legacy_tags=_LEGACY_DOC_TAGS)
            receipt["repaired"].extend(f"docs:{w}" for w in out_docs["written"])
            receipt.setdefault("checks", []).append(
                {
                    "id": "consumer-docs",
                    "status": "PASS",
                    "detail": f"{out_docs['status']} ({len(out_docs['written'])} writes)",
                }
            )
        except fctx.ContextError as exc:
            receipt["skipped"].append(f"docs:{exc.kind}")
            receipt.setdefault("checks", []).append(
                {"id": "consumer-docs", "status": "BLOCKED", "detail": f"{exc.kind}: {exc.detail}"}
            )
        return receipt


def update(*, scope: str = "project", profile: str = "recommended",
           hosts: tuple[str, ...] = ("all",), root: Path | None = None,
           gateway_profile: str | None = None,
           yes: bool = False, dry_run: bool = False) -> dict[str, Any]:
    if gateway_profile is not None and gateway_profile not in GATEWAY_PROFILES:
        raise kit.InstallError(
            kit.E_PROFILE,
            f"gateway_profile {gateway_profile!r}; {GATEWAY_PROFILES}")
    selected = tuple(HOSTS) if hosts == ("all",) else hosts
    ctx = _ctx(scope, profile, selected, root, dry_run)
    if ctx.dry_run:
        return kit.plan(ctx)
    with kit.acquire_lock(ctx.state_dir):
        result = kit.apply_install(ctx, approved=yes)
    _persist_components(ctx, gateway_profile)
    if result.get("status") == "completed":
        # Update regrava assets — o registry/docs convergem junto
        # (idempotente: re-registro inalterado = zero writes).
        _register_context(ctx, result)
        _drop_stale_doc_entries(ctx)
    result["bridge"] = _bridge_install(dry_run=False, yes=yes)
    return result


def uninstall(*, scope: str = "project", root: Path | None = None,
              purge_state: bool = False) -> dict[str, Any]:
    ctx = _ctx(scope, "recommended", (), root, False)
    with kit.acquire_lock(ctx.state_dir):
        doc = kit.uninstall(ctx, purge_state=purge_state)
        # So chama a camada de contexto quando ha residuo — a transacao
        # adquire lock proprio e criaria `.forge/context/` num root pristino.
        if _docs_leftovers(ctx.root):
            checks = _unregister_context(ctx.root)
            doc.setdefault("checks", []).extend(checks)
            if any(c.get("status") == "BLOCKED" for c in checks):
                doc["status"] = "failed"
    try:
        from forge_agent_bridge.install import lifecycle as _bridge_lc
        # Bridge uninstall is state-preserving by contract (pair.token,
        # events, backups kept) — `purge_state` here only purges PF state.
        doc["bridge"] = _bridge_lc.uninstall(scope="user")
    except Exception as exc:  # noqa: BLE001 - honest degraded state
        doc["bridge"] = {"status": "unverified", "error": str(exc)}
    return doc


def _init_app_home(gateway_profile: str | None = None) -> dict[str, Any]:
    """The runtime home (config/db/token) — separate from the project install."""
    from ..config import db_path, home_dir, load_config, save_config
    from ..security import TokenStore
    from ..store.sqlite import Store

    home = home_dir("user")
    home.mkdir(parents=True, exist_ok=True)
    (home / "state" / "objects").mkdir(parents=True, exist_ok=True)
    cfg = load_config(home)
    if gateway_profile:
        cfg["gateway_profile"] = gateway_profile
    save_config(cfg, home)
    Store(db_path(home, cfg)).close()
    tok = TokenStore(home / str(cfg["api"]["token_file"]))
    return {"home": str(home), "token_preview": tok.preview}


# --------------------------------------------------------------------------
# forge-context/v1 wiring (install-2.0 — mesmo desenho dos siblings
# api-forge/spark-aws/platform-forge). `.forge/context/` e o registry de
# workspace compartilhado entre forges — camada diferente de
# `~/.forge/installations/` (conta) e de `.product-forge/` (ledger). Este
# forge so registra e desregistra o proprio `forge_id`.
# --------------------------------------------------------------------------

_PKG_DIR = Path(__file__).resolve().parents[1]
_REPO_DIR = _PKG_DIR.parent.parent  # src/product_forge -> repo root

# Markers de geracoes anteriores (`product-forge:managed` do installkit
# generico); `install_docs`/`uninstall_docs` os removem ao convergir os
# consumer docs para blocos `forge:*`.
_LEGACY_DOC_TAGS: tuple[str, ...] = ("product-forge:managed",)
_CONSUMER_DOCS: tuple[str, ...] = ("AGENTS.md", "CLAUDE.md", "AGENT_PROTOCOL.md")

_PF_DOMAINS: tuple[str, ...] = (
    "product-intelligence",
    "analytics",
    "dashboards",
    "knowledge-management",
    "agentic-workspaces",
)


def _mds(base: Path) -> list[str]:
    return sorted(p.stem for p in base.glob("*.md")) if base.is_dir() else []


def _drop_stale_doc_entries(ctx: kit.InstallContext) -> None:
    """Remove entradas antigas de ledger para os consumer docs: os arquivos
    agora sao gerenciados pela camada forge_context (blocos `forge:*`), nao
    por hash de arquivo inteiro — conteudo do usuario fora dos marcadores
    nao e drift."""
    ledger = kit.Ledger.load(ctx.state_dir)
    changed = False
    for name in _CONSUMER_DOCS:
        if ledger.get(name) is not None:
            ledger.drop(name)
            changed = True
    if changed:
        ledger.save()


def _context_manifest(ctx: kit.InstallContext) -> dict[str, Any]:
    """Manifesto forge/context/v1 montado das fontes reais: `forge.json` +
    `forge.agentic.json` (pacote ou checkout) e as raizes bundled de
    skills/agents/rules que `_render_assets` usou."""

    def _bundled_json(name: str) -> dict[str, Any] | None:
        for cand in (_PKG_DIR / name, _REPO_DIR / name):
            data = kit._load_json(cand, None)
            if isinstance(data, dict):
                return data
        return None

    forge_json = _bundled_json("forge.json")
    agentic = _bundled_json("forge.agentic.json")

    skills_root = _skills_root()
    skills = (
        sorted(d.name for d in skills_root.glob("pf-*") if d.is_dir())
        if skills_root
        else []
    )
    agents_root = _agents_root()
    coordinators = _mds(agents_root) if agents_root else []
    executors = _mds(agents_root / "executors") if agents_root else []

    rules_root = _bundled_dir("rules")
    rule_areas = (
        sorted(
            {p.stem for p in rules_root.glob("*.yaml")}
            | {p.stem for p in (rules_root / "catalog").glob("*.yaml")}
        )
        if rules_root
        else []
    )

    # Knowledge e runtime nativo (FTS5 via `productforge knowledge`), nao um
    # bundle copiavel — `_bundled_dir` corretamente exclui o pacote
    # `product_forge/knowledge` (tem __init__.py, e codigo, nao conteudo).
    providers = [{"id": "product-knowledge", "interface": "native-runtime"}]

    checks: list[dict[str, Any]] = [
        {
            "id": "skills-bundle",
            "status": "PASS" if skills else "UNVERIFIED",
            "detail": f"{len(skills)} skills",
        },
        {
            "id": "agent-specs",
            "status": "PASS" if coordinators else "UNVERIFIED",
            "detail": f"{len(coordinators)} coordinators, {len(executors)} executors",
        },
        {
            "id": "rules-catalog",
            "status": "PASS" if rule_areas else "UNVERIFIED",
            "detail": f"{len(rule_areas)} rule areas",
        },
    ]
    return fctx.build_manifest(
        forge_id=FORGE_ID,
        name="Product Forge",
        version=__version__,
        cli="productforge",
        package="product_forge",
        distribution="product-forge",
        python_spec=">=3.11",
        scope=ctx.scope,
        profile=ctx.profile,
        hosts=ctx.hosts,
        forge_json=forge_json,
        agentic=agentic,
        kind="specialist",
        domains=_PF_DOMAINS,
        skills=skills,
        coordinators=coordinators,
        agents=executors,
        rule_areas=rule_areas,
        knowledge_providers=providers,
        eval_suites=(
            {
                "id": "agent-eval",
                "kind": "output-verification",
                "command": ["productforge", "agent", "eval", "{agent_id}"],
            },
        ),
        protocols=(
            {"id": "forge/v1", "version": "1"},
            {"id": "forge/context/v1", "version": "1"},
            {"id": "forge/context-registry/v1", "version": "1"},
        ),
        discovery_commands=(
            {
                "id": "product-context",
                "argv": ["productforge", "product", "context", "{product_id}"],
                "mode": "direct-capability",
                "read_only": True,
                "description": "recover the Product Context Package for a product",
            },
            {
                "id": "knowledge-query",
                "argv": ["productforge", "knowledge", "query", "{product_id}", "{question}"],
                "mode": "direct-capability",
                "read_only": True,
                "description": "grounded answer over product knowledge with citations",
            },
            {
                "id": "doctor",
                "argv": ["productforge", "doctor"],
                "mode": "diagnostic-only",
                "read_only": True,
                "description": "environment + installation health",
            },
        ),
        mcp={
            "server_name": "product-forge",
            "command": ["productforge", "mcp", "serve"],
            "verify_tool": "productforge_status",
        },
        resources={
            "skills-bundle": {
                "kind": "bundled",
                "location": "product_forge/skills",
                "optional": False,
            },
            "agents-bundle": {
                "kind": "bundled",
                "location": "product_forge/agents",
                "optional": False,
            },
            "rules-catalog": {
                "kind": "bundled",
                "location": "rules",
                "optional": False,
            },
            "install-state": {
                "kind": "referenced",
                "location": ".product-forge",
                "optional": True,
            },
        },
        mutating_verbs=(
            "install",
            "uninstall",
            "repair",
            "integrate",
            "detach",
            "knowledge import",
            "obsidian import",
            "obsidian export",
            "agent run",
            "agent eval",
            "agent publish",
        ),
        requires_approval=("install", "uninstall", "agent publish"),
        offline_available=True,
        health={
            "status": "healthy" if skills and coordinators and rule_areas else "degraded",
            "checks": checks,
        },
        components=ctx.options or None,
        recorded_by="product-forge",
    )


def _register_context(ctx: kit.InstallContext, receipt: dict[str, Any]) -> None:
    """Grava `.forge/context/` — manifesto + entrada no registry +
    ROUTING.md + consumer docs, numa UNICA transacao (install-2.0 §9.2).
    Falha vira check BLOCKED nomeado no recibo — e o recibo reporta a
    falha (componente mandatorio), nunca install "completed" sem registry.
    ``scope=user`` tem target=``~``: `~/.forge/` e nivel de conta —
    contexto de workspace nao se escreve la (mesma regra dos siblings)."""
    if ctx.scope == "user":
        return
    try:
        manifest = _context_manifest(ctx)
        out = fctx.install_transaction(
            ctx.root, manifest, owner=FORGE_ID, legacy_tags=_LEGACY_DOC_TAGS
        )
        receipt.setdefault("checks", []).append(
            {
                "id": "context-registry",
                "status": "PASS",
                "detail": f".forge/context {out['status']} ({len(out['written'])} writes)",
            }
        )
        docs = out["docs"]
        receipt.setdefault("checks", []).append(
            {
                "id": "consumer-docs",
                "status": "PASS",
                "detail": f"{docs['status']}: {len(docs['written'])} written, "
                f"{len(docs['kept'])} kept",
            }
        )
    except fctx.ContextError as exc:
        receipt.setdefault("checks", []).append(
            {"id": "context-registry", "status": "BLOCKED", "detail": f"{exc.kind}: {exc.detail}"}
        )
        receipt["status"] = "failed"


def _unregister_context(root: Path) -> list[dict[str, Any]]:
    """Remove manifesto/entry/blocos `forge:*` deste forge numa UNICA
    transacao (§9.2) — so artifacts proprios; docs compartilhados
    regeneram para os sobreviventes."""
    try:
        out = fctx.uninstall_transaction(
            root, FORGE_ID, owner=FORGE_ID, legacy_tags=_LEGACY_DOC_TAGS
        )
        docs = out["docs"]
        return [
            {
                "id": "context-registry",
                "status": "PASS",
                "detail": f".forge/context {out['status']}",
            },
            {
                "id": "consumer-docs",
                "status": "PASS",
                "detail": f"{docs['status']}: {len(docs['written'])} changed",
            },
        ]
    except fctx.ContextError as exc:
        return [
            {
                "id": "context-registry",
                "status": "BLOCKED",
                "detail": f"{exc.kind}: {exc.detail}",
            }
        ]


def _docs_leftovers(root: Path) -> bool:
    """True quando o alvo ainda carrega residuo forge_context — leitura sem
    lock; so um hit justifica o caminho de escrita (nunca criamos
    `.forge/context/` num root pristino)."""
    if (root / fctx.CONTEXT_DIR).exists():
        return True
    needles = (
        f"forge:{FORGE_ID}:",
        f"{fctx.DOC_TAG_ECOSYSTEM}:",
        fctx.PROTOCOL_SENTINEL,
        *_LEGACY_DOC_TAGS,
    )
    for name in _CONSUMER_DOCS:
        path = root / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if any(n in text for n in needles):
            return True
    return False
