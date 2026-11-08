import json
import sys

import pytest

from product_forge.knowledge.defuddle import DefuddleError, _run_bounded, parse_defuddle


def test_defuddle_adapter_uses_stdin_json_and_preserves_provenance(monkeypatch):
    calls = {}

    monkeypatch.setattr("product_forge.knowledge.defuddle.executable", lambda _command=None: "defuddle")

    def fake_run(args, payload, **kwargs):
        calls["args"] = args
        calls["payload"] = payload
        calls["kwargs"] = kwargs
        return 0, json.dumps({
            "title": "Runbook", "contentMarkdown": "# Safe path", "parseTime": 7,
        }).encode(), b""

    monkeypatch.setattr("product_forge.knowledge.defuddle._run_bounded", fake_run)
    result = parse_defuddle("<html><body>safe</body></html>", "https://example.com/runbook")

    assert calls["args"] == ["defuddle", "parse", "-", "--json", "--markdown"]
    assert calls["payload"].startswith(b"<html>")
    assert calls["kwargs"]["max_stdout_bytes"] > 0
    assert result["schema"] == "productforge/DefuddleDocument/v1"
    assert result["extractor"] == "defuddle-cli"
    assert result["provenance"]["network_fetch"] == "stdlib-url"


def test_defuddle_adapter_keeps_legacy_content_fallback(monkeypatch):
    monkeypatch.setattr("product_forge.knowledge.defuddle.executable", lambda _command=None: "defuddle")
    monkeypatch.setattr(
        "product_forge.knowledge.defuddle._run_bounded",
        lambda *args, **kwargs: (0, json.dumps({
            "title": "Legacy", "content": "# Legacy content",
        }).encode(), b""),
    )

    result = parse_defuddle("<p>safe</p>", "https://example.com/legacy")

    assert result["content"] == "# Legacy content"


def test_defuddle_adapter_fails_honestly_when_optional_tool_is_missing(monkeypatch):
    monkeypatch.setattr("product_forge.knowledge.defuddle.executable", lambda _command=None: None)
    with pytest.raises(DefuddleError, match="not installed") as exc:
        parse_defuddle("<p>safe</p>", "https://example.com/runbook")
    assert exc.value.code == "DEFUDDLE-UNAVAILABLE"


def test_bounded_runner_terminates_when_stdout_exceeds_limit():
    with pytest.raises(DefuddleError) as exc:
        _run_bounded(
            [sys.executable, "-c", "import sys; sys.stdout.write('x' * 100000)"],
            b"",
            timeout_s=5,
            max_stdout_bytes=32,
            max_stderr_bytes=32,
        )
    assert exc.value.code == "DEFUDDLE-SIZE-LIMIT"


def test_bounded_runner_terminates_on_timeout():
    with pytest.raises(DefuddleError) as exc:
        _run_bounded(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            b"",
            timeout_s=0.1,
            max_stdout_bytes=32,
            max_stderr_bytes=32,
        )
    assert exc.value.code == "DEFUDDLE-TIMEOUT"
