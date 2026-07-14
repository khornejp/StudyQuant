#!/usr/bin/env python3
"""
BTCUSDT Quant v7.18 - Regime Threshold & Feature Selection Experiment Runner

다른 PC에서도 돌릴 수 있도록 만든 실험 자동화 스크립트.
F1뿐만 아니라 Sharpe, MDD, Calmar 등 트레이딩 지표도 함께 비교.

사용법:
    python run_experiments.py --input data.csv --output experiments/ --quick
    python run_experiments.py --input data.csv --output experiments/ --full

필요사항:
    - Python 3.10+
    - btcusdt_quant 패키지 설치 (pip install -e .)
    - 학습용 CSV 데이터 파일
"""

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ExperimentConfig:
    name: str
    rv_percentile: float
    trend_percentile: float
    low_vol_multiplier: float
    min_run_bars: int
    feature_selection: bool = False
    fs_target_min: int = 0
    fs_target_max: int = 0


@dataclass  
class ExperimentResult:
    name: str
    config: ExperimentConfig
    success: bool
    error: str = ""
    # Metrics
    mean_test_f1: float = 0.0
    mean_test_accuracy: float = 0.0
    mean_test_precision: float = 0.0
    mean_test_recall: float = 0.0
    mean_test_ece: float = 0.0
    mean_test_brier: float = 0.0
    mean_test_sharpe: float = 0.0
    mean_test_mdd: float = 0.0
    mean_test_calmar: float = 0.0
    # Regime results
    regime_high_vol_f1: float = 0.0
    regime_ranging_f1: float = 0.0
    regime_trending_f1: float = 0.0
    regime_high_vol_rows: int = 0
    regime_ranging_rows: int = 0
    regime_trending_rows: int = 0
    # Feature selection
    fs_original_count: int = 0
    fs_selected_count: int = 0
    # Timing
    elapsed_seconds: float = 0.0


def run_experiment(
    input_path: Path,
    output_base: Path,
    config: ExperimentConfig,
) -> ExperimentResult:
    """Run a single experiment and extract metrics."""
    output_dir = output_base / config.name
    output_dir.mkdir(parents=True, exist_ok=True)
    
    cmd = [
        sys.executable, "-m", "btcusdt_quant", "train",
        "--input", str(input_path),
        "--output", str(output_dir),
        "--model-family", "stdlib",
        "--regime-aware",
        "--regime-rv-percentile", str(config.rv_percentile),
        "--regime-trend-percentile", str(config.trend_percentile),
        "--regime-low-vol-multiplier", str(config.low_vol_multiplier),
        "--regime-min-run-bars", str(config.min_run_bars),
    ]
    
    if config.feature_selection:
        cmd.extend([
            "--feature-selection",
            "--feature-selection-target-min", str(config.fs_target_min),
            "--feature-selection-target-max", str(config.fs_target_max),
        ])
    
    print(f"\n{'='*70}")
    print(f"[실험 시작] {config.name}")
    print(f"명령어: {' '.join(cmd)}")
    print(f"{'='*70}")
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,  # 1시간 타임아웃
        )
        elapsed = time.time() - start_time
        
        if result.returncode != 0:
            print(f"[실패] {config.name}")
            print(f"에러: {result.stderr[-500:]}")
            return ExperimentResult(
                name=config.name,
                config=config,
                success=False,
                error=result.stderr[-500:],
                elapsed_seconds=elapsed,
            )
        
        # 결과 파싱
        return _parse_results(output_dir, config, elapsed)
        
    except subprocess.TimeoutExpired:
        print(f"[타임아웃] {config.name} (1시간 초과)")
        return ExperimentResult(
            name=config.name,
            config=config,
            success=False,
            error="timeout",
            elapsed_seconds=3600,
        )
    except Exception as e:
        print(f"[예외] {config.name}: {e}")
        return ExperimentResult(
            name=config.name,
            config=config,
            success=False,
            error=str(e),
            elapsed_seconds=time.time() - start_time,
        )


def _parse_results(output_dir: Path, config: ExperimentConfig, elapsed: float) -> ExperimentResult:
    """Parse experiment results from output files."""
    result = ExperimentResult(
        name=config.name,
        config=config,
        success=True,
        elapsed_seconds=elapsed,
    )
    
    # Parse regime summary
    regime_summary_path = output_dir / "regime_run_summary.json"
    if regime_summary_path.exists():
        summary = json.loads(regime_summary_path.read_text(encoding="utf-8"))
        result.mean_test_f1 = float(summary.get("aggregated_mean_test_f1", 0.0))
        
        regime_results = summary.get("regime_results", {})
        for regime, data in regime_results.items():
            f1 = float(data.get("mean_test_f1", 0.0))
            rows = int(data.get("row_count", 0))
            if "high_volatility" in regime:
                result.regime_high_vol_f1 = f1
                result.regime_high_vol_rows = rows
            elif "ranging" in regime:
                result.regime_ranging_f1 = f1
                result.regime_ranging_rows = rows
            elif "trending" in regime:
                result.regime_trending_f1 = f1
                result.regime_trending_rows = rows
    
    # Parse run summary for detailed metrics
    run_summary_path = output_dir / "run_summary.json"
    if run_summary_path.exists():
        summary = json.loads(run_summary_path.read_text(encoding="utf-8"))
        result.mean_test_accuracy = float(summary.get("mean_test_accuracy", 0.0))
        result.mean_test_precision = float(summary.get("mean_test_precision", 0.0))
        result.mean_test_recall = float(summary.get("mean_test_recall", 0.0))
        result.mean_test_ece = float(summary.get("mean_test_ece", 0.0))
        result.mean_test_brier = float(summary.get("mean_test_brier", 0.0))
    
    # Parse fold metrics for trading metrics
    fold_metrics_path = output_dir / "fold_metrics.csv"
    if fold_metrics_path.exists():
        # Read test fold metrics
        import csv
        with open(fold_metrics_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            test_rows = [row for row in reader if row.get("split") == "test"]
            if test_rows:
                result.mean_test_sharpe = _mean_field(test_rows, "sharpe")
                result.mean_test_mdd = _mean_field(test_rows, "mdd")
                result.mean_test_calmar = _mean_field(test_rows, "calmar")
    
    # Parse feature selection report
    fs_report_path = output_dir / "feature_selection_report.json"
    if fs_report_path.exists():
        fs_report = json.loads(fs_report_path.read_text(encoding="utf-8"))
        result.fs_original_count = int(fs_report.get("feature_count_original", 0))
        result.fs_selected_count = int(fs_report.get("feature_count_bounded" if fs_report.get("bounds_applied") else "feature_count_core", 0))
    
    print(f"[완료] {config.name} | F1={result.mean_test_f1:.4f} | Sharpe={result.mean_test_sharpe:.4f} | MDD={result.mean_test_mdd:.4f} | 시간={elapsed:.1f}초")
    return result


def _mean_field(rows: list[dict[str, str]], field: str) -> float:
    values = [float(row.get(field, 0.0)) for row in rows if row.get(field)]
    return sum(values) / len(values) if values else 0.0


def print_results_table(results: list[ExperimentResult]) -> None:
    """Print formatted results table."""
    print("\n" + "="*100)
    print("실험 결과 요약")
    print("="*100)
    
    # Header
    print(f"{'실험명':<20} {'F1':>8} {'정확도':>8} {'Sharpe':>8} {'MDD':>8} {'Calmar':>8} {'high_vol':>10} {'ranging':>10} {'trending':>10} {'특성수':>8} {'시간(초)':>10}")
    print("-"*100)
    
    # Sort by F1 descending
    for r in sorted(results, key=lambda x: x.mean_test_f1, reverse=True):
        status = "✅" if r.success else "❌"
        fs_info = f"{r.fs_selected_count}/{r.fs_original_count}" if r.fs_original_count > 0 else "-"
        print(f"{status} {r.name:<18} {r.mean_test_f1:>8.4f} {r.mean_test_accuracy:>8.4f} "
              f"{r.mean_test_sharpe:>8.4f} {r.mean_test_mdd:>8.4f} {r.mean_test_calmar:>8.4f} "
              f"{r.regime_high_vol_f1:>10.4f} {r.regime_ranging_f1:>10.4f} {r.regime_trending_f1:>10.4f} "
              f"{fs_info:>8} {r.elapsed_seconds:>10.1f}")
    
    print("="*100)
    
    # Best by different metrics
    successful = [r for r in results if r.success]
    if successful:
        best_f1 = max(successful, key=lambda r: r.mean_test_f1)
        best_sharpe = max(successful, key=lambda r: r.mean_test_sharpe)
        best_calmar = max(successful, key=lambda r: r.mean_test_calmar)
        
        print("\n[최고 성능 설정]")
        print(f"  F1 최고:      {best_f1.name} (F1={best_f1.mean_test_f1:.4f})")
        print(f"  Sharpe 최고:  {best_sharpe.name} (Sharpe={best_sharpe.mean_test_sharpe:.4f})")
        print(f"  Calmar 최고:  {best_calmar.name} (Calmar={best_calmar.mean_test_calmar:.4f})")
        
        # Check if high_vol F1 >= 0.45
        if best_f1.regime_high_vol_f1 >= 0.45:
            print(f"\n✅ high_vol F1 목표 달성: {best_f1.regime_high_vol_f1:.4f} (>= 0.45)")
        else:
            print(f"\n⚠️  high_vol F1 목표 미달: {best_f1.regime_high_vol_f1:.4f} (< 0.45)")


def main():
    parser = argparse.ArgumentParser(description="BTCUSDT Quant v7.18 실험 자동화")
    parser.add_argument("--input", required=True, help="학습용 CSV 데이터 경로")
    parser.add_argument("--output", default="experiments", help="실험 결과 출력 폴더")
    parser.add_argument("--quick", action="store_true", help="빠른 실험 (4개 조합만)")
    parser.add_argument("--full", action="store_true", help="전체 실험 (20개 조합)")
    parser.add_argument("--with-fs", action="store_true", help="Feature Selection 20~30 실험도 포함")
    parser.add_argument("--fs-only", action="store_true", help="Feature Selection만 실험")
    args = parser.parse_args()
    
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"에러: 입력 파일을 찾을 수 없습니다: {input_path}")
        sys.exit(1)
    
    output_base = Path(args.output)
    output_base.mkdir(parents=True, exist_ok=True)
    
    # Experiment configurations
    if args.fs_only:
        experiments = [
            ExperimentConfig("fs_baseline", 0.75, 0.70, 2.0, 3, False),
            ExperimentConfig("fs_20_30", 0.75, 0.70, 2.0, 3, True, 20, 30),
            ExperimentConfig("fs_25_35", 0.75, 0.70, 2.0, 3, True, 25, 35),
            ExperimentConfig("fs_15_25", 0.75, 0.70, 2.0, 3, True, 15, 25),
        ]
    elif args.quick:
        experiments = [
            ExperimentConfig("baseline", 0.75, 0.70, 2.0, 3),
            ExperimentConfig("rv80_trend70", 0.80, 0.70, 2.0, 3),
            ExperimentConfig("rv70_trend65", 0.70, 0.65, 2.0, 3),
            ExperimentConfig("rv75_trend65_m15", 0.75, 0.65, 1.5, 3),
        ]
    else:  # full or default
        experiments = [
            # Baseline
            ExperimentConfig("baseline", 0.75, 0.70, 2.0, 3),
            # rv_percentile sweep
            ExperimentConfig("rv70_trend70", 0.70, 0.70, 2.0, 3),
            ExperimentConfig("rv75_trend70", 0.75, 0.70, 2.0, 3),
            ExperimentConfig("rv80_trend70", 0.80, 0.70, 2.0, 3),
            ExperimentConfig("rv85_trend70", 0.85, 0.70, 2.0, 3),
            # trend_percentile sweep
            ExperimentConfig("rv75_trend60", 0.75, 0.60, 2.0, 3),
            ExperimentConfig("rv75_trend65", 0.75, 0.65, 2.0, 3),
            ExperimentConfig("rv75_trend75", 0.75, 0.75, 2.0, 3),
            # low_vol_multiplier sweep
            ExperimentConfig("rv75_trend70_m15", 0.75, 0.70, 1.5, 3),
            ExperimentConfig("rv75_trend70_m25", 0.75, 0.70, 2.5, 3),
            # min_run_bars
            ExperimentConfig("rv75_trend70_run1", 0.75, 0.70, 2.0, 1),
            ExperimentConfig("rv75_trend70_run5", 0.75, 0.70, 2.0, 5),
        ]
    
    # Add feature selection experiments if requested
    if args.with_fs or args.full:
        experiments.extend([
            ExperimentConfig("fs_baseline", 0.75, 0.70, 2.0, 3, True, 20, 30),
            ExperimentConfig("fs_rv80", 0.80, 0.70, 2.0, 3, True, 20, 30),
            ExperimentConfig("fs_rv75_trend65", 0.75, 0.65, 2.0, 3, True, 20, 30),
        ])
    
    print("BTCUSDT Quant v7.18 실험 자동화")
    print(f"입력 데이터: {input_path}")
    print(f"출력 폴더: {output_base}")
    print(f"총 실험 수: {len(experiments)}")
    print("평가 지표: F1, Accuracy, Sharpe, MDD, Calmar")
    
    results: list[ExperimentResult] = []
    for i, config in enumerate(experiments, 1):
        print(f"\n[{i}/{len(experiments)}] ", end="")
        result = run_experiment(input_path, output_base, config)
        results.append(result)
        
        # 중간 결과 저장
        _save_intermediate(results, output_base)
    
    # Final report
    print_results_table(results)
    
    # Save final results
    final_report_path = output_base / "experiment_results.json"
    final_report_path.write_text(
        json.dumps([_result_to_dict(r) for r in results], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\n최종 결과 저장: {final_report_path}")


def _save_intermediate(results: list[ExperimentResult], output_base: Path) -> None:
    """Save intermediate results after each experiment."""
    path = output_base / "experiment_results_partial.json"
    path.write_text(
        json.dumps([_result_to_dict(r) for r in results], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _result_to_dict(r: ExperimentResult) -> dict[str, Any]:
    return {
        "name": r.name,
        "config": {
            "rv_percentile": r.config.rv_percentile,
            "trend_percentile": r.config.trend_percentile,
            "low_vol_multiplier": r.config.low_vol_multiplier,
            "min_run_bars": r.config.min_run_bars,
            "feature_selection": r.config.feature_selection,
            "fs_target_min": r.config.fs_target_min,
            "fs_target_max": r.config.fs_target_max,
        },
        "success": r.success,
        "error": r.error,
        "metrics": {
            "mean_test_f1": r.mean_test_f1,
            "mean_test_accuracy": r.mean_test_accuracy,
            "mean_test_precision": r.mean_test_precision,
            "mean_test_recall": r.mean_test_recall,
            "mean_test_ece": r.mean_test_ece,
            "mean_test_brier": r.mean_test_brier,
            "mean_test_sharpe": r.mean_test_sharpe,
            "mean_test_mdd": r.mean_test_mdd,
            "mean_test_calmar": r.mean_test_calmar,
        },
        "regime_results": {
            "high_vol_f1": r.regime_high_vol_f1,
            "high_vol_rows": r.regime_high_vol_rows,
            "ranging_f1": r.regime_ranging_f1,
            "ranging_rows": r.regime_ranging_rows,
            "trending_f1": r.regime_trending_f1,
            "trending_rows": r.regime_trending_rows,
        },
        "feature_selection": {
            "original_count": r.fs_original_count,
            "selected_count": r.fs_selected_count,
        },
        "elapsed_seconds": r.elapsed_seconds,
    }


if __name__ == "__main__":
    main()
