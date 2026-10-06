"""Paper broker and deliberately unavailable live broker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Fill:
    time: object
    side: int
    price: float
    quantity: float = 1.0


class Broker(Protocol):
    def fill(self, time: object, side: int, price: float) -> Fill: ...


class PaperBroker:
    """Deterministic next-open fill recorder with no network capability."""

    network_enabled = False

    def fill(self, time: object, side: int, price: float) -> Fill:
        if side not in {-1, 1} or price <= 0:
            raise ValueError("invalid paper fill")
        return Fill(time, side, float(price))


class LiveBroker:
    network_enabled = False

    def __init__(self, *_: object, **__: object) -> None:
        raise RuntimeError("live mode is disabled: no authenticated calls or orders are implemented")


__all__ = ["Broker", "Fill", "LiveBroker", "PaperBroker"]

