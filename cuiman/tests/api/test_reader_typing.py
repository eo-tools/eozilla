"""Check the client return-type contract with the workspace's type checker."""

import subprocess
import sys
from pathlib import Path


def test_read_job_result_infers_requested_type(tmp_path):
    """Keep sync and async generic-overload assertions in the regular test suite."""
    assertions = Path(__file__).resolve().parents[1] / "typing/read_job_result.py"
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "--cache-dir", str(tmp_path), str(assertions)],
        cwd=Path(__file__).resolve().parents[3],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
