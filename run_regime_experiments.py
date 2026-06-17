#!/usr/bin/env python3
"""Run regime threshold experiments and save summary."""
import json
import subprocess
import sys
from pathlib import Path

EXPERIMENTS = [
    {"rv": 0.80, "trend": 0.70, "mult": 2.0, "name": "rv80_trend70"},
    {"rv": 0.70, "trend": 0.70, "mult": 2.0, "name": "rv70_trend70"},
    {"rv": 0.75, "trend": 0.65, "mult": 2.0, "name": "rv75_trend65"},
    {"rv": 0.75, "trend": 0.75, "mult": 2.0, "name": "rv75_trend75"},
    {"rv": 0.75, "trend": 0.70, "mult": 1.5, "name": "rv75_trend70_m15"},
]

def run_experiment(exp):
    output = Path(f"artifacts/experiments/{exp['name']}")
    output.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "btcusdt_quant", "train",
        "--input", "artifacts/btcusdt_1m_2024_01_02.csv",
        "--output", str(output),
        "--model-family", "stdlib",
        "--regime-aware",
        "--regime-rv-percentile", str(exp["rv"]),
        "--regime-trend-percentile", str(exp["trend"]),
        "--regime-low-vol-multiplier", str(exp["mult"]),
    ]
    print(f"\n{'='*60}")
    print(f"Running: {exp['name']}")
    print(f"Command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(f"Return code: {result.returncode}")
    if result.stdout:
        print(result.stdout[-500:])  # Last 500 chars
    if result.stderr:
        print(result.stderr[-500:])
    
    summary_path = output / "regime_run_summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text())
        return {
            "name": exp["name"],
            "config": exp,
            "aggregated_f1": summary.get("aggregated_mean_test_f1", 0),
            "regime_results": summary.get("regime_results", {}),
            "regime_counts": summary.get("regime_counts", {}),
        }
    return {"name": exp["name"], "config": exp, "error": "No summary found"}

def main():
    results = []
    for exp in EXPERIMENTS:
        result = run_experiment(exp)
        results.append(result)
        # Save intermediate results
        Path("artifacts/experiments/results.json").write_text(
            json.dumps(results, indent=2)
        )
    
    print("\n" + "="*60)
    print("ALL EXPERIMENTS COMPLETE")
    print("="*60)
    for r in results:
        print(f"{r['name']}: F1={r.get('aggregated_f1', 'N/A')}")
        if "regime_results" in r:
            for regime, data in r["regime_results"].items():
                f1 = data.get("mean_test_f1", "N/A")
                print(f"  {regime}: F1={f1}")

if __name__ == "__main__":
    main()
