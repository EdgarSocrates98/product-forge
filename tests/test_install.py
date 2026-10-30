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
    plan = kit_lifecycle.install(scope="project", root=project,
                                 hosts=("devin",), dry_run=True)
    assert plan["status"] == "planned" and plan["planned_files"]
    assert any(f["path"].startswith(".devin/skills/pf-") for f in plan["planned_files"])

    doc = kit_lifecycle.install(scope="project", root=project,
                                hosts=("devin",), yes=True)
    assert doc["checks"][0]["status"] == "PASS"
    assert (project / ".agents/skills/pf-sql/SKILL.md").is_file()
    assert (project / ".devin/skills/pf-aws/SKILL.md").is_file()
    assert (project / ".agents/agents/product-intel-coordinator.md").is_file()
    assert (project / ".agents/agents/executors/pf-judge.md").is_file()
    assert "product-forge:managed" in (project / "AGENTS.md").read_text()
    mcp = json.loads((project / ".mcp.json").read_text())
    assert mcp["mcpServers"]["product-forge"]["command"] == "productforge"
    assert doc["app_home"]["home"]


def test_minimal_profile_skips_skills(project):
    plan = kit_lifecycle.install(scope="project", root=project, profile="minimal",
                                 hosts=("devin",), dry_run=True)
    assert not any("skills/" in f["path"] for f in plan["planned_files"])


def test_status_repair_uninstall(project, tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "home"))
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
    kit_lifecycle.install(scope="project", root=project, hosts=("devin",), yes=True)
    s1 = kit_lifecycle.status(scope="project", root=project)["ledger_entries"]
    kit_lifecycle.update(scope="project", hosts=("devin",), yes=True)
    assert kit_lifecycle.status(scope="project", root=project)["ledger_entries"] == s1


def test_mcp_tools_expanded(tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "pf"))
    from product_forge.config import db_path, home_dir, load_config
    from product_forge.mcp.server import call_tool, tool_specs
    from product_forge.store.sqlite import Store

    names = {t["name"] for t in tool_specs()}
    assert {"productforge_status", "product_list", "product_context", "knowledge_query",
            "agent_list", "product_graph", "knowledge_health", "query_validate",
            "dashboard_list", "roadmap", "alerts_list", "audit_list",
            "agent_run", "agent_eval"} <= names

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
    from product_forge.errors import NotFoundError
    with pytest.raises(NotFoundError):
        call_tool("agent_run", {"agent_id": "nope", "input": "hi"})
