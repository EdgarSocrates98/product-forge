"""Install lifecycle state model (cycle 16.1 wave-07) — ``forge/InstallLifecycle/v1``.

The receipt ``status`` is the coarse operation verdict; ``lifecycle.state``
is the derived, honest position of the installation. ``completed`` is never
a synonym for production-ready: it maps to ``applied`` (writes executed,
verification pending), ``verified`` (checks PASS) or ``failed`` — never to
``ready``/``certified``.

Covers the wave-07 fronts end to end:

- lifecycle envelope on plan/apply/repair/uninstall receipts and on
  status/doctor health docs;
- incremental reinstall (§7.4): unchanged managed assets are not re-touched;
- host-mirror sync: installed host assets are byte-identical to the bundle;
- resolved, absolute ``.mcp.json`` argv (§9.3 — no PATH launch);
- honest unverified states and a truly read-only ``repair --dry-run``;
- compact L0 forge block in the consumer docs (§8.1).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from product_forge.install import lifecycle as kit_lifecycle
from product_forge.install import lifecycle_state as lcs


@pytest.fixture()
def project(tmp_path):
    (tmp_path / "proj").mkdir()
    (tmp_path / "proj" / ".git").mkdir()
    return tmp_path / "proj"


def _receipt(status: str, verification: str | None = None, **kw: object) -> dict:
    doc: dict = {"status": status, "verification": {"status": verification or "PASS"}}
    doc.update(kw)
    return doc


# -- closed vocabulary + derivation mapping ---------------------------------


def test_state_vocabulary_is_closed() -> None:
    assert set(lcs.STATES) == {
        "planned",
        "blocked",
        "failed",
        "applied",
        "partially_applied",
        "verified",
        "unverified",
        "ready",
        "certified",
    }


@pytest.mark.parametrize(
    ("doc", "want"),
    [
        (_receipt("planned", "UNVERIFIED"), "planned"),
        (_receipt("blocked", "UNVERIFIED"), "blocked"),
        (_receipt("refused", "UNVERIFIED"), "blocked"),
        (_receipt("unsupported", "UNVERIFIED"), "blocked"),
        (_receipt("failed", "FAIL"), "failed"),
        (_receipt("unverified", "UNVERIFIED"), "unverified"),
        (_receipt(""), "unverified"),
        # completed is never production-ready by itself:
        (_receipt("completed", "PASS"), "verified"),
        (_receipt("completed", "UNVERIFIED"), "applied"),
        (_receipt("completed", "BLOCKED"), "applied"),
        (_receipt("completed", "FAIL"), "failed"),
        (_receipt("mystery", "PASS"), "unverified"),
    ],
)
def test_receipt_state_mapping(doc: dict, want: str) -> None:
    state, detail = lcs.receipt_state(doc)
    assert state == want
    assert detail


def test_completed_never_ready_or_certified() -> None:
    """§5.3 core: 'completed' alone can never reach the ready/certified
    states — those require health or external certification evidence."""
    for verification in ("PASS", "FAIL", "UNVERIFIED", "BLOCKED", "NOT_APPLICABLE"):
        state, _ = lcs.receipt_state(_receipt("completed", verification))
        assert state not in {"ready", "certified"}


def test_partial_batch_is_partially_applied() -> None:
    doc = _receipt(
        "failed",
        "FAIL",
        forges=[
            {"forge_id": "a", "status": "completed"},
            {"forge_id": "b", "status": "blocked"},
            {"forge_id": "c", "status": "failed"},
        ],
        checks=[{"id": "forge:b", "status": "FAIL"}],
    )
    state, detail = lcs.receipt_state(doc)
    assert state == "partially_applied"
    assert "1/3" in detail


def test_all_gated_batch_is_blocked_not_failed() -> None:
    doc = _receipt(
        "failed",
        "FAIL",
        checks=[
            {"id": "forge:a", "status": "BLOCKED"},
            {"id": "forge:b", "status": "BLOCKED"},
        ],
    )
    state, _ = lcs.receipt_state(doc)
    assert state == "blocked"


@pytest.mark.parametrize(
    ("health", "want"),
    [
        ("healthy", "ready"),
        ("degraded", "partially_applied"),
        ("broken", "failed"),
        ("unverified", "unverified"),
    ],
)
def test_health_state_mapping(health: str, want: str) -> None:
    state, _ = lcs.health_state({"status": health})
    assert state == want


def test_old_receipt_without_lifecycle_still_derives() -> None:
    """Backward compat: a pre-16.1 receipt parses and gets a state view —
    the lifecycle block is a view over evidence, never a stored verdict."""
    legacy = {
        "schema": "forge/InstallReceipt/v1",
        "receipt_id": "sha256:abc",
        "forge_id": "x",
        "operation": "install",
        "scope": "project",
        "target_root": "/nonexistent/x",  # noqa: S108 - fixture-shaped doc, no I/O
        "managed_files": [],
        "checks": [],
        "created_at": "2025-01-01T00:00:00+00:00",
        "status": "completed",
        "verification": {"status": "PASS"},
    }
    state, _ = lcs.receipt_state(legacy)
    assert state == "verified"
    block = lcs.receipt_block(legacy)
    assert block == {
        "schema": "forge/InstallLifecycle/v1",
        "state": "verified",
        "detail": block["detail"],
    }


def test_terminal_success_set() -> None:
    assert {"verified", "ready", "certified"} == lcs.TERMINAL_SUCCESS
    assert "applied" not in lcs.TERMINAL_SUCCESS
    assert "planned" not in lcs.TERMINAL_SUCCESS


def _assert_lifecycle_block(doc: dict, states: set[str] | None = None) -> dict:
    block = doc["lifecycle"]
    assert block["schema"] == lcs.LIFECYCLE_SCHEMA
    assert block["state"] in (states or lcs.STATES)
    assert set(block) <= {"schema", "state", "detail"}
    assert isinstance(block.get("detail"), str) and block["detail"]
    return block


# -- end-to-end over the real lifecycle -------------------------------------


def test_dry_run_plan_carries_planned_lifecycle(project, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FORGE_HOME_OVERRIDE", str(tmp_path / "acct"))
    plan = kit_lifecycle.install(scope="project", root=project, hosts=("devin",), dry_run=True)
    assert plan["status"] == "planned"
    _assert_lifecycle_block(plan, {"planned"})
    # dry-run wrote nothing
    assert not (project / ".product-forge").exists()


def test_install_receipt_lifecycle_and_persistence(project, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FORGE_HOME_OVERRIDE", str(tmp_path / "acct"))
    doc = kit_lifecycle.install(scope="project", root=project, hosts=("devin",), yes=True)
    assert doc["status"] == "completed"
    _assert_lifecycle_block(doc, {"verified"})
    # the persisted receipt carries the final state view too
    receipts = sorted((project / ".product-forge" / "receipts").glob("install-*.json"))
    assert receipts
    persisted = json.loads(receipts[-1].read_text())
    _assert_lifecycle_block(persisted, {"verified"})


def test_incremental_reinstall_does_not_rewrite_unchanged(
    project, tmp_path, monkeypatch
) -> None:
    """§7.4 — a second install reports every managed asset ``unchanged``
    and re-touches none of them: zero byte writes, mtimes preserved."""
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FORGE_HOME_OVERRIDE", str(tmp_path / "acct"))
    first = kit_lifecycle.install(scope="project", root=project, hosts=("devin",), yes=True)
    assert first["counts"]["written"] > 0
    victim = project / ".agents/skills/pf-sql/SKILL.md"
    mtime_before = victim.stat().st_mtime_ns

    second = kit_lifecycle.install(scope="project", root=project, hosts=("devin",), yes=True)
    assert second["status"] == "completed"
    actions = {f["action"] for f in second["managed_files"]}
    assert actions <= {"unchanged", "adopted", "skipped"}
    assert second["counts"]["written"] == 0
    assert second["counts"]["written_bytes"] == 0
    assert second["counts"].get("unchanged", 0) > 0
    assert victim.stat().st_mtime_ns == mtime_before
    _assert_lifecycle_block(second, {"verified"})


def test_host_mirrors_byte_synced_with_bundle(project, tmp_path, monkeypatch) -> None:
    """Every shipped host asset is byte-identical to the bundled source —
    host mirrors are synced copies, never divergent forks (§7.2)."""
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FORGE_HOME_OVERRIDE", str(tmp_path / "acct"))
    kit_lifecycle.install(scope="project", root=project, hosts=("devin", "claude"), yes=True)

    skills_root = kit_lifecycle._skills_root()
    assert skills_root is not None
    shared = project / ".agents/skills"
    claude = project / ".claude/skills"
    checked = 0
    for skill_dir in sorted(skills_root.glob("pf-*")):
        assert skill_dir.is_dir()
        for src in sorted(skill_dir.rglob("*")):
            if not src.is_file():
                continue
            rel = src.relative_to(skills_root).as_posix()
            assert (shared / rel).read_bytes() == src.read_bytes(), rel
            assert (claude / rel).read_bytes() == src.read_bytes(), rel
            checked += 1
    assert checked > 0

    agents_root = kit_lifecycle._agents_root()
    assert agents_root is not None
    for src in sorted(agents_root.rglob("*.md")):
        rel = src.relative_to(agents_root).as_posix()
        assert (project / ".agents/agents" / rel).read_bytes() == src.read_bytes(), rel
        assert (project / ".claude/agents" / rel).read_bytes() == src.read_bytes(), rel


def test_mcp_managed_key_uses_resolved_absolute_argv(project, tmp_path, monkeypatch) -> None:
    """§9.3 — the managed ``.mcp.json`` entry never launches the forge via
    PATH: no registered shim → interpreter-pinned module argv."""
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FORGE_HOME_OVERRIDE", str(tmp_path / "acct"))
    kit_lifecycle.install(scope="project", root=project, hosts=("devin",), yes=True)
    entry = json.loads((project / ".mcp.json").read_text())["mcpServers"]["product-forge"]
    assert entry["command"] == sys.executable
    assert Path(entry["command"]).is_absolute()
    assert entry["args"] == ["-m", "product_forge", "mcp", "serve"]


def test_status_and_doctor_carry_lifecycle(project, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FORGE_HOME_OVERRIDE", str(tmp_path / "acct"))
    kit_lifecycle.install(scope="project", root=project, hosts=("devin",), yes=True)
    st = kit_lifecycle.status(scope="project", root=project)
    _assert_lifecycle_block(st, {"ready"})
    doc = kit_lifecycle.doctor(scope="project", root=project)
    _assert_lifecycle_block(doc)
    # the managed-key probe is real evidence, not file presence: the kit
    # doctor ran the JSON-RPC handshake against the resolved argv.
    handshake = next(c for c in doc["checks"] if c["id"] == "mcp-handshake")
    assert handshake["status"] == "PASS"


def test_status_unverified_install_is_unverified(project, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FORGE_HOME_OVERRIDE", str(tmp_path / "acct"))
    st = kit_lifecycle.status(scope="project", root=project)
    assert st["status"] == "unverified"
    _assert_lifecycle_block(st, {"unverified"})


def test_repair_dry_run_is_read_only(project, tmp_path, monkeypatch) -> None:
    """Dry-run writes nothing (§10.3): the plan names the action, the
    drifted file stays missing until the real run."""
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FORGE_HOME_OVERRIDE", str(tmp_path / "acct"))
    kit_lifecycle.install(scope="project", root=project, hosts=("devin",), yes=True)
    victim = project / ".agents/skills/pf-sql/SKILL.md"
    victim.unlink()

    plan = kit_lifecycle.repair(scope="project", root=project, dry_run=True)
    assert plan["status"] == "planned"
    _assert_lifecycle_block(plan, {"planned"})
    actions = {a["path"]: a["action"] for a in plan["repair_plan"]["actions"]}
    assert actions[".agents/skills/pf-sql/SKILL.md"] == "restore"
    assert not victim.exists()  # read-only: nothing restored

    fixed = kit_lifecycle.repair(scope="project", root=project)
    assert victim.exists()
    assert ".agents/skills/pf-sql/SKILL.md" in fixed["repaired"]
    _assert_lifecycle_block(fixed, {"verified"})


def test_uninstall_receipt_carries_lifecycle(project, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FORGE_HOME_OVERRIDE", str(tmp_path / "acct"))
    kit_lifecycle.install(scope="project", root=project, hosts=("devin",), yes=True)
    doc = kit_lifecycle.uninstall(scope="project", root=project)
    _assert_lifecycle_block(doc, {"verified"})
    receipts = sorted((project / ".product-forge" / "receipts").glob("uninstall-*.json"))
    persisted = json.loads(receipts[-1].read_text())
    _assert_lifecycle_block(persisted, {"verified"})


def test_docs_only_install_reports_registered_truth(project, tmp_path, monkeypatch) -> None:
    """Honest workspace state: ``--host none`` + minimal leaves an empty
    kit ledger but a real registry entry — status must not claim
    NOT_INSTALLED where the context registry proves otherwise."""
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FORGE_HOME_OVERRIDE", str(tmp_path / "acct"))
    doc = kit_lifecycle.install(
        scope="project", root=project, hosts=(), components=("skills",), yes=True
    )
    assert doc["status"] == "completed"
    st = kit_lifecycle.status(scope="project", root=project)
    assert st["ledger_entries"] == 0
    assert st["status"] == "healthy"
    assert st["context_registered"] is True
    _assert_lifecycle_block(st, {"ready"})


def test_receipt_context_bytes_are_honest(project, tmp_path, monkeypatch) -> None:
    """Context-budget metadata reports observable bytes only (§8.5) —
    never invented token counts."""
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FORGE_HOME_OVERRIDE", str(tmp_path / "acct"))
    doc = kit_lifecycle.install(scope="project", root=project, hosts=("devin",), yes=True)
    ctx = doc["context"]
    assert ctx["skills_bytes"] > 0
    assert ctx["managed_bytes"] >= ctx["skills_bytes"]
    assert "token" not in json.dumps(ctx).lower()


def test_mcp_verify_cli_probes_resolved_argv() -> None:
    """``productforge mcp verify`` — the wizard's next step exists and runs
    the real handshake against the resolved argv (exit 0 on PASS)."""
    from typer.testing import CliRunner

    from product_forge.cli import app

    result = CliRunner().invoke(app, ["mcp", "verify"])
    assert result.exit_code == 0, result.stdout
    out = json.loads(result.stdout)
    assert out["id"] == "mcp-handshake"
    assert out["status"] == "PASS"
    assert "productforge_status" in out["tools"]


def test_compact_l0_forge_block_in_consumer_docs(project, tmp_path, monkeypatch) -> None:
    """§8.1 minimal L0 boot: the AGENTS.md ``forge:`` block is the
    routing-critical minimum — identity, domains, verifiable pointers —
    not a duplicated instruction dump."""
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FORGE_HOME_OVERRIDE", str(tmp_path / "acct"))
    kit_lifecycle.install(scope="project", root=project, hosts=("devin",), yes=True)
    text = (project / "AGENTS.md").read_text()
    begin = text.index("forge:product-forge:begin")
    end = text.index("forge:product-forge:end")
    block = text[begin:end]
    assert "product-forge" in block
    assert ".forge/context/capabilities/product-forge.json" in block
    assert "AGENT_PROTOCOL.md" in block
    # compact: the verbose block listed every discovery verb inline
    assert len(block) < 1200
    # the manifest it points to actually exists (verifiable pointer)
    assert (project / ".forge/context/capabilities/product-forge.json").is_file()
