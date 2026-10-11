"""EWA7 reference book (Codex redesign 2026-10-11): equal weight over available core sleeves, min(1, 2/|A_T|);
binary OFF/ON RL head with ON re-weighting; all-ON == EWA7 exactly; Codex read-only expected values."""
import numpy as np, pandas as pd, pytest
from btcusdt_quant.rl import allocator_contracts as C, allocator_env as E, allocator_vec_env as V, gates as GT

H = 3600 * 10**9
TS = lambda s: pd.Timestamp(s, tz="UTC").value  # noqa: E731


def test_ewa_levels():
    on = np.array([[1, 1, 0, 0, 0, 0, 0], [1, 1, 1, 1, 0, 0, 0], [1] * 7, [0] * 7], bool)
    lv = C.ewa_levels(on)
    assert lv[0].tolist() == [1, 1, 0, 0, 0, 0, 0] and np.allclose(lv[1, :4], 0.5) and np.allclose(lv[2], 2 / 7)
    assert lv[3].sum() == 0 and np.all(lv.sum(1) <= C.GROSS_CAP + 1e-12)


@pytest.fixture(scope="module")
def cell():
    return E.load_cell("o2_p0.5", fold="F4", cadence_h=4, allow_test=False)


def test_binary_all_on_equals_ewa7(cell):
    v = V.VecAllocatorEnv(cell, 2, cadence_h=4, static_mode="ewa7", binary=True, penalties=False)
    obs = v.reset(np.array([TS("2023-01-01"), TS("2024-06-01")]), 360)
    me, mp, mo = obs["masks"]
    assert not me[:, :, 2:].any() and not mo[:, :, 1:].any() and not mp[:, :, 1].any()
    z = np.zeros((2, 7), np.int64)
    tot = 0.0
    while True:
        on = obs["masks"][0][:, :, 1].astype(np.int64)                 # ON wherever legal (available)
        obs, r, done, info = v.step(on, z, z)
        assert np.array_equal(info["net_rl"], info["net_st"]) and np.all(r == 0.0)
        assert info["gross_reserved"].max() <= C.GROSS_CAP + 1e-12 and info["dd_coef"] == info["to_coef"] == 0.0
        tot += float(np.abs(info["net_st"]).sum())
        if done:
            break
    assert tot > 0


def test_ewa7_codex_expected_o2_p05():
    """Codex read-only value: 2022..2025 yearly flat-reset episodes (1h), net4 / hourly MDD / daily boot60."""
    cd = E.load_cell("o2_p0.5", fold="F4", allow_test=False)
    hours = []
    for y in range(2022, 2026):
        a, b = TS(f"{y}-01-01"), TS(f"{y + 1}-01-01")
        v = V.VecAllocatorEnv(cd, 1, static_mode="ewa7")
        v.reset(np.array([a]), (b - a) // H)
        z = np.zeros((1, 7), np.int64)
        for _ in range((b - a) // H):
            hours.append(v.step(z, z, z)[3]["net_st"][0])
    h = np.array(hours)
    d = h.reshape(-1, 24).sum(1)
    assert round(h.sum(), 3) == 23663.788 and round(GT.mdd(h), 3) == 2931.355 and round(GT.boot_p05(d, 60), 3) == 7.839
