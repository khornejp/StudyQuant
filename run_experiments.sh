#!/bin/bash
# BTCUSDT Quant v7.18 실험 자동화 쉘 스크립트
# Linux/Mac 환경용

echo "=========================================="
echo "BTCUSDT Quant v7.18 실험 자동화"
echo "=========================================="

# Python 경로 탐지
PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    if command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        echo "[오류] Python을 찾을 수 없습니다. Python 3.10+이 필요합니다."
        exit 1
    fi
fi

echo "Python: $PYTHON_CMD"
$PYTHON_CMD --version

# btcusdt_quant 확인
if ! $PYTHON_CMD -c "import btcusdt_quant" 2>/dev/null; then
    echo "[오류] btcusdt_quant 패키지가 설치되지 않았습니다."
    echo "pip install -e ."
    exit 1
fi

# 인자 확인
INPUT_FILE="${1:-}"
OUTPUT_DIR="${2:-experiments}"
EXTRA_ARGS="${3:-}"

if [ -z "$INPUT_FILE" ]; then
    echo "사용법: $0 [데이터_CSV_경로] [출력_폴] [옵션]"
    echo ""
    echo "예시:"
    echo "  $0 data.csv experiments"
    echo "  $0 data.csv experiments --quick"
    echo "  $0 data.csv experiments --full"
    echo "  $0 data.csv experiments --with-fs"
    exit 1
fi

echo "입력 데이터: $INPUT_FILE"
echo "출력 폴: $OUTPUT_DIR"
echo "추가 옵션: $EXTRA_ARGS"
echo ""
echo "실험 시작..."
echo "=========================================="

$PYTHON_CMD run_experiments.py --input "$INPUT_FILE" --output "$OUTPUT_DIR" $EXTRA_ARGS

echo ""
echo "=========================================="
echo "실험 완료!"
echo "결과 폴: $OUTPUT_DIR"
echo "요약 파일: $OUTPUT_DIR/experiment_results.json"
echo "=========================================="
