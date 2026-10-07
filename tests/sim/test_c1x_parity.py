import json, subprocess, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]  # tests/sim -> repo

@pytest.mark.slow
def test_c1x_parity_exact():
    subprocess.run([sys.executable, "scripts/sim_c1x_parity.py"], check=True, cwd=ROOT)
    result = json.loads((ROOT / "out/sim_parity_20261007/c1x_parity.json").read_text(encoding="utf-8"))
    assert result["passed"] and result["n_actual"] == result["n_expected"]
    assert result["max_abs_diff_net_bps"] < 1e-6
