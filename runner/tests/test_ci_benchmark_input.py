"""Execute the workflow's actual Python input-validation block locally, not remote CI."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from runner.benchmarks import DEFAULT_CONFIG, load_policy


@pytest.mark.parametrize("mode", ["default", "approved-test-input", "invalid"])
def test_workflow_budget_input_is_validated_without_shell_interpolation(tmp_path, mode):
    repo = Path(__file__).resolve().parents[2]
    workflow = (repo / ".github/workflows/full-stack-conformance.yml").read_text()
    block = workflow.split("      - name: Apply explicitly supplied benchmark budgets", 1)[1]
    script = block.split("          python - <<'PY'\n", 1)[1].split("          PY\n", 1)[0]
    script = "\n".join(line[10:] for line in script.splitlines())
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs/benchmark-thresholds.json").write_bytes(DEFAULT_CONFIG.read_bytes())
    policy = load_policy(DEFAULT_CONFIG)
    if mode == "approved-test-input":
        policy["combined"]["max_run_seconds"] = 10  # Synthetic test input, not a default SLO.
    elif mode == "invalid":
        policy["combined"]["max_run_seconds"] = -1
    value = "" if mode == "default" else json.dumps(policy)
    environment = tmp_path / "github-env"
    env = dict(os.environ, PYTHONPATH=str(repo), GITHUB_ENV=str(environment), BENCHMARK_THRESHOLDS_JSON=value)
    result = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, env=env, capture_output=True)
    if mode == "invalid":
        assert result.returncode != 0 and not environment.exists()
    elif mode == "default":
        assert result.returncode == 0 and not environment.exists()
    else:
        assert result.returncode == 0, result.stderr
        assert environment.read_text().startswith("BENCHMARK_CONFIG=")
        assert json.loads((tmp_path / "local/benchmark-thresholds.json").read_text()) == policy
