from typer.testing import CliRunner

from product_forge import __version__
from product_forge.cli import app


def test_version_flag_is_available_at_the_cli_root() -> None:
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == __version__
