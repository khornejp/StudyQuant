from __future__ import annotations

def fill_stop(side: int, level: float, o: float, h: float, l: float) -> float | None:
    if side == 1:
        return o if o >= level else (level if h >= level else None)
    return o if o <= level else (level if l <= level else None)

def fill_limit(side: int, level: float, o: float, h: float, l: float) -> float | None:
    if side == 1:
        return o if o <= level else (level if l < level else None)
    return o if o >= level else (level if h > level else None)

def fill_oco(upper: float, lower: float, o: float, h: float, l: float) -> tuple[int, float] | None:
    up, down = fill_stop(1, upper, o, h, l), fill_stop(-1, lower, o, h, l)
    if up is not None and down is not None:
        return (1, up) if abs(upper - o) < abs(o - lower) else (-1, down)
    if up is not None:
        return 1, up
    if down is not None:
        return -1, down
    return None

def exit_touch(side: int, stop: float, take: float, o: float, h: float, l: float) -> tuple[str, float] | None:
    stop_price = fill_stop(-side, stop, o, h, l)
    if stop_price is not None:
        return "stop", stop_price
    take_price = fill_limit(-side, take, o, h, l)
    return ("take", take_price) if take_price is not None else None
