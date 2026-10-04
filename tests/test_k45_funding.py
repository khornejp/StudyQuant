import pandas as pd
import pytest

from out import k45_funding as funding


def test_archive_uses_scheduled_t_rate():
    settlements = funding.load_settlements()
    rates = settlements.set_index("time").rate
    assert rates.loc[pd.Timestamp("2021-01-08 00:00", tz="UTC")] == pytest.approx(0.00213517)
    assert rates.loc[pd.Timestamp("2021-01-08 08:00", tz="UTC")] == pytest.approx(0.00092044)


def test_archive_count_and_normalisation_error():
    settlements = funding.load_settlements()
    assert len(settlements) == 7_119
    error = (settlements.raw_calc_time - settlements.time).abs()
    assert error.max() <= pd.Timedelta(seconds=60)


def test_long_24h_has_three_internal_settlements():
    rates = [0.0001, -0.0002, 0.0003]
    settlements = pd.DataFrame({
        "time": pd.to_datetime(["2024-01-01 08:00", "2024-01-01 16:00",
                                "2024-01-02 00:00"], utc=True),
        "rate": rates,
    })
    internal, boundary = funding.trade_funding(
        1, pd.Timestamp("2024-01-01 04:00", tz="UTC"),
        pd.Timestamp("2024-01-02 04:00", tz="UTC"), settlements, "PESS")
    assert internal == pytest.approx(-sum(rates) * 1e4)
    assert boundary == 0


@pytest.mark.parametrize(
    "rate,pess,opt",
    [(0.0001, -1.0, 0.0), (-0.0001, 0.0, 1.0)],
)
def test_exit_boundary_is_sign_aware(rate, pess, opt):
    t = pd.Timestamp("2024-01-01 08:00", tz="UTC")
    settlements = pd.DataFrame({"time": [t], "rate": [rate]})
    entry = t - pd.Timedelta(hours=1)
    assert funding.trade_funding(1, entry, t, settlements, "PESS") == pytest.approx((0, pess))
    assert funding.trade_funding(1, entry, t, settlements, "OPT") == pytest.approx((0, opt))


def test_r26_cost_convention_round_trip():
    value = 12.345
    cashflow = funding.to_cashflow_bps(value, "R2_6_COST")
    assert cashflow == pytest.approx(-value)
    assert funding.from_cashflow_bps(cashflow, "R2_6_COST") == pytest.approx(value)
    assert funding.from_cashflow_bps(
        funding.to_cashflow_bps(value, "R2_14_CASHFLOW"), "R2_14_CASHFLOW") == pytest.approx(value)


def test_vector_trade_funding_matches_scalar():
    times = pd.to_datetime(["2024-01-01 00:00", "2024-01-01 08:00",
                            "2024-01-01 16:00"], utc=True)
    settlements = pd.DataFrame({"time": times, "rate": [0.0001, -0.0002, 0.0003]})
    sides = [1, -1]
    entries = [times[0], times[0] + pd.Timedelta(hours=1)]
    exits = [times[2], times[1]]
    for boundary in funding.BOUNDARIES:
        internal, edge, _ = funding.trade_funding_frame(
            sides, entries, exits, settlements, boundary)
        scalar = [funding.trade_funding(side, entry, exit_, settlements, boundary)
                  for side, entry, exit_ in zip(sides, entries, exits)]
        assert list(zip(internal, edge)) == pytest.approx(scalar)
