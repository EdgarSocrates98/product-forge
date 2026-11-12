"""Contract tests for the standalone ``forge-obsidian`` release lane."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "publish-forge-obsidian.yml"


def _load() -> dict[str, Any]:
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _triggers(data: dict[str, Any]) -> dict[str, Any]:
    # PyYAML's YAML 1.1 loader interprets the bare ``on`` key as ``True``.
    value = data.get("on", data.get(True))
    assert isinstance(value, dict)
    return value


def _steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    steps = job.get("steps")
    assert isinstance(steps, list) and steps
    return steps


def _run_text(job: dict[str, Any]) -> str:
    return "\n".join(str(step.get("run", "")) for step in _steps(job))


def test_release_workflow_is_manual_and_has_a_version_gate() -> None:
    data = _load()
    trigger = _triggers(data)
    assert set(trigger) == {"workflow_dispatch"}
    assert trigger["workflow_dispatch"]["inputs"]["version"]["required"] is True
    assert set(data["jobs"]) == {"build", "publish", "verify"}
    assert "EXPECTED_VERSION" in _run_text(data["jobs"]["build"])
    assert "version mismatch" in _run_text(data["jobs"]["build"])


def test_release_workflow_builds_checksums_and_publishes_the_same_artifact() -> None:
    data = _load()
    build = data["jobs"]["build"]
    publish = data["jobs"]["publish"]

    assert publish["needs"] == "build"
    assert publish["environment"] == "release"
    assert publish["permissions"] == {"contents": "read", "id-token": "write"}

    build_text = _run_text(build)
    publish_text = _run_text(publish)
    assert "python -m build" in build_text
    assert "python -m twine check dist/*" in build_text
    assert "sha256sum -- *" in build_text
    assert "test -f dist-checksums.txt" in publish_text
    assert "cd dist && sha256sum --check ../dist-checksums.txt" in publish_text
    assert "pypa/gh-action-pypi-publish@" in "\n".join(str(step.get("uses", "")) for step in _steps(publish))

    artifact_steps = [
        step for step in _steps(build) if str(step.get("uses", "")).startswith("actions/upload-artifact@")
    ]
    assert len(artifact_steps) == 1
    assert "dist-checksums.txt" in str(artifact_steps[0]["with"]["path"])
    assert any(str(step.get("uses", "")).startswith("actions/download-artifact@") for step in _steps(publish))


def test_release_workflow_verifies_an_exact_clean_pypi_install() -> None:
    data = _load()
    verify = data["jobs"]["verify"]
    assert verify["needs"] == "publish"
    text = _run_text(verify)
    assert "https://pypi.org/pypi/forge-obsidian/{version}/json" in text
    assert "python -m venv" in text
    assert '"forge-obsidian==${{ inputs.version }}"' in text
    assert "import forge_obsidian" in text


def test_release_workflow_pins_every_action_to_a_commit_sha() -> None:
    for job_name, job in _load()["jobs"].items():
        for step in _steps(job):
            uses = step.get("uses")
            if uses:
                ref = str(uses).partition("@")[2]
                assert re.fullmatch(r"[0-9a-f]{40}", ref), f"{job_name}: {uses}"
