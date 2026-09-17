"""Keep CLI discovery independent of the API and its runtime dependencies."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["--help"],
        ["--version"],
        ["configure", "--help"],
        ["login", "--help"],
        ["list-processes", "--help"],
        ["lp", "--help"],
        ["validate-request", "--help"],
        ["show-app", "--help"],
        ["validate-request", "example", "--input", "n=1", "--format", "json"],
    ],
)
def test_cli_discovery_does_not_import_runtime_dependencies(args):
    script = """
import importlib.abc
import sys

blocked = {
    'cuiman.api', 'cuiman.app', 'cuiman.cli.client', 'cuiman.cli.config',
    'pydantic_settings', 'IPython', 'httpx2', 'authlib',
    'joserfc', 'keyring', 'remotestate', 'yaml',
}
if sys.argv[1:2] == ['validate-request'] and '--help' not in sys.argv:
    blocked.discard('yaml')

class BlockRuntimeImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(name + '.') for name in blocked):
            raise AssertionError('Unexpected startup import: ' + fullname)

sys.meta_path.insert(0, BlockRuntimeImports())
from cuiman.cli import cli, new_cli
from typer.testing import CliRunner

for application in (cli, new_cli(name='anolis-client', version='1.2.3')):
    result = CliRunner().invoke(application, sys.argv[1:])
    assert result.exit_code == 0, (result.output, result.exception)
    if 'example' in sys.argv:
        import json
        request = json.loads(result.output)
        assert request['process_id'] == 'example'
        assert request['inputs'] == {'n': 1}
"""
    workspace = Path(__file__).resolve().parents[3]
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(workspace / package / "src") for package in ("cuiman", "gavicore")]
        + [env.get("PYTHONPATH", "")]
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script, *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_configure_help_lists_supported_authentication_choices():
    from typer.main import get_command

    from cuiman.api.auth.config import AUTH_TYPE_NAMES, OAUTH2_GRANT_TYPE_NAMES
    from cuiman.cli import cli

    configure = get_command(cli).commands["configure"]
    options = {option.name: option for option in configure.params}
    assert "|".join(AUTH_TYPE_NAMES) in options["auth_type"].help
    assert "|".join(OAUTH2_GRANT_TYPE_NAMES) in options["grant_type"].help
