"""Install lifecycle (vendored forge installkit) + expanded MCP tools."""

import json

import pytest

from product_forge.install import lifecycle as kit_lifecycle


@pytest.fixture()
def project(tmp_path):
    (tmp_path / "proj").mkdir()
    (tmp_path / "proj" / ".git").mkdir()
    return tmp_path / "proj"


def test_install_plan_then_apply(project, tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FORGE_HOME_OVERRIDE", str(tmp_path / "acct"))
    plan = kit_lifecycle.install(scope="project", root=project, hosts=("devin",), dry_run=True)
    assert plan["status"] == "planned" and plan["planned_files"]
    # `.agents/` is the shared host surface — devin reads it natively
    # (vendored installkit 1.0.4+ consolidates skills there, not
    # `.devin/skills/`).
    assert any(f["path"].startswith(".agents/skills/pf-") for f in plan["planned_files"])

    doc = kit_lifecycle.install(scope="project", root=project, hosts=("devin",), yes=True)
    assert doc["checks"][0]["status"] == "PASS"
    assert (project / ".agents/skills/pf-sql/SKILL.md").is_file()
    assert (project / ".agents/skills/pf-aws/SKILL.md").is_file()
    assert (project / ".agents/agents/product-intel-coordinator.md").is_file()
    assert (project / ".agents/agents/executors/pf-judge.md").is_file()
    # Consumer docs are forge_context-managed now: `forge:*` blocks +
    # `.forge/context/` registry, not `product-forge:managed` markers.
    agents_md = (project / "AGENTS.md").read_text()
    assert "forge:product-forge:begin" in agents_md
    assert "forge:ecosystem:begin" in agents_md
    registry = json.loads((project / ".forge/context/registry.json").read_text())
    assert registry["schema"] == "forge/context-registry/v1"
    entry = next(f for f in registry["forges"] if f["forge_id"] == "product-forge")
    assert entry["kind"] == "specialist"
    check_ids = {c["id"] for c in doc["checks"]}
    assert {"context-registry", "consumer-docs"} <= check_ids
    mcp = json.loads((project / ".mcp.json").read_text())
    assert mcp["mcpServers"]["product-forge"]["command"] == "productforge"
    # install-2.1: user-level state is opt-in at project scope — named
    # skipped states, and zero writes under the account dirs.
    assert doc["app_home"]["status"] == "skipped"
    assert doc["bridge"]["status"] == "skipped"
    assert not (tmp_path / "home").exists()
    assert not (tmp_path / "acct" / ".forge-bridge").exists()
    # The account registry entry still records the declared surface.
    manifest = json.loads(
        (tmp_path / "acct" / ".forge" / "installations" / "product-forge.json").read_text()
    )
    assert manifest["installation_kind"] == "content"
    assert manifest["install"]["approval"] == "--yes"
    assert manifest["depends_on"] == ["forge-agent-bridge"]
    assert manifest["mcp"]["verify_tool"] == "productforge_status"


def test_minimal_profile_skips_skills(project):
    plan = kit_lifecycle.install(
        scope="project", root=project, profile="minimal", hosts=("devin",), dry_run=True
    )
    assert not any("skills/" in f["path"] for f in plan["planned_files"])


def test_status_repair_uninstall(project, tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FORGE_HOME_OVERRIDE", str(tmp_path / "acct"))
    kit_lifecycle.install(scope="project", root=project, hosts=("devin",), yes=True)
    s = kit_lifecycle.status(scope="project", root=project)
    assert s["status"] == "healthy" and s["ledger_entries"] > 0

    victim = project / ".agents/skills/pf-sql/SKILL.md"
    victim.unlink()
    assert kit_lifecycle.status(scope="project", root=project)["status"] == "degraded"
    r = kit_lifecycle.repair(scope="project", root=project)
    assert victim.exists() and r["repaired"]

    u = kit_lifecycle.uninstall(scope="project", root=project)
    assert u["removed"]
    assert not (project / ".agents/skills").exists()
    agents_md = project / "AGENTS.md"
    assert not agents_md.exists() or "product-forge:managed" not in agents_md.read_text()


def test_update_idempotent(project, tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FORGE_HOME_OVERRIDE", str(tmp_path / "acct"))
    kit_lifecycle.install(scope="project", root=project, hosts=("devin",), yes=True)
    s1 = kit_lifecycle.status(scope="project", root=project)["ledger_entries"]
    # root must be explicit — without it the scope resolver walks to the
    # repo VCS root and the update would rewrite this checkout.
    kit_lifecycle.update(scope="project", root=project, hosts=("devin",), yes=True)
    assert kit_lifecycle.status(scope="project", root=project)["ledger_entries"] == s1


def test_mcp_tools_expanded(tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "pf"))
    from product_forge.config import db_path, home_dir, load_config
    from product_forge.mcp.server import call_tool, tool_specs
    from product_forge.store.sqlite import Store

    names = {t["name"] for t in tool_specs()}
    assert len(names) == 17
    assert {
        "productforge_status",
        "product_list",
        "product_context",
        "knowledge_query",
        "knowledge_evidence",
        "obsidian_preview",
        "obsidian_files",
        "agent_list",
        "product_graph",
        "knowledge_health",
        "query_validate",
        "dashboard_list",
        "roadmap",
        "alerts_list",
        "audit_list",
        "agent_run",
        "agent_eval",
    } <= names

    home = home_dir("user")
    (home / "state" / "objects").mkdir(parents=True, exist_ok=True)
    st = Store(db_path(home, load_config(home)))
    from product_forge.domain.models import Product

    st.put("products", Product(id="p1", workspace_id="w1", name="P"))
    st.close()

    assert call_tool("query_validate", {"statement": "SELECT 1"})["ok"]
    assert not call_tool("query_validate", {"statement": "DELETE FROM t"})["ok"]
    assert call_tool("product_list", {})["items"]
    assert call_tool("roadmap", {"product_id": "p1"})["lanes"]
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "runbook.md").write_text("# Runbook\n", encoding="utf-8")
    monkeypatch.setenv("FORGE_OBSIDIAN_VAULT", str(vault))
    assert call_tool("obsidian_files", {})["items"][0]["path"] == "runbook.md"
    from product_forge.errors import NotFoundError

    with pytest.raises(NotFoundError):
        call_tool("agent_run", {"agent_id": "nope", "input": "hi"})


# -- guided-install surface (spark-forge-aws parity) -------------------------


def test_workspace_scope_and_gateway_profile(project, tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FORGE_HOME_OVERRIDE", str(tmp_path / "acct"))
    doc = kit_lifecycle.install(
        scope="workspace",
        root=project,
        hosts=("claude",),
        gateway_profile="deep",
        components=("skills", "mcp"),
        init_app=True,  # explicit opt-in: user-config write at workspace scope
        yes=True,
    )
    assert doc["status"] == "completed"
    comp = json.loads((project / ".product-forge/components.json").read_text())
    assert comp["gateway_profile"] == "deep"
    assert comp["profile"] == "recommended"
    # component narrowing: mcp+skills selected → agents NOT shipped
    assert not (project / ".claude/agents").exists() or not any((project / ".claude/agents").rglob("*.md"))
    from product_forge.config import home_dir, load_config

    assert load_config(home_dir("user"))["gateway_profile"] == "deep"


def test_rules_bundle_and_no_code_packages(project, tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FORGE_HOME_OVERRIDE", str(tmp_path / "acct"))
    kit_lifecycle.install(scope="project", root=project, hosts=("devin",), yes=True)
    bundle = project / ".product-forge" / "bundle"
    assert (bundle / "rules" / "catalog" / "pf-sql.yaml").is_file()
    # code packages are never bundled (knowledge is a runtime module)
    assert not (bundle / "knowledge").exists()
    assert not list(bundle.rglob("*.pyc"))


def test_gateway_profile_validation_and_host_adapter():
    from product_forge.install.cli import _hosts_tuple

    assert _hosts_tuple("all") == ("all",)
    assert _hosts_tuple("claude,devin") == ("claude", "devin")
    assert _hosts_tuple("none") == ()
    from product_forge import _installkit as kit

    with pytest.raises(kit.InstallError):
        kit_lifecycle.install(scope="project", gateway_profile="bogus", dry_run=True)


def test_wizard_module_contract():
    """run_wizard exists with the shared contract; guided route needs TTY."""
    from product_forge.install import cli as icli
    from product_forge.ui.wizard import run_wizard  # noqa: F401

    assert icli.guided_install_available() in (True, False)
    assert callable(icli.run_guided_install)


# -- install-2.1: user-state opt-in + bridge ownership ----------------------


def test_opt_in_provisions_app_home_and_bridge(project, tmp_path, monkeypatch):
    """--init-app/--with-bridge at project scope provision user-level
    state once; the service check is module-import based (the wheel
    ships no `forge-bridge` script); a second run skips instead of
    rewriting the providers/config/ledger snapshots."""
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "home"))
    acct = tmp_path / "acct"
    monkeypatch.setenv("FORGE_HOME_OVERRIDE", str(acct))
    doc = kit_lifecycle.install(
        scope="project",
        root=project,
        hosts=("devin",),
        init_app=True,
        with_bridge=True,
        yes=True,
    )
    assert doc["app_home"]["home"]
    bridge_root = acct / ".forge-bridge"
    assert (bridge_root / "pair.token").is_file()
    assert (bridge_root / "providers.json").is_file()
    # ownership marker lives under THIS install's state dir
    assert (project / ".product-forge" / "bridge-provisioned").is_file()
    actions = {s["action"] for s in doc["bridge"]["plan"]}
    assert "verify-module" in actions
    assert "verify-cli" not in actions
    assert any(
        s.get("action") == "verify-module" and s.get("result") == "importable"
        for s in doc["bridge"]["applied"]
    )
    # already provisioned → skipped; snapshots are not stomped
    providers_before = (bridge_root / "providers.json").read_bytes()
    doc2 = kit_lifecycle.install(
        scope="project", root=project, hosts=("devin",), with_bridge=True, yes=True
    )
    assert doc2["bridge"]["status"] == "skipped"
    assert (bridge_root / "providers.json").read_bytes() == providers_before


def test_uninstall_removes_only_self_provisioned_bridge(project, tmp_path, monkeypatch):
    """Ownership-aware bridge cleanup: the provisioning marker decides —
    pair.token/events/backups are user content and always survive."""
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "home"))
    acct = tmp_path / "acct"
    monkeypatch.setenv("FORGE_HOME_OVERRIDE", str(acct))
    kit_lifecycle.install(
        scope="project", root=project, hosts=("devin",), with_bridge=True, yes=True
    )
    bridge_root = acct / ".forge-bridge"
    u = kit_lifecycle.uninstall(scope="project", root=project)
    assert u["status"] == "completed"
    assert not (bridge_root / "providers.json").exists()
    assert not (bridge_root / "components.json").exists()
    assert (bridge_root / "pair.token").exists()  # user content preserved
    assert not (project / ".product-forge" / "bridge-provisioned").exists()


def test_uninstall_preserves_foreign_bridge_state(project, tmp_path, monkeypatch):
    """Bridge state without our marker (unknown provenance) is never
    deleted; a registered standalone install is foreign-owned even when
    our marker is present."""
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "home"))
    acct = tmp_path / "acct"
    monkeypatch.setenv("FORGE_HOME_OVERRIDE", str(acct))
    bridge_root = acct / ".forge-bridge"
    bridge_root.mkdir(parents=True)
    (bridge_root / "providers.json").write_text('{"foreign": true}')
    (bridge_root / "components.json").write_text('{"foreign": true}')
    kit_lifecycle.install(scope="project", root=project, hosts=("devin",), yes=True)
    u = kit_lifecycle.uninstall(scope="project", root=project)
    assert u["bridge"]["status"] == "skipped"
    assert (bridge_root / "providers.json").read_text() == '{"foreign": true}'
    # a standalone bridge registration outranks our marker
    inst = acct / ".forge" / "installations"
    inst.mkdir(parents=True, exist_ok=True)
    (inst / "forge-agent-bridge.json").write_text('{"forge_id": "forge-agent-bridge"}')
    (project / ".product-forge").mkdir(exist_ok=True)
    (project / ".product-forge" / "bridge-provisioned").write_text("product-forge\n")
    u2 = kit_lifecycle.uninstall(scope="project", root=project)
    assert u2["bridge"]["status"] == "skipped"
    assert "foreign-owned" in u2["bridge"]["reason"]
    assert (bridge_root / "providers.json").read_text() == '{"foreign": true}'


def test_discover_projects_finds_gitless_members(tmp_path):
    """installkit 1.0.6: a directory counts as a workspace member via
    .git OR a project manifest — gitless checkouts are first-class."""
    from product_forge import _installkit as kit

    ws = tmp_path / "ws"
    (ws / "git-member" / ".git").mkdir(parents=True)
    (ws / "gitless-member").mkdir()
    (ws / "gitless-member" / "pyproject.toml").write_text("[project]\nname='x'\n")
    (ws / "plain-dir").mkdir()  # no markers → not a member
    (ws / ".venv" / "git-member" / ".git").mkdir(parents=True)  # IGNORED_DIRS
    found = {p.name for p in kit.discover_projects(ws)}
    assert found == {"git-member", "gitless-member"}
