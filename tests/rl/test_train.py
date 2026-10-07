"""Window training driver (plan 3 Task 5)."""
import json, math, types
import numpy as np, pandas as pd, pytest
from btcusdt_quant.rl import train as T
from btcusdt_quant.rl.models import TemporalActorCritic
from btcusdt_quant.sim.rolling import WINDOWS
from tests.rl.test_vec_env import T0, market, make_store, NO_FUNDING


def test_nonfinite_validation_raises(monkeypatch):
    monkeypatch.setattr(T, "replay", lambda *a, **k: types.SimpleNamespace(minute_pnl=pd.Series([np.nan])))
    store = make_store(T0, T0 + pd.Timedelta(days=3))
    m = market(0, gaps=0)
    val_fn = T.make_val_fn(store, m, NO_FUNDING, T0 + pd.Timedelta(days=1), T0 + pd.Timedelta(days=3), "cpu")
    with pytest.raises(RuntimeError, match="non-finite"):
        val_fn(TemporalActorCritic(4, 3 + 7, "conv"))


@pytest.mark.parametrize("bad", [np.nan, 0.0, -1.0])
def test_bad_prices_raise_value_error(bad):
    m = market(0, gaps=0)
    T.check_minutes(m)
    m.loc[5000, "low"] = bad
    with pytest.raises(ValueError, match="finite and > 0"):
        T.check_minutes(m)


@pytest.fixture(scope="module")
def smoke_run(tmp_path_factory):
    out = tmp_path_factory.mktemp("rl_run")
    return T.run_config(WINDOWS[0], "S1", "conv", 3e-4, 0, out, smoke=True), out


def test_smoke_run_writes_manifest_and_checkpoint(smoke_run):
    res, out = smoke_run
    assert math.isfinite(res["val_net_bps"]) and res["transitions"] == 2048 and (out / "best.pt").exists()
    man = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert man["data_cutoff"] == "2026-01-01" and man["hypothesis"].startswith("강화학습") and man["input_hashes"]
    assert len(man["selection_trace"]) == 2


def test_selection_trace_uses_validation_only(smoke_run):
    _, out = smoke_run
    text = (out / "manifest.json").read_text(encoding="utf-8")
    man = json.loads(text)
    assert all(set(r) == {"update", "transitions", "val_net_bps"} for r in man["selection_trace"])
    assert not any("test" in k for k in man)
    assert str(WINDOWS[0].test_start) not in text and str(WINDOWS[0].test_end) not in text
