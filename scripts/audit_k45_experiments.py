"""Mechanical audit of every out/k45_* experiment.

Writes docs/audit/2026-10-02_k45_experiment_audit.md. No interpretation:
manifest fields verbatim, output hash check, test rerun, REPORT.md head verbatim,
and a table of numbers quoted in conversation vs the value stored on disk.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")
DOC = os.path.join(ROOT, "docs", "audit", "2026-10-02_k45_experiment_audit.md")
PY = sys.executable
REPORT_HEAD_LINES = 150
HEX64 = re.compile(r"^[0-9a-f]{64}$")

TESTS = {
    "k45_trend_side_20261001": "tests/test_k45_trend_side.py",
    "k45_trend_side_tp_20261001": "tests/test_k45_trend_side.py",
    "k45_gate_direction_20261001": "tests/test_k45_gate_direction.py",
    "k45_gate_direction_audit_20261001": "tests/test_k45_gate_direction.py",
    "k45_gate_direction_r2_20261001": "tests/test_k45_gate_direction_r2.py",
    "k45_gate_direction_r2_6_20261001": "tests/test_k45_gate_direction_r2_6.py",
    "k45_gate_direction_r2_7_20261001": "tests/test_k45_gate_direction_r2_7.py",
    "k45_gate_direction_r2_8_20261001": "tests/test_k45_gate_direction_r2_8.py",
    "k45_gate_direction_r2_10_20261001": "tests/test_k45_gate_direction_r2_10.py",
    "k45_gate_direction_r2_10b_20261001": "tests/test_k45_gate_direction_r2_10.py",
    "k45_gate_direction_r2_9_20261001": "tests/test_k45_gate_direction_r2_9.py",
    "k45_gate_direction_r2_11_20261001": "tests/test_k45_gate_direction_r2_11.py",
    "k45_mtf_entry_r2_12_20261001": "tests/test_k45_mtf_entry_r2_12.py",
    "k45_classic_rules_r2_14_20261002": "tests/test_k45_classic_rules_r2_14.py",
    "k45_gate_direction_r2_9b_20261002": "tests/test_k45_gate_direction_r2_9b.py",
    "k45_meta_label_r2_15_20261002": "tests/test_k45_meta_label_r2_15.py",
    "k45_holdout_a_2026q3": "tests/test_k45_holdout_a_2026q3.py",
    "k45_mtf_persistence_r2_13_20261002": "tests/test_k45_mtf_persistence_r2_13.py",
    "k45_contrarian_robust_r2_17_20261002": "tests/test_k45_contrarian_robust_r2_17.py",
    "k45_risk_stop_r2_18_20261002": "tests/test_k45_risk_stop_r2_18.py",
    "k45_train_window_r2_16_20261002": "tests/test_k45_train_window_r2_16.py",
    "k45_validation_r2_19_20261003": "tests/test_k45_validation_r2_19.py",
    "k45_mtf_tail_r2_20_20261003": "tests/test_k45_mtf_tail_r2_20.py",
    "k45_patchtst_updown_r2_21_20261003": "tests/test_k45_patchtst_updown_r2_21.py",
    "k45_funding_fix_20261004": "tests/test_k45_funding.py",
    "k45_funding_rerun_r2_20_21_20261004": "tests/test_k45_mtf_tail_r2_20.py",
    "k45_candidate_compare_r2_23_20261004": "tests/test_k45_candidate_compare_r2_23.py",
    "k45_single_book_combo_r2_24_20261004": "tests/test_k45_single_book_combo_r2_24.py",
    "k45_combo_robust_r2_25_20261004": "tests/test_k45_combo_robust_r2_25.py",
    "k45_hold_a_data_r2_26_20261004": "tests/test_k45_hold_a_data_r2_26.py",
    "k45_hold_a_eval_build_r2_27_20261005": "tests/test_k45_hold_a_eval_r2_27.py",
    "k45_hold_a_unblock_r2_28_20261005": "tests/test_k45_hold_a_eval_r2_27.py",
    "k45_hold_a_runner_complete_r2_29_20261005": "tests/test_k45_hold_a_eval_r2_27.py",
    "k45_hold_a_report_complete_r2_30_20261005": "tests/test_k45_hold_a_eval_r2_27.py",
    "k45_hold_a_final_review_r2_31_20261005": "tests/test_k45_hold_a_eval_r2_27.py",
    "k45_hold_a_exclude_bookticker_r2_32_20261005": "tests/test_k45_hold_a_eval_r2_27.py",
}


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_pairs(obj, key_hint=""):
    """Yield (path, sha) pairs found anywhere under an outputs-like manifest node."""
    if isinstance(obj, dict):
        sha = obj.get("sha256")
        path = obj.get("path") or obj.get("file") or obj.get("name")
        if isinstance(sha, str) and HEX64.match(sha) and isinstance(path, str):
            yield path, sha
            return
        for k, v in obj.items():
            if isinstance(v, str) and HEX64.match(v):
                if k != "sha256":
                    yield k, v
            elif isinstance(v, dict) and isinstance(v.get("sha256"), str) and not (
                    v.get("path") or v.get("file") or v.get("name")):
                yield k, v["sha256"]
            else:
                yield from hash_pairs(v, k)
    elif isinstance(obj, list):
        for v in obj:
            yield from hash_pairs(v, key_hint)


def resolve(path: str, exp_dir: str) -> str | None:
    for cand in (path, os.path.join(ROOT, path), os.path.join(exp_dir, path),
                 os.path.join(exp_dir, os.path.basename(path))):
        if os.path.isfile(cand):
            return cand
    return None


def verify_outputs(manifest: dict, exp_dir: str):
    node = None
    for key in ("outputs", "output_sha256"):
        if key in manifest:
            node = manifest[key]
            break
    if node is None:
        return None
    rows = []
    for path, sha in hash_pairs(node):
        real = resolve(path, exp_dir)
        if real is None:
            rows.append((path, "MISSING"))
        else:
            rows.append((path, "OK" if sha256(real) == sha else "CHANGED"))
    return rows


def run_test(test: str) -> str:
    if not os.path.isfile(os.path.join(ROOT, test)):
        return "test file not found"
    r = subprocess.run([PY, "-m", "pytest", "-q", test,
                        "--basetemp=.pytest_tmp_r2_33_audit"], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = [l for l in (r.stdout + r.stderr).splitlines() if l.strip()]
    return lines[-1] if lines else f"exit {r.returncode}"


def git_tracked(test: str) -> str:
    r = subprocess.run(["git", "log", "--oneline", "-1", "--", test], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout.strip() or "not committed"


def scalar_fields(manifest: dict) -> list[tuple[str, str]]:
    skip = {"inputs", "outputs", "sources", "source", "input_sha256", "source_sha256",
            "output_sha256", "out_of_sample_result"}
    out = []
    for k, v in manifest.items():
        if k in skip:
            continue
        if isinstance(v, (dict, list)):
            out.append((k, json.dumps(v, ensure_ascii=False)[:600]))
        else:
            out.append((k, str(v)))
    return out


def fence(text: str) -> str:
    return "```text\n" + text.rstrip() + "\n```"


# ---------- quoted-number checks (value I stated vs value on disk) ----------

def _q(path, **flt):
    d = pd.read_parquet(os.path.join(OUT, path))
    for k, v in flt.items():
        d = d[d[k] == v]
    return d


def claim_rows():
    rows = []

    def add(exp, what, said, fn):
        try:
            val = fn()
        except Exception as e:  # report the failure itself, never hide it
            val = f"ERROR {type(e).__name__}: {e}"
        rows.append((exp, what, said, val))

    g9 = "k45_gate_direction_r2_9_20261001/grid_metrics.parquet"
    for hl, said_dev, said_hb in ((90, "n 335 / +20.80", "n 40 / +29.26"),
                                  (240, "n 245 / +21.85", "n 32 / +63.80")):
        for seg, said in (("DEV", said_dev), ("HOLD_B", said_hb)):
            add("R2-9", f"SIDE ROLLING_180D q=0.01 L{hl}/S60 {seg} n / net_mean", said,
                lambda hl=hl, seg=seg: (lambda r: f"n {int(r.n)} / {r.net_mean_bps:+.2f}")(
                    _q(g9, combination="SIDE", method="ROLLING_180D", q=0.01, h_long=hl,
                       h_short=60, segment=seg).iloc[0]))
    add("R2-9", "SIDE ROLLING_180D q=0.01 L90/S60 DEV pw_ci95", "[+7.35, +33.72]",
        lambda: (lambda r: f"[{r.pw_ci95_lower:+.2f}, {r.pw_ci95_upper:+.2f}]")(
            _q(g9, combination="SIDE", method="ROLLING_180D", q=0.01, h_long=90, h_short=60,
               segment="DEV").iloc[0]))
    add("R2-9", "DEV cells with pw_ci95_lower > 0", "43",
        lambda: str(int((_q(g9, segment="DEV").pw_ci95_lower > 0).sum())))

    c10 = "k45_gate_direction_r2_10_20261001/core_metrics.parquet"
    for seg, said in (("DEV", "n 678 / +6.44"), ("HOLD_B", "+1.61")):
        add("R2-10", f"RESIDUAL_MATCHED_CAUSAL_M020_RATE L45/S60 {seg}", said,
            lambda seg=seg: (lambda r: f"n {int(r.n)} / {r.net_mean_bps:+.2f}")(
                _q(c10, rule="RESIDUAL_MATCHED_CAUSAL_M020_RATE", h_long=45, h_short=60,
                   segment=seg).iloc[0]))

    m11 = json.load(open(os.path.join(OUT, "k45_gate_direction_r2_11_20261001/manifest.json"),
                         encoding="utf-8"))["out_of_sample_result"]
    add("R2-11", "manifest out_of_sample_result", "-0.0023 / -0.0029 / -0.31 / -1.78 / false",
        lambda: json.dumps(m11))
    tf = "k45_gate_direction_r2_11_20261001/tuning_folds.parquet"
    add("R2-11", "DEV tuned-version fallback share", "54.8%",
        lambda: (lambda t: f"{(t.selection_status != 'TUNED').mean():.3%}")(
            _q(tf, version="tuned", segment="DEV")))
    sp11 = "k45_gate_direction_r2_11_20261001/single_position_comparison.parquet"
    add("R2-11", "RESIDUAL causal L45/S60 DEV fixed -> tuned", "+6.44 -> -0.30",
        lambda: (lambda r: f"{r.net_mean_bps_fixed:+.2f} -> {r.net_mean_bps_tuned:+.2f}")(
            _q(sp11, rule="RESIDUAL_MATCHED_CAUSAL_M020_RATE", h_long=45, h_short=60,
               segment="DEV").iloc[0]))

    c12 = "k45_mtf_entry_r2_12_20261001/core_metrics.parquet"
    add("R2-12", "DEV cells with pw_ci95_lower > 0 (of 100)", "0",
        lambda: str(int((_q(c12, segment="DEV").pw_ci95_lower > 0).sum())))
    add("R2-12", "1h h60 15m gate E1 k1.0 DEV / HOLD_B", "n 1428 +3.76 / n 150 +14.11",
        lambda: " / ".join(
            f"n {int(r.n)} {r.net_mean_bps:+.2f}" for _, r in
            _q(c12, tf="1h", horizon=60, entry_tf=15, rule="E1", k=1.0, gate_used=True)
            .sort_values("segment").iterrows()))

    a14 = "k45_classic_rules_r2_14_20261002/all_cells.parquet"
    for cid, said in (("F3|1h|10/24|signal|LS", "DEV 873 +35,384 Sharpe 1.49 / HB 76 +1,182"),
                      ("A3|4h|720|signal|LS", "DEV 339 +31,309 Sharpe 0.80 / HB 45 +3,056"),
                      ("F1|1h|5/24|signal|LS", "DEV 818 +16,024 Sharpe 0.75 / HB 48 +928")):
        add("R2-14", cid, said,
            lambda cid=cid: " / ".join(
                f"{r.segment} {int(r.n)} {r.net_total_bps:+,.0f} Sharpe {r.daily_sharpe:.2f}"
                for _, r in _q(a14, cell_id=cid).sort_values("segment").iterrows()))
    add("R2-14", "SPA p (zero / buy_hold)", "0.144 / 0.734",
        lambda: (lambda d: " / ".join(f"{b} {p:.3f}" for b, p in zip(d.benchmark, d.spa_p)))(
            pd.read_parquet(os.path.join(OUT, "k45_classic_rules_r2_14_20261002/multiple_testing.parquet"))))
    y14 = "k45_classic_rules_r2_14_20261002/yearly.parquet"
    add("R2-14", "F3 10/24 LS yearly net_bps",
        "+4,281 / +14,319 / +4,765 / +5,540 / +5,070 / +1,410 / +1,182",
        lambda: " / ".join(f"{int(r.year)} {r.net_bps:+,.0f}" for _, r in
                           _q(y14, cell_id="F3|1h|10/24|signal|LS").sort_values("year").iterrows()))
    # --- after the funding fix (R2-22 .. R2-26), numbers quoted 2026-10-04 ---
    def comp(path, seg, bnd, cand):
        d = _q(path, segment=seg, boundary=bnd, candidate=cand)
        return d.iloc[0]

    m23 = "k45_candidate_compare_r2_23_20261004/metrics.parquet"
    for cand, said in (("F3|1h|10/24|signal|LS", "+30,362 / 1.55 / +7.56"),
                       ("E1|1h|3|signal|L", "+8,614 / 0.83 / -0.09")):
        add("R2-23", f"{cand} DEV_COMMON PESS net / Sharpe / PW lower", said,
            lambda cand=cand: (lambda r: f"{r.net_total_bps:+,.0f} / {r.mtm_daily_sharpe:.2f} / "
                                         f"{r.pw_ci95_lower_daily_bps:+.2f}")(
                comp(m23, "DEV_COMMON", "PESS", cand)))
    c24 = "k45_single_book_combo_r2_24_20261004/combo_metrics.parquet"
    add("R2-24", "C1 FIRST DEV_COMMON PESS net / Sharpe / MDD", "+35,718 / 1.73 / 3,674",
        lambda: (lambda r: f"{r.net_total_bps:+,.0f} / {r.mtm_daily_sharpe:.2f} / "
                           f"{r.mtm_max_drawdown_bps:,.0f}")(
            _q(c24, combo="C1", rule="FIRST", boundary="PESS", segment="DEV_COMMON").iloc[0]))
    h25 = "k45_combo_robust_r2_25_20261004/hypothesis.parquet"
    add("R2-25", "neighbour combos both-better count (PESS / OPT)", "17 / 15",
        lambda: (lambda d: f"{int(d.set_index('boundary').loc['PESS','both_frozen_n'])} / "
                           f"{int(d.set_index('boundary').loc['OPT','both_frozen_n'])}")(
            pd.read_parquet(os.path.join(OUT, h25))))

    m32 = "k45_hold_a_exclude_bookticker_r2_32_20261005/hold_a/metrics.parquet"
    for book, said in (("H1", "365.221046"), ("H2", "1503.528994"),
                       ("H3", "1376.416586"), ("H4", "1397.682266"),
                       ("H5", "400.702128"), ("B0", "3381.737936")):
        add("R2-32", f"HOLD_A PESS 4bps total_net {book}", said,
            lambda book=book: f"{_q(m32, book=book, boundary='PESS', cost_bps=4.0).loc[lambda d: d.fold.isna(), 'total_net_bps'].iloc[0]:.6f}")
    hold_manifest = os.path.join(
        OUT, "k45_hold_a_exclude_bookticker_r2_32_20261005/hold_a/manifest.json")
    add("R2-32", "frozen hypotheses CONFIRMED", "6",
        lambda: str(sum(row["verdict"] == "CONFIRMED" for row in
                        json.load(open(hold_manifest, encoding="utf-8"))["out_of_sample_result"])))
    fold32 = "k45_hold_a_exclude_bookticker_r2_32_20261005/fold_comparison.parquet"
    for arm, said in (("LONG", "581 / 621"), ("SHORT", "621 / 621")):
        add("R2-32", f"{arm} exact folds", said,
            lambda arm=arm: (lambda d: f"{int(d.selection_exact.sum())} / {len(d)}")(
                _q(fold32, arm=arm)))
    return rows


NUM = re.compile(r"[-+]?\d[\d,]*\.?\d*")


def same(said: str, disk: str) -> str:
    """Every number I quoted must match some disk number at the quoted precision."""
    if disk.startswith("ERROR"):
        return "확인 불가"
    disk_nums = [float(x.replace(",", "")) for x in NUM.findall(disk.replace("−", "-"))]
    for tok in NUM.findall(said.replace("−", "-")):
        dec = len(tok.split(".")[1]) if "." in tok else 0
        v = float(tok.replace(",", ""))
        tol = 0.5 * 10 ** -dec + 1e-12
        if not any(abs(v - d) <= tol for d in disk_nums):
            return f"다름 ({tok})"
    return "같음"


def main():
    os.makedirs(os.path.dirname(DOC), exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True).stdout.strip()
    L = [f"# K45 실험 전수 점검 (기계적 추출)", "",
         f"- 생성 UTC: {now}",
         f"- git HEAD: {head}",
         f"- 생성 스크립트: scripts/audit_k45_experiments.py",
         "- 방식: 각 out/k45_* 폴더의 manifest.json 필드를 그대로 옮기고, manifest에 기록된 출력 파일 SHA256을 지금 디스크 파일과 비교하고, 대응 테스트를 다시 실행하고, REPORT.md 앞부분을 그대로 붙인다. 해석 문장은 쓰지 않는다.",
         "- 마지막 절: 대화에서 내가 인용한 숫자와 디스크 값을 나란히 둔다.", ""]

    dirs = sorted(d for d in glob.glob(os.path.join(OUT, "k45_*")) if os.path.isdir(d))
    L += ["## 폴더 목록", "", "| 폴더 | manifest | REPORT.md 줄 수 | 대응 테스트 | 테스트 커밋 |", "|---|---|---|---|---|"]
    for d in dirs:
        name = os.path.basename(d)
        rep = os.path.join(d, "REPORT.md")
        nlines = sum(1 for _ in open(rep, encoding="utf-8", errors="replace")) if os.path.isfile(rep) else "없음"
        test = TESTS.get(name, "")
        L.append(f"| {name} | {'있음' if os.path.isfile(os.path.join(d, 'manifest.json')) else '없음'} | {nlines} | {test} | {git_tracked(test) if test else ''} |")
    L.append("")

    test_cache: dict[str, str] = {}
    for d in dirs:
        name = os.path.basename(d)
        L += [f"## {name}", ""]
        mpath = os.path.join(d, "manifest.json")
        test = TESTS.get(name)
        if test:
            if test not in test_cache:
                test_cache[test] = run_test(test)
            L.append(f"- 테스트 재실행 `{test}`: `{test_cache[test]}`")
        if not os.path.isfile(mpath):
            files = sorted(os.listdir(d))
            L += ["- manifest 없음 (미완료 또는 실행 전).", f"- 파일: {', '.join(files)}", ""]
            for logname in ("queue.log",):
                p = os.path.join(d, logname)
                if os.path.isfile(p):
                    txt = open(p, "rb").read().decode("utf-16", errors="replace") if open(p, "rb").read(2) == b"\xff\xfe" else open(p, encoding="utf-8", errors="replace").read()
                    L += [f"- {logname}:", fence(txt), ""]
            continue
        m = json.load(open(mpath, encoding="utf-8"))
        L += ["### manifest 필드", "", "| 필드 | 값 |", "|---|---|"]
        for k, v in scalar_fields(m):
            L.append(f"| {k} | {v.replace('|', '/').replace(chr(10), ' ')} |")
        L.append("")
        if "out_of_sample_result" in m:
            L += ["### out_of_sample_result (원문)", "",
                  fence(json.dumps(m["out_of_sample_result"], ensure_ascii=False, indent=1)[:6000]), ""]
        ver = verify_outputs(m, d)
        if ver is None:
            L += ["- 출력 해시: manifest에 outputs 해시 항목 없음.", ""]
        else:
            ok = sum(1 for _, s in ver if s == "OK")
            bad = [(p, s) for p, s in ver if s != "OK"]
            L.append(f"- 출력 해시 확인: {ok}/{len(ver)} 일치")
            for p, s in bad:
                L.append(f"  - {s}: {p}")
            L.append("")
        rep = os.path.join(d, "REPORT.md")
        if os.path.isfile(rep):
            lines = open(rep, encoding="utf-8", errors="replace").read().splitlines()
            L += [f"### REPORT.md 앞 {min(REPORT_HEAD_LINES, len(lines))}줄 (전체 {len(lines)}줄, 원문)", ""]
            L += lines[:REPORT_HEAD_LINES]
            L.append("")

    L += ["## 대화에서 인용한 숫자 vs 디스크 값", "",
          "| 실험 | 항목 | 대화에서 말한 값 | 디스크 값 | 같음 |", "|---|---|---|---|---|"]
    for exp, what, said, val in claim_rows():
        esc = lambda s: s.replace("|", r"\|")
        L.append(f"| {exp} | {esc(what)} | {esc(said)} | {esc(val)} | {same(said, val)} |")
    L.append("")
    with open(DOC, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(DOC)


if __name__ == "__main__":
    main()
