from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ExchangeCredentials:
    api_key: str
    api_secret: str

    def masked(self) -> dict[str, str]:
        return {
            "api_key": mask_secret(self.api_key),
            "api_secret": mask_secret(self.api_secret),
        }


def load_binance_credentials_from_env() -> ExchangeCredentials:
    api_key = os.environ.get("BINANCE_API_KEY", "")
    api_secret = os.environ.get("BINANCE_API_SECRET", "")
    if not api_key or not api_secret:
        raise RuntimeError("BINANCE_API_KEY and BINANCE_API_SECRET are required")
    return ExchangeCredentials(api_key=api_key, api_secret=api_secret)


def mask_secret(value: str, visible: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= visible * 2:
        return "*" * len(value)
    return f"{value[:visible]}...{value[-visible:]}"
