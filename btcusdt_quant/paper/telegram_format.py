"""Telegram message layout for the paper books (user format 2026-10-07).

Paper books trade one unit; one unit is shown as a 100 USDT notional so bps and USDT read together.
Exit reasons carry a code (TIME_EXIT, SIGNAL_EXIT, SL, TP1, SL_BE, DATA_END, LIQUIDATION).
"""
from __future__ import annotations
from typing import Mapping
import pandas as pd

UNIT_NOTIONAL_USDT = 100.0
CANDIDATE_NAMES = {"F3|1h|10/24|signal|LS": "F3 역추세 1시간", "F3|5m|10/24|signal|LS": "F3 역추세 5분",
                   "F3_global_ls_account|1h|w30|q20|h12|LS": "F3-w30 역추세", "E1|1h|3|signal|L": "E1 거래량 돌파"}
REASONS = {"MAX_HOLD_OR_REVERSE": ("최대 보유 또는 반대 신호", "TIME_EXIT/SIGNAL_EXIT"),
           "MAX_HOLD": ("최대 보유 시간 도달", "TIME_EXIT"), "REVERSE": ("반대 신호", "SIGNAL_EXIT"),
           "FLAG": ("청산 조건 충족", "SIGNAL_EXIT"), "STOP": ("손절 기준가 도달", "SL"),
           "TAKE": ("1차 익절 (절반)", "TP1"), "BREAKEVEN": ("본전 손절", "SL_BE"),
           "TRAIL": ("추적 손절", "TRAILING_STOP"),
           "DATA_END": ("데이터 끝", "DATA_END"), "REPLAY_END": ("데이터 끝", "DATA_END"),
           "liquidation": ("모의 강제청산", "LIQUIDATION")}


def _usdt(bps: object) -> float:
    return float(bps) / 1e4 * UNIT_NOTIONAL_USDT


def _money(bps: object) -> str:
    return f"{_usdt(bps):+,.2f} USDT ({float(bps):+.1f} bps)"


def _side(value: object) -> str:
    return "LONG" if int(value) > 0 else "SHORT"


def _kst(value: object, seconds: bool = False) -> str:
    try:
        stamp = pd.Timestamp(value)
    except (ValueError, TypeError):
        return str(value)
    if pd.isna(stamp):
        return "-"
    stamp = stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp
    return stamp.tz_convert("Asia/Seoul").strftime("%m/%d %H:%M:%S" if seconds else "%m/%d %H:%M") + " KST"


def _hold(minutes: object) -> str:
    total = int(float(minutes))
    return f"{total // 60}시간 {total % 60}분" if total >= 60 else f"{total}분"


def _reason(value: object) -> str:
    parts = [REASONS.get(p, (p, p)) for p in str(value).split("+")]
    return " + ".join(t for t, _ in parts) + " [" + "+".join(c for _, c in parts) + "]"


def _technique(value: object) -> str:
    from . import catalog
    text = str(value)
    if text in CANDIDATE_NAMES:
        return CANDIDATE_NAMES[text]
    return catalog.label(text) if text in catalog.BOOKS else text


def _trade_id(book: object, entry_time: object) -> str:
    try:
        stamp = pd.Timestamp(entry_time)
        stamp = stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp
        return f"{book}-{stamp.tz_convert('Asia/Seoul'):%m%d-%H%M}"
    except (ValueError, TypeError):
        return str(book)


def _btc(price: object, units: float = 1.0) -> str:
    return f"{units * UNIT_NOTIONAL_USDT / float(price):.5f} BTC"


def _given(event: Mapping[str, object], key: str) -> bool:
    value = event.get(key)
    return value is not None and not (isinstance(value, float) and pd.isna(value)) and value != ""


def entry_message(event: Mapping[str, object]) -> str:
    lines = [f"🟢 [모의 진입 체결] BTCUSDT · {event['book']}", "",
             f"기법 : {_technique(event.get('candidate', event['book']))}",
             f"방향 : {_side(event['side'])}",
             f"평균 진입가 : {float(event['price']):,.2f} USDT"]
    if "notional_usd" in event:
        lines += [f"진입 금액 : {float(event['notional_usd']):,.2f} USDT",
                  f"증거금 : {float(event['margin_usd']):,.2f} USDT (x3, 격리)",
                  f"청산가 : {float(event['liquidation_price']):,.2f}",
                  f"잔고 : {float(event['balance_usd']):,.2f} USDT"]
    else:
        lines += [f"체결 수량 : {_btc(event['price'])}",
                  f"진입 금액 : {UNIT_NOTIONAL_USDT:,.2f} USDT (1단위)",
                  "체결 상태 : 전량 체결"]
        if _given(event, "exit_time"):
            lines += ["", f"최대 보유 끝 : {_kst(event['exit_time'])}"]
    lines += [""]
    if _given(event, "entry_time"):
        lines.append(f"체결 시각 : {_kst(event['entry_time'])}")
    lines.append(f"거래 ID : {_trade_id(event['book'], event.get('entry_time'))}")
    return "\n".join(lines)


def exit_message(event: Mapping[str, object]) -> str:
    if "pnl_usd" in event:                                       # x3 overlay books (USD fields)
        lines = [("✅" if float(event["pnl_usd"]) >= 0 else "❌") + f" [모의 포지션 종료] BTCUSDT · {event['book']}", "",
                 f"순실현손익 : {float(event['pnl_usd']):+,.2f} USDT", "",
                 f"종료가 : {float(event['price']):,.2f}",
                 f"진입 명목 : {float(event['notional_usd']):,.2f} USDT · 증거금 {float(event['margin_usd']):,.2f} USDT",
                 f"잔고 : {float(event['balance_usd']):,.2f} USDT",
                 f"종료 근거 : {_reason(event['reason'])}"]
        return "\n".join(lines)
    # bps fields are per 1 unit; units < 1 marks a DETEXIT leg, so the rate is shown on that leg's own notional.
    net, units = float(event["net_bps"]), float(event.get("units", 1.0))
    partial = str(event["reason"]) == "TAKE"
    entry = float(event.get("entry_price", event["price"]))
    title = "🟡 [모의 부분 종료]" if partial else ("✅" if net >= 0 else "❌") + " [모의 포지션 종료]"
    lines = [f"{title} BTCUSDT · {event['book']}", "",
             f"{'이번 종료 순손익' if partial else '순실현손익'} : {_usdt(net):+,.2f} USDT",
             f"순손익률 : {net / units:+.1f} bps", ""]
    if _given(event, "candidate"):
        lines.append(f"기법 : {_technique(event['candidate'])}")
    if "side" in event:
        lines.append(f"방향 : {_side(event['side'])}")
    lines += [f"평균 진입가 : {entry:,.2f}",
              f"평균 종료가 : {float(event['price']):,.2f}",
              f"{'이번 종료 수량' if partial else '종료 수량'} : {_btc(entry, units)}",
              f"잔여 수량 : {_btc(entry, units) + ' (보유 중)' if partial else '0 BTC'}",
              f"보유 시간 : {_hold(event['hold_minutes'])}", "",
              f"매매손익 : {_usdt(event['gross_bps']):+,.2f} USDT",
              f"진입·종료 수수료 : {_usdt(-float(event['cost_bps'])):+,.2f} USDT",
              f"펀딩 순수취액 : {_usdt(event['funding_bps']):+,.2f} USDT", "",
              f"종료 근거 : {_reason(event['reason'])}",
              f"누적 실현 순손익 : {_money(event['cumulative_net_bps'])} (장부 전체)", ""]
    if _given(event, "exit_time"):
        lines.append(f"종료 시각 : {_kst(event['exit_time'])}")
    if _given(event, "entry_time"):
        lines.append(f"거래 ID : {_trade_id(event['book'], event['entry_time'])}")
    return "\n".join(lines).strip()


def liquidation_message(event: Mapping[str, object]) -> str:
    return "\n".join([f"🚨 [모의 강제청산] BTCUSDT · {event['book']}", "",
                      f"청산 체결가 : {float(event['price']):,.2f} (모의, 청산가 기준)",
                      f"청산가 : {float(event['liquidation_price']):,.2f}",
                      f"순실현손익 : {float(event['pnl_usd']):+,.2f} USDT",
                      "청산 상태 : 전체 · 잔고 0.00 USDT",
                      "이벤트 구분 : LIQUIDATION (모의 장부, 거래소 이벤트 아님)"])


def daily_message(event: Mapping[str, object]) -> str:
    rows = sorted(event.get("rows", []), key=lambda r: float(r["day_net_bps"]), reverse=True)
    total = sum(float(r["day_net_bps"]) for r in rows)
    trades = sum(int(r["trades"]) for r in rows)
    wins, longs = (sum(int(r.get(k, 0)) for r in rows) for k in ("wins", "longs"))
    pct = lambda a, b: "—" if not b else f"{100 * a / b:.1f}%"
    avg = lambda net, n: "—" if not n else f"{float(net) / n:+.1f} bps"
    lines = ["📊 [모의 일일 거래 요약]", "", f"대상일 : {event['date']} (UTC 00:00~24:00)",
             "집계 : 당일 종료 거래", "정렬 : 순손익 USDT 내림차순", f"단위 : 1단위 = {UNIT_NOTIONAL_USDT:,.0f} USDT",
             f"BTC 보유 비교 : {_money(event['buy_hold_bps'])}", "",
             "[전체 성과]", f"순손익 : {_usdt(total):+,.2f} USDT", f"평균 순손익 : {avg(total, trades)}",
             f"완료 거래 : {trades}회", f"승률 : {pct(wins, trades)}",
             f"롱 / 숏 : {longs}회 / {trades - longs}회", "", "[장부별 성과]", ""]
    for k, r in enumerate(rows, 1):
        n, w, lg = int(r["trades"]), int(r.get("wins", 0)), int(r.get("longs", 0))
        lines += [f"{k}. {r['book']}",
                  f"순손익 : {_usdt(r['day_net_bps']):+,.2f} USDT · 누적 {_usdt(r['total_net_bps']):+,.2f} USDT",
                  f"평균 순손익 : {avg(r['day_net_bps'], n)}",
                  f"거래 : {n}회 | 승률 : {pct(w, n)}",
                  f"롱 {lg} / 숏 {n - lg} | {pct(lg, n)} / {pct(n - lg, n)}" if n else "롱 / 숏 : —", ""]
    if "open_positions" in event:
        lines += ["[현재 보유]", f"미종료 거래 : {int(event['open_positions'])}건",
                  f"평가손익 : {_usdt(event['open_unrealized_bps']):+,.2f} USDT"]
    return "\n".join(lines).strip()


def format_message(event_type: str, event: Mapping[str, object]) -> str:
    if event_type == "entry":
        return entry_message(event)
    if event_type == "exit":
        return exit_message(event)
    if event_type == "liquidation":
        return liquidation_message(event)
    if event_type == "distance_warning":
        return "\n".join([f"⚠️ [모의 청산 경고] BTCUSDT · {event['book']}", "",
                          f"청산가까지 거리 : {float(event['distance_pct']):.2f}%",
                          f"현재가 : {float(event['price']):,.2f} · 청산가 {float(event['liquidation_price']):,.2f}"])
    if event_type == "dropped_signal":
        return "\n".join([f"⚪ [버린 신호] {event['book']} · {_side(event['side'])}",
                          f"{_technique(event['candidate'])} · {event.get('reason') or '-'}",
                          f"{_kst(event['entry_time'])}"])
    if event_type == "daily_summary":
        return daily_message(event)
    if event_type == "alert":
        return f"🚧 [장애] {event['kind']}\n{event['detail']}"
    if event_type == "connection_test":
        return str(event["text"])
    raise ValueError(f"unknown notification event: {event_type}")


def split_message(text: str, limit: int = 4000) -> list[str]:
    """Telegram sendMessage allows 4096 characters; split on blank lines."""
    if len(text) <= limit:
        return [text]
    parts, current = [], ""
    for block in text.split("\n\n"):
        candidate = block if not current else current + "\n\n" + block
        if len(candidate) > limit and current:
            parts.append(current); current = block
        else:
            current = candidate
    parts.append(current)
    return [p[:limit] for p in parts]
