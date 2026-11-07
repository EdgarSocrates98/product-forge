import io

from typer.testing import CliRunner

from product_forge import __version__
from product_forge import cli
from product_forge.cli import app


def test_version_flag_is_available_at_the_cli_root() -> None:
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_json_output_falls_back_to_ascii_for_legacy_windows_codepages(monkeypatch) -> None:
    class LegacyStdout(io.StringIO):
        encoding = "cp1252"

    stream = LegacyStdout()
    monkeypatch.setattr(cli.sys, "stdout", stream)
    cli._out({"plan": "managed bridge → workspace"})
    output = stream.getvalue()
    assert "managed bridge" in output
    assert "\\u2192" in output
