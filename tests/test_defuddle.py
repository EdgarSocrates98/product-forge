import json
import subprocess

import pytest

from product_forge.knowledge.defuddle import DefuddleError, parse_defuddle


def test_defuddle_adapter_uses_stdin_json_and_preserves_provenance(monkeypatch):
    calls = {}

    class Completed:
        returncode = 0
        stdout = json.dumps({"title": "Runbook", "contentMarkdown": "# Safe path", "parseTime": 7})

    monkeypatch.setattr("product_forge.knowledge.defuddle.executable", lambda _command=None: "defuddle")

    def fake_run(args, **kwargs):
        calls["args"] = args
        calls["kwargs"] = kwargs
        return Completed()

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = parse_defuddle("<html><body>safe</body></html>", "https://example.com/runbook")

    assert calls["args"] == ["defuddle", "parse", "-", "--json", "--markdown"]
    assert calls["kwargs"]["input"].startswith("<html>")
    assert result["schema"] == "productforge/DefuddleDocument/v1"
    assert result["extractor"] == "defuddle-cli"
    assert result["provenance"]["network_fetch"] == "stdlib-url"


def test_defuddle_adapter_keeps_legacy_content_fallback(monkeypatch):
    class Completed:
        returncode = 0
        stdout = json.dumps({"title": "Legacy", "content": "# Legacy content"})

    monkeypatch.setattr("product_forge.knowledge.defuddle.executable", lambda _command=None: "defuddle")
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: Completed())

    result = parse_defuddle("<p>safe</p>", "https://example.com/legacy")

    assert result["content"] == "# Legacy content"


def test_defuddle_adapter_fails_honestly_when_optional_tool_is_missing(monkeypatch):
    monkeypatch.setattr("product_forge.knowledge.defuddle.executable", lambda _command=None: None)
    with pytest.raises(DefuddleError, match="not installed") as exc:
        parse_defuddle("<p>safe</p>", "https://example.com/runbook")
    assert exc.value.code == "DEFUDDLE-UNAVAILABLE"
