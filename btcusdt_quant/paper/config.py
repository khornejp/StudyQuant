"""TOML configuration and local credential slots for paper trading."""

from __future__ import annotations

import hashlib
import os
import tomllib
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from btcusdt_quant.secrets import mask_secret


@dataclass(frozen=True)
class PaperConfig:
    mode: str = "paper"
    symbol: str = "BTCUSDT"
    books: tuple[str, ...] = ("C1", "F3", "E1", "C4")
    book_start_times: dict[str, str] = field(default_factory=dict)
    comparison_books: tuple[str, ...] = ()
    leverage_books: tuple[str, ...] | None = None
    primary_book: str = "C1"
    start_time: str = "2026-10-01T00:00:00Z"
    cost_bps: float = 4.0
    leverage: float = 3.0
    budget_usd: float = 100.0
    maintenance_margin_rate: float = 0.004
    liquidation_fee_rate: float = 0.0
    sqlite_path: str = "artifacts/live/live.sqlite"
    data_root: str = "artifacts/live"
    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = 8765
    telegram_entry: bool = True
    telegram_exit: bool = True
    telegram_dropped_signal: bool = False
    telegram_daily_summary: bool = True
    telegram_alert: bool = True
    telegram_retry_base_seconds: float = 5.0
    telegram_retry_max_seconds: float = 300.0
    telegram_books: tuple[str, ...] | None = None   # None = every book; catalog books stay off Telegram
    retired_books: tuple[str, ...] = ()     # R2-52A switch snapshot: rows kept as the record, never processed again
    alert_collector_lag_seconds: float = 10.0
    alert_gap_minutes: int = 1
    alert_disk_free_ratio: float = 0.10
    book_ticker_enabled: bool = True
    book_ticker_raw_ticks: bool = False
    websocket_reconnect_max_seconds: float = 60.0

    def __post_init__(self) -> None:
        if self.mode not in {"paper", "live"}:
            raise ValueError("mode must be paper or live")
        if self.symbol != "BTCUSDT":
            raise ValueError("v1 supports BTCUSDT only")
        if self.primary_book not in self.books:
            raise ValueError("primary_book must be enabled")
        if set(self.book_start_times) - set(self.books):
            raise ValueError("book_start_times keys must be enabled books")
        if set(self.comparison_books) - set(self.books) or self.primary_book in self.comparison_books:
            raise ValueError("comparison_books must be enabled non-primary books")
        if self.leverage_books is not None and set(self.leverage_books) - set(self.books):
            raise ValueError("leverage_books must be enabled books")
        if set(self.retired_books) & (set(self.books) | {f"{name}_x3" for name in self.leverage_books or ()}):
            raise ValueError("retired_books must not be active")
        for value in (self.start_time, *self.book_start_times.values()):
            stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                raise ValueError("book start times must be timezone-aware")
        if self.dashboard_host != "127.0.0.1":
            raise ValueError("dashboard_host must be 127.0.0.1")
        if self.cost_bps != 4.0:
            raise ValueError("frozen round-trip cost is 4 bps")
        if self.leverage != 3.0 or self.budget_usd != 100.0:
            raise ValueError("frozen leverage book is 3x with $100 budget")
        if self.maintenance_margin_rate != .004 or self.liquidation_fee_rate != 0.0:
            raise ValueError("frozen liquidation settings changed")
        if self.telegram_retry_base_seconds <= 0 or self.telegram_retry_max_seconds <= 0:
            raise ValueError("telegram retry seconds must be positive")
        if not 0 < self.alert_disk_free_ratio < 1:
            raise ValueError("alert_disk_free_ratio must be between 0 and 1")

    @property
    def hash(self) -> str:
        return hashlib.sha256(repr(sorted(asdict(self).items())).encode()).hexdigest()


def load_config(path: str | Path = "config/paper.toml") -> PaperConfig:
    with Path(path).open("rb") as handle:
        payload = tomllib.load(handle)
    values = payload.get("paper", payload)
    if "books" in values:
        values["books"] = tuple(values["books"])
    for name in ("comparison_books", "leverage_books", "telegram_books", "retired_books"):
        if name in values:
            values[name] = tuple(values[name])
    config = PaperConfig(**values)
    if config.mode == "live":
        raise RuntimeError("live mode is disabled: LiveBroker is not implemented")
    return config


def load_env_slots(path: str | Path = ".env") -> dict[str, str]:
    """Load only named secret slots into process memory; never log raw values."""
    values = {"BINANCE_API_KEY": "", "BINANCE_API_SECRET": "",
              "TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}
    env_path = Path(path)
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key in values:
                values[key] = value.strip().strip("'\"")
    for key in values:
        values[key] = os.environ.get(key, values[key])
    return values


def credential_status(path: str | Path = ".env") -> dict[str, object]:
    values = load_env_slots(path)
    return {"loaded": bool(values["BINANCE_API_KEY"] and values["BINANCE_API_SECRET"]),
            "api_key": mask_secret(values["BINANCE_API_KEY"]),
            "api_secret": mask_secret(values["BINANCE_API_SECRET"])}


def telegram_status(path: str | Path = ".env") -> dict[str, object]:
    values = load_env_slots(path)
    token = values["TELEGRAM_BOT_TOKEN"]
    configured = bool(token and values["TELEGRAM_CHAT_ID"])
    label = (f"텔레그램: 설정됨 ({mask_secret(token)})" if configured else
             "텔레그램: 미설정")
    return {"configured": configured, "token": mask_secret(token), "label": label}


__all__ = ["PaperConfig", "credential_status", "load_config", "load_env_slots",
           "telegram_status"]
