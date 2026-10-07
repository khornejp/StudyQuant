from btcusdt_quant.sim import orders

def test_stop_gap_fills_at_open():
    assert orders.fill_stop(1, 100, o=105, h=106, l=104) == 105
    assert orders.fill_stop(-1, 100, o=95, h=96, l=94) == 95

def test_stop_touch_fills_at_level():
    assert orders.fill_stop(1, 100, o=99, h=101, l=98) == 100
    assert orders.fill_stop(1, 100, o=99, h=99.9, l=98) is None

def test_limit_needs_trade_through():
    assert orders.fill_limit(1, 100, o=101, h=102, l=99.9) == 100
    assert orders.fill_limit(1, 100, o=101, h=102, l=100) is None   # touch only
    assert orders.fill_limit(1, 100, o=99, h=100, l=98) == 99          # opens below: fill at open

def test_oco_both_touched_prefers_nearer_open():
    assert orders.fill_oco(upper=101, lower=95, o=100, h=102, l=94) == (1, 101)

def test_stop_wins_same_minute():
    assert orders.exit_touch(1, stop=99, take=103, o=100, h=104, l=98) == ("stop", 99)
    assert orders.exit_touch(-1, stop=101, take=97, o=100, h=102, l=96) == ("stop", 101)

def test_exit_gap_through_stop_at_open():
    assert orders.exit_touch(1, stop=99, take=103, o=97, h=98, l=96) == ("stop", 97)

def test_stop_exact_touch_fills_at_level():
    assert orders.fill_stop(1, 100, o=99, h=100, l=98) == 100
    assert orders.fill_stop(-1, 100, o=101, h=102, l=100) == 100

def test_limit_open_at_level_fills_and_short_needs_trade_through():
    assert orders.fill_limit(1, 100, o=100, h=101, l=100) == 100
    assert orders.fill_limit(-1, 100, o=100, h=100, l=99) == 100
    assert orders.fill_limit(-1, 100, o=99, h=100, l=98) is None      # touch only
    assert orders.fill_limit(-1, 100, o=99, h=100.1, l=98) == 100
    assert orders.fill_limit(-1, 100, o=101, h=102, l=100.5) == 101   # opens above: fill at open

def test_oco_lower_nearer_and_tie_go_short():
    assert orders.fill_oco(upper=105, lower=99, o=100, h=106, l=98) == (-1, 99)
    assert orders.fill_oco(upper=101, lower=99, o=100, h=102, l=98) == (-1, 99)
