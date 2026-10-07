from pathlib import Path


def test_sim_package_and_tools_import():
    import numba, hypothesis  # noqa: F401
    import btcusdt_quant.sim as sim
    import btcusdt_quant.backtest as legacy  # noqa: F401  legacy API still importable
    assert sim.__name__ == "btcusdt_quant.sim"
    assert (Path(sim.__file__).parents[1] / "backtest.py").is_file()
