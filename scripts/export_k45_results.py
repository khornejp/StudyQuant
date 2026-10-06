"""Drop every out/k45_* result into docs/results/ as plain files.

Per experiment folder: REPORT.md and manifest.json copied verbatim, and
tables.md with every parquet of <= MAX_ROWS rows rendered in full (larger
parquets listed with shape and path). No interpretation is added.
"""
from __future__ import annotations

import glob
import os
import shutil

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")
DEST = os.path.join(ROOT, "docs", "results")
MAX_ROWS = 2000  # ponytail: row cap keeps files readable; raise if a bigger table must be inline

DOC_LINKS = {
    "k45_gate_direction_r2_7_20261001": "https://claude.ai/code/artifact/b113e4cd-8b7f-439a-be79-1733ac7a0b3c",
    "k45_gate_direction_r2_10_20261001": "https://claude.ai/code/artifact/1b5e4d15-7cdb-4d58-ad3f-4c80f174e00e",
    "k45_gate_direction_r2_9_20261001": "https://claude.ai/code/artifact/2c237cc4-bd79-45c2-b814-eefb5fad3874",
    "k45_gate_direction_r2_11_20261001": "https://claude.ai/code/artifact/ac465066-3f8a-4cf3-a801-4abf763b2fdd",
    "k45_mtf_entry_r2_12_20261001": "https://claude.ai/code/artifact/f932d55e-4c0b-4465-9176-5aee392cc633",
    "k45_classic_rules_r2_14_20261002": "https://claude.ai/code/artifact/837d2a37-97a0-4d6e-9f9e-d56f9e2c3fed",
}


def cell(v) -> str:
    if isinstance(v, float):
        return "" if pd.isna(v) else f"{v:.6g}"
    return str(v).replace("|", r"\|").replace("\n", " ")[:300]


def render(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join(cell(v) for v in row) + " |")
    return "\n".join(lines)


def main():
    os.makedirs(DEST, exist_ok=True)
    index = ["# K45 실험 결과 파일 모음", "",
             "생성: scripts/export_k45_results.py. 각 폴더 = out/ 의 같은 이름 폴더에서 복사·변환. 해석 없음.", "",
             "| 실험 폴더 | REPORT.md | manifest.json | 표 수 (전체/인라인) | 분석 문서(Claude Docs) |", "|---|---|---|---|---|"]
    for src in sorted(d for d in glob.glob(os.path.join(OUT, "k45_*")) if os.path.isdir(d)):
        name = os.path.basename(src)
        dst = os.path.join(DEST, name)
        os.makedirs(dst, exist_ok=True)
        copied = {}
        for fn in ("REPORT.md", "manifest.json", "BRIEF.md", "BRIEF_v2.md"):
            p = os.path.join(src, fn)
            if os.path.isfile(p):
                shutil.copy2(p, os.path.join(dst, fn))
                copied[fn] = True
        parts = [f"# {name} — parquet 표 전체", "", f"원본 폴더: out/{name}/", ""]
        total = inline = 0
        for p in sorted(glob.glob(os.path.join(src, "*.parquet"))):
            total += 1
            try:
                df = pd.read_parquet(p)
            except Exception as e:  # show the failure, do not skip silently
                parts += [f"## {os.path.basename(p)}", "", f"읽기 실패: {type(e).__name__}: {e}", ""]
                continue
            parts += [f"## {os.path.basename(p)}", "", f"행 {len(df):,} × 열 {df.shape[1]}", ""]
            if len(df) <= MAX_ROWS:
                inline += 1
                parts += [render(df), ""]
            else:
                parts += [f"{MAX_ROWS:,}행 초과라 인라인하지 않음. 열: {', '.join(map(str, df.columns))}", ""]
        with open(os.path.join(dst, "tables.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(parts))
        index.append(f"| [{name}]({name}/) | {'있음' if copied.get('REPORT.md') else '없음'} | "
                     f"{'있음' if copied.get('manifest.json') else '없음'} | {total}/{inline} | {DOC_LINKS.get(name, '')} |")
    index += ["", "점검 결과: docs/audit/2026-10-02_k45_experiment_audit.md"]
    with open(os.path.join(DEST, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(index))
    print(DEST)


if __name__ == "__main__":
    main()
