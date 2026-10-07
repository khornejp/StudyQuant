"""Result guard (spec D2): reject reports with silent zero-trade strategies, label-only diagnostics, unexplained NaN."""
from __future__ import annotations
import math


def _nan_without_reason(obj, path: str, problems: list[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, float) and math.isnan(v) and f"{k}_reason" not in obj and "reason" not in obj:
                problems.append(f"{path}.{k}: NaN without reason")
            else:
                _nan_without_reason(v, f"{path}.{k}", problems)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _nan_without_reason(v, f"{path}[{i}]", problems)


def check(report: dict) -> None:
    problems = []
    for name, value in report.get("diagnostics", {}).items():
        if isinstance(value, str):
            problems.append(f"diagnostic {name} is a bare label {value!r}, not a computed value")
    for strategy in report.get("strategies", []):
        if strategy.get("trade_n") == 0 and not strategy.get("zero_reason"):
            problems.append(f"strategy {strategy.get('id')} has zero trades without zero_reason")
    _nan_without_reason(report, "report", problems)
    if problems:
        raise ValueError("result guard: " + "; ".join(problems))
