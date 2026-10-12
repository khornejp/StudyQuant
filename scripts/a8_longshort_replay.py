"""A8 R2 월 평가를 같은 checkpoint/RNG로 재생해 long/short 성과를 분해한다."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import gc
import hashlib
import io
import json
import os
from pathlib import Path
import sys

os.environ.setdefault("NUMBA_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import numba
import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from btcusdt_quant.rl import a8_ga_rl as A8  # noqa: E402
from btcusdt_quant.rl import a8_selection as SEL  # noqa: E402
from btcusdt_quant.rl import maker_kernel as MK  # noqa: E402
from btcusdt_quant.rl import smdp_reward as RW  # noqa: E402

DEFAULT_RUN = ROOT / "out/rl_allocator_20261010/smdp_a8/a8_ga_selection_r2_20261012"
DEFAULT_OUT = ROOT / "out/rl_allocator_20261010/smdp_a8/longshort_r2"
TOLERANCE = 1e-6
SIDES = ("short", "long")
REASONS = (("cap", MK.EXIT_CAP), ("SL", MK.EXIT_SL), ("TP", MK.EXIT_TP), ("RL", MK.EXIT_RL))
FROZEN_HYPOTHESIS = (
    "GA selection 월 평가의 원본 모델, evaluator state, RNG, cell을 그대로 재생하고 "
    "진입 후 포지션 부호로 long/short 성과만 분해한다. 정책, 액션, 체결은 변경하지 않는다."
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


@numba.njit(cache=False)
def _shadow_advance(o, h, l, c, t, frate, ST, gi, tgt, wait, endx, off, pen, jout, sl_mult, tp_mult, rv_dec,
                    cap_penalty_bps, tp_profit_reward, loss_penalty, net4, entries, round_trips, reason_count,
                    reason_pnl, hold_sum, abs_position_sum, position_minutes, flat_net4):
    """maker kernel과 같은 minute 순서로 state를 재생하며 방향 통계만 추가한다."""
    for e in range(ST.shape[0]):
        st = ST[e]
        i = gi[e]
        n = endx[e]
        requested_wait = wait[e]
        effective_wait = requested_wait
        if abs(st[MK.S_U]) > MK.EPS and st[MK.S_OPENK] >= 0:
            age = i - int(st[MK.S_OPENK]) + 1
            effective_wait = min(effective_wait, max(MK.CAP_MIN - age, 1))
        j = min(i + effective_wait, n - 1)
        jout[e] = i
        if st[MK.S_FAULT] > 0:
            continue
        if st[MK.S_KILL] > 0:
            st[MK.S_FAULT], st[MK.S_FAULTK], st[MK.S_FAULTCODE] = 1.0, i + 1, 5.0
            st[MK.S_KILLCOUNT] += 1
            continue
        st[MK.S_EVENT], st[MK.S_EVENTK], st[MK.S_CAPFLAG], st[MK.S_CURTGT] = 0.0, float(i), 0.0, tgt[e]
        sigma = rv_dec[e] * np.sqrt(requested_wait / MK.CAP_MIN)
        st[MK.S_SL_MULT], st[MK.S_TP_MULT] = sl_mult[e], tp_mult[e]
        st[MK.S_SL_BPS], st[MK.S_TP_BPS] = sl_mult[e] * sigma, tp_mult[e] * sigma
        st[MK.S_LASTWAIT] = requested_wait
        if st[MK.S_REENTRYAWAIT] > 0:
            if abs(tgt[e]) > MK.EPS and st[MK.S_REENTRYACTIVE] == 0:
                st[MK.S_REENTRYREQ] += 1
                st[MK.S_REENTRYACTIVE] = 1.0
            elif abs(tgt[e]) <= MK.EPS:
                st[MK.S_REENTRYAWAIT], st[MK.S_REENTRYACTIVE] = 0.0, 0.0
        if st[MK.S_PEND] > 0:
            if abs(st[MK.S_PTGT] - tgt[e]) > MK.EPS:
                st[MK.S_PEND] = 0.0
                MK._place(st, c, tgt[e], i + 2, off[e], n)
        else:
            MK._place(st, c, tgt[e], i + 1, off[e], n)
        last = i
        for k in range(i + 1, j + 1):
            code = MK._fault_at(o, h, l, c, t, k)
            if code > 0:
                st[MK.S_FAULT], st[MK.S_FAULTK], st[MK.S_FAULTCODE] = 1.0, k, code
                st[MK.S_KILLCOUNT] += 1
                break
            u0 = st[MK.S_U]
            open_k = st[MK.S_OPENK]
            pnl0 = np.empty(5, np.float64)
            pnl0[MK.EXIT_RL] = st[MK.S_RLPNL]
            pnl0[MK.EXIT_SL] = st[MK.S_SLPNL]
            pnl0[MK.EXIT_TP] = st[MK.S_TPPNL]
            pnl0[MK.EXIT_CAP] = st[MK.S_CAPPNL]
            value, _ = MK._minute(o, h, l, c, frate, st, k, off[e], pen[e], n, cap_penalty_bps,
                                  tp_profit_reward, loss_penalty)
            u1 = st[MK.S_U]
            direction = -1
            if abs(u0) > MK.EPS:
                direction = 0 if u0 < 0 else 1
            elif abs(u1) > MK.EPS:
                direction = 0 if u1 < 0 else 1
            if direction >= 0:
                net4[e, direction] += value
            else:
                flat_net4[e] += value
            if abs(u0) <= MK.EPS and abs(u1) > MK.EPS:
                entries[e, 0 if u1 < 0 else 1] += 1
            if abs(u0) > MK.EPS and abs(u1) <= MK.EPS:
                direction = 0 if u0 < 0 else 1
                reason = int(st[MK.S_EVENT])
                round_trips[e, direction] += 1
                reason_count[e, direction, reason] += 1
                if reason == MK.EXIT_RL:
                    reason_pnl[e, direction, reason] += st[MK.S_RLPNL] - pnl0[reason]
                elif reason == MK.EXIT_SL:
                    reason_pnl[e, direction, reason] += st[MK.S_SLPNL] - pnl0[reason]
                elif reason == MK.EXIT_TP:
                    reason_pnl[e, direction, reason] += st[MK.S_TPPNL] - pnl0[reason]
                elif reason == MK.EXIT_CAP:
                    reason_pnl[e, direction, reason] += st[MK.S_CAPPNL] - pnl0[reason]
                hold_sum[e, direction] += k - int(open_k) + 1
            if abs(u1) > MK.EPS:
                direction = 0 if u1 < 0 else 1
                abs_position_sum[e, direction] += abs(u1)
                position_minutes[e, direction] += 1
            last = k
            if st[MK.S_EVENT] in (MK.EXIT_SL, MK.EXIT_TP, MK.EXIT_CAP):
                break
        jout[e] = last


class ReplayEnv(A8.A8BatchEnv):
    def reset_direction_stats(self) -> None:
        shape = (self.E, 2)
        self.direction_net4 = np.zeros(shape, np.float64)
        self.direction_entries = np.zeros(shape, np.int64)
        self.direction_round_trips = np.zeros(shape, np.int64)
        self.direction_reason_count = np.zeros((self.E, 2, 5), np.int64)
        self.direction_reason_pnl = np.zeros((self.E, 2, 5), np.float64)
        self.direction_hold_sum = np.zeros(shape, np.float64)
        self.direction_abs_position_sum = np.zeros(shape, np.float64)
        self.direction_position_minutes = np.zeros(shape, np.int64)
        self.direction_flat_net4 = np.zeros(self.E, np.float64)
        self.shadow_max_error = 0.0

    def step(self, a_t: np.ndarray, a_w: np.ndarray, a_sl=None, a_tp=None) -> dict:
        target = self.targets[a_t]
        wait = self.waits[a_w]
        a_sl = np.zeros(self.E, np.int64) if a_sl is None else np.asarray(a_sl, np.int64)
        a_tp = np.zeros(self.E, np.int64) if a_tp is None else np.asarray(a_tp, np.int64)
        shadow_state = self.ST.copy()
        shadow_jout = np.zeros(self.E, np.int64)
        _shadow_advance(self.o, self.h, self.l, self.c, self.t, self.frate, shadow_state, self.gi.copy(), target,
                        wait, self.endx, self.off, self.pen, shadow_jout, self.sl_grid[a_sl], self.tp_grid[a_tp],
                        self.rv[self.gi], self.cfg.cap_penalty_bps, self.cfg.tp_profit_reward, self.cfg.loss_penalty,
                        self.direction_net4, self.direction_entries, self.direction_round_trips,
                        self.direction_reason_count, self.direction_reason_pnl, self.direction_hold_sum,
                        self.direction_abs_position_sum, self.direction_position_minutes, self.direction_flat_net4)
        result = super().step(a_t, a_w, a_sl, a_tp)
        state_error = float(np.max(np.abs(shadow_state - self.ST)))
        self.shadow_max_error = max(self.shadow_max_error, state_error)
        if state_error > 1e-10 or not np.array_equal(shadow_jout, self.gi):
            raise RuntimeError(f"shadow replay mismatch: state={state_error:.3e}, index={not np.array_equal(shadow_jout, self.gi)}")
        return result


def _make_evaluator(market, features, genome, rv_median, seed: int, start_ns: int, end_ns: int):
    original = A8.A8BatchEnv
    A8.A8BatchEnv = ReplayEnv
    try:
        evaluator = A8.A8Evaluator(market, features, genome.reward_config(), rv_median, SEL.CELLS,
                                   start_ns, end_ns, seed + 100_000, device="cuda")
    finally:
        A8.A8BatchEnv = original
    evaluator.env.reset_direction_stats()
    return evaluator


def _side_record(env: ReplayEnv, cell: int, direction: int) -> dict:
    round_trips = int(env.direction_round_trips[cell, direction])
    position_minutes = int(env.direction_position_minutes[cell, direction])
    reasons = {
        name: {"count": int(env.direction_reason_count[cell, direction, code]),
               "pnl": float(env.direction_reason_pnl[cell, direction, code])}
        for name, code in REASONS
    }
    return {
        "entries": int(env.direction_entries[cell, direction]),
        "round_trips": round_trips,
        "net4": float(env.direction_net4[cell, direction]),
        "exits": reasons,
        "avg_hold_min": (float(env.direction_hold_sum[cell, direction] / round_trips) if round_trips else None),
        "holding_minutes_sum": float(env.direction_hold_sum[cell, direction]),
        "avg_abs_position": (float(env.direction_abs_position_sum[cell, direction] / position_minutes)
                             if position_minutes else None),
        "abs_position_minute_sum": float(env.direction_abs_position_sum[cell, direction]),
        "position_minutes": position_minutes,
    }


def _aggregate(cells: dict, side: str) -> dict:
    records = [cell[side] for cell in cells.values()]
    round_trips = sum(record["round_trips"] for record in records)
    position_minutes = sum(record["position_minutes"] for record in records)
    hold_sum = sum(record["holding_minutes_sum"] for record in records)
    abs_sum = sum(record["abs_position_minute_sum"] for record in records)
    return {
        "entries": sum(record["entries"] for record in records),
        "round_trips": round_trips,
        "net4": sum(record["net4"] for record in records),
        "exits": {name: {"count": sum(record["exits"][name]["count"] for record in records),
                          "pnl": sum(record["exits"][name]["pnl"] for record in records)}
                  for name, _ in REASONS},
        "avg_hold_min": hold_sum / round_trips if round_trips else None,
        "holding_minutes_sum": hold_sum,
        "avg_abs_position": abs_sum / position_minutes if position_minutes else None,
        "abs_position_minute_sum": abs_sum,
        "position_minutes": position_minutes,
    }


def _validated_record(raw: dict, source: dict, env: ReplayEnv, metadata: dict) -> dict:
    errors = []
    checks = (("net4", "net4"), ("round_trips", "round_trips"), ("sl_count", "sl_count"),
              ("tp_count", "tp_count"), ("renewal_count", "renewal_count"), ("rl_count", "rl_count"),
              ("sl_pnl", "sl_pnl"), ("tp_pnl", "tp_pnl"), ("cap_pnl", "cap_pnl"),
              ("rl_exit_pnl", "rl_exit_pnl"))
    cells = {}
    for cell_index, cell_name in enumerate(SEL.CELL_NAMES):
        for raw_key, source_key in checks:
            error = abs(float(raw[raw_key][cell_index]) - float(source["cells"][cell_name][source_key]))
            errors.append((f"{cell_name}.{raw_key}.source", error))
        cell = {side: _side_record(env, cell_index, direction) for direction, side in enumerate(SIDES)}
        cells[cell_name] = cell
        errors.append((f"{cell_name}.net4.split",
                       abs(sum(cell[side]["net4"] for side in SIDES) - float(raw["net4"][cell_index]))))
        errors.append((f"{cell_name}.round_trips.split",
                       abs(sum(cell[side]["round_trips"] for side in SIDES)
                           - float(raw["round_trips"][cell_index]))))
        for name, code in REASONS:
            raw_count = (raw["renewal_count"] if code == MK.EXIT_CAP else raw["sl_count"] if code == MK.EXIT_SL
                         else raw["tp_count"] if code == MK.EXIT_TP else raw["rl_count"])
            raw_pnl = (raw["cap_pnl"] if code == MK.EXIT_CAP else raw["sl_pnl"] if code == MK.EXIT_SL
                       else raw["tp_pnl"] if code == MK.EXIT_TP else raw["rl_exit_pnl"])
            errors.append((f"{cell_name}.{name}_count.split",
                           abs(sum(cell[side]["exits"][name]["count"] for side in SIDES)
                               - float(raw_count[cell_index]))))
            errors.append((f"{cell_name}.{name}_pnl.split",
                           abs(sum(cell[side]["exits"][name]["pnl"] for side in SIDES)
                               - float(raw_pnl[cell_index]))))
        errors.append((f"{cell_name}.flat_net4", abs(float(env.direction_flat_net4[cell_index]))))
    errors.extend((("faults", abs(float(raw["faults"]))),
                   ("identity_error", max(0.0, float(raw["identity_error"]) - 1e-8)),
                   ("shadow_state", float(env.shadow_max_error))))
    worst_name, worst_error = max(errors, key=lambda item: item[1])
    if worst_error > TOLERANCE:
        raise RuntimeError(f"검증 실패: {worst_name} error={worst_error:.12g}; 결과 저장 금지")
    summary = {side: _aggregate(cells, side) for side in SIDES}
    return {
        "schema_version": 1,
        **metadata,
        "generated_utc": _utc(),
        "frozen_hypothesis": FROZEN_HYPOTHESIS,
        "dataset_role": "GA selection replay",
        "out_of_sample": False,
        "metric_semantics": {
            "net4": "minute PnL을 minute 시작 포지션 부호에 배정; 신규 진입 minute은 체결 후 부호에 배정",
            "avg_hold_min": "해당 월에 완결된 포지션의 전체 진입-청산 보유시간 평균",
            "avg_abs_position": "해당 방향의 non-flat minute-end |executed position| 평균",
        },
        "validation": {
            "passed": True,
            "tolerance": TOLERANCE,
            "max_abs_error": worst_error,
            "worst_check": worst_name,
            "checked": "cell별 source net4/RT/SL/TP/cap/RL count·PnL, 방향합, shadow state, fault",
        },
        "cells": cells,
        "summary": summary,
    }


def _write_summary(output_dir: Path) -> list[dict]:
    grouped = {}
    for path in sorted(output_dir.glob("generation_*/**/months/*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if not record.get("validation", {}).get("passed"):
            continue
        key0 = (record["generation"], record["genome"], int(record["seed"]))
        for side in SIDES:
            key = (*key0, side)
            row = grouped.setdefault(key, {
                "generation": key0[0], "genome": key0[1], "seed": key0[2], "side": side,
                "months": 0, "entries": 0, "round_trips": 0, "net4": 0.0,
                "holding_minutes_sum": 0.0, "abs_position_minute_sum": 0.0, "position_minutes": 0,
                "max_validation_error": 0.0, "latest_source_timestamp_utc": "",
            })
            value = record["summary"][side]
            row["months"] += 1
            for field in ("entries", "round_trips", "position_minutes"):
                row[field] += int(value[field])
            for field in ("net4", "holding_minutes_sum", "abs_position_minute_sum"):
                row[field] += float(value[field])
            for reason, _ in REASONS:
                row[f"{reason}_count"] = row.get(f"{reason}_count", 0) + int(value["exits"][reason]["count"])
                row[f"{reason}_pnl"] = row.get(f"{reason}_pnl", 0.0) + float(value["exits"][reason]["pnl"])
            row["max_validation_error"] = max(row["max_validation_error"],
                                               float(record["validation"]["max_abs_error"]))
            row["latest_source_timestamp_utc"] = max(row["latest_source_timestamp_utc"],
                                                      record["source_timestamp_utc"])
    rows = []
    for key in sorted(grouped):
        row = grouped[key]
        row["avg_hold_min"] = (row["holding_minutes_sum"] / row["round_trips"]
                               if row["round_trips"] else "")
        row["avg_abs_position"] = (row["abs_position_minute_sum"] / row["position_minutes"]
                                   if row["position_minutes"] else "")
        row["validation_passed"] = True
        row["data_cutoff"] = "<2024-01-01T00:00:00Z"
        row["out_of_sample"] = False
        rows.append(row)
    fields = ["generation", "genome", "seed", "side", "months", "entries", "round_trips", "net4",
              "cap_count", "cap_pnl", "SL_count", "SL_pnl", "TP_count", "TP_pnl", "RL_count", "RL_pnl",
              "avg_hold_min", "avg_abs_position", "position_minutes", "max_validation_error",
              "validation_passed", "latest_source_timestamp_utc", "data_cutoff", "out_of_sample"]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    A8.atomic_write(output_dir / "summary.csv", stream.getvalue().encode("utf-8"))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    run_dir, output_dir = args.run_dir.resolve(), args.output_dir.resolve()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA 필요: checkpoint의 CUDA generator state와 같은 action sample 보장 불가")
    numba.set_num_threads(1)
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)

    report = json.loads((run_dir / "selection_report.json").read_text(encoding="utf-8"))
    current_hashes = SEL._code_hashes()
    if current_hashes != report["hashes"]:
        raise RuntimeError("실행 코드 hash가 selection report와 다름; replay 금지")
    config_identity = dict(report["config"])
    config_identity.pop("stop_after_commits", None)
    checkpoint_hashes = {"code": report["hashes"], "input": report["input_hash"], "config": config_identity}

    completed = []
    for result_path in sorted((run_dir / "genomes").glob("generation_*/*/seed_*/result.json")):
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if result.get("status") == "complete":
            completed.append((result_path, result))
    if not completed:
        raise RuntimeError("완료 genome 없음")

    first_genome = A8.Genome.from_json(completed[0][1]["genome"])
    base_market, features, _, rv_median, input_hash, _ = SEL._load_inputs(first_genome.reward_config())
    if input_hash != report["input_hash"]:
        raise RuntimeError("입력 hash 불일치; replay 금지")
    months = A8.selection_months(report["config"]["start"], report["config"]["end"])
    start_ns, end_ns = months[0].value, (months[-1] + pd.offsets.MonthBegin(1)).value

    processed = skipped = 0
    for result_path, result in completed:
        seed_dir = result_path.parent
        generation, genome_name, seed_name = seed_dir.parents[1].name, seed_dir.parent.name, seed_dir.name
        seed = int(seed_name.removeprefix("seed_"))
        genome = A8.Genome.from_json(result["genome"])
        market = dict(base_market)
        market["m"] = RW.m_of_t(market["rv"], market["rv_ref"], genome.reward_config())
        model = A8.fresh_model(genome, features[1].shape[1], seed, device="cuda")
        genome_processed = genome_skipped = 0
        for source_path in sorted((seed_dir / "months").glob("*.json")):
            month = pd.Timestamp(f"{source_path.stem[:4]}-{source_path.stem[4:]}-01", tz="UTC")
            previous = month - pd.offsets.MonthBegin(1)
            checkpoint = (seed_dir / "checkpoints" / "pretrained.pt" if month == months[0]
                          else seed_dir / "checkpoints" / f"trained_{previous:%Y%m}.pt")
            if not checkpoint.exists():
                raise RuntimeError(f"선행 checkpoint 없음: {checkpoint}")
            checkpoint_sha, source_sha = _sha256(checkpoint), _sha256(source_path)
            target = output_dir / generation / genome_name / seed_name / "months" / source_path.name
            if target.exists():
                old = json.loads(target.read_text(encoding="utf-8"))
                valid = (old.get("validation", {}).get("passed")
                         and old.get("checkpoint_sha256") == checkpoint_sha
                         and old.get("source_month_sha256") == source_sha)
                if not valid:
                    raise RuntimeError(f"기존 출력 검증/hash 불일치; 덮어쓰기 금지: {target}")
                skipped += 1
                genome_skipped += 1
                continue
            state = A8.load_checkpoint(checkpoint, checkpoint_hashes)
            expected_phase = "pretrained" if month == months[0] else f"trained:{previous:%Y-%m}"
            if state["phase"] != expected_phase:
                raise RuntimeError(f"checkpoint phase 불일치: {checkpoint} {state['phase']} != {expected_phase}")
            model.load_state_dict(state["trainer"]["model"])
            evaluator = _make_evaluator(market, features, genome, rv_median, seed, start_ns, end_ns)
            evaluator.load_state_dict(state["evaluator"])
            evaluator.env.reset_direction_stats()
            raw = evaluator.run_month(model, (month + pd.offsets.MonthBegin(1)).value)
            source = json.loads(source_path.read_text(encoding="utf-8"))
            metadata = {
                "run_id": report["run_id"], "generation": generation, "genome": genome_name, "seed": seed,
                "month": f"{month:%Y-%m}", "source_month_json": str(source_path.relative_to(ROOT)),
                "source_month_sha256": source_sha, "source_timestamp_utc": datetime.fromtimestamp(
                    source_path.stat().st_mtime, timezone.utc).isoformat(),
                "checkpoint": str(checkpoint.relative_to(ROOT)), "checkpoint_sha256": checkpoint_sha,
                "checkpoint_phase": state["phase"], "data_cutoff": "<2024-01-01T00:00:00Z",
                "physical_test_reads": 0,
            }
            record = _validated_record(raw, source, evaluator.env, metadata)
            A8.json_write(target, record)
            processed += 1
            genome_processed += 1
            del evaluator, state, raw
            gc.collect()
        print(f"완료 {generation}/{genome_name}/{seed_name}: 처리={genome_processed}, skip={genome_skipped}", flush=True)
        del model
        torch.cuda.empty_cache()
    rows = _write_summary(output_dir)
    print(f"검증 일치: 처리={processed}, skip={skipped}, summary_rows={len(rows)}", flush=True)
    for row in rows:
        print(f"{row['generation']}/{row['genome']} {row['side']} entry={row['entries']} "
              f"RT={row['round_trips']} net4={row['net4']:.6f}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
