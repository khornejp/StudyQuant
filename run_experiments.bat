@echo off
chcp 65001 >nul
echo ==========================================
echo BTCUSDT Quant v7.18 실험 자동화 배치 파일
echo ==========================================
echo.

REM Python 경로 자동 탐지 (python 또는 python3)
set PYTHON_CMD=python
where python >nul 2>nul
if %errorlevel% neq 0 (
    where python3 >nul 2>nul
    if %errorlevel% equ 0 (
        set PYTHON_CMD=python3
    ) else (
        echo [오류] Python을 찾을 수 없습니다. Python 3.10+이 설치되어 있어야 합니다.
        pause
        exit /b 1
    )
)

echo Python 명령어: %PYTHON_CMD%
%PYTHON_CMD% --version
echo.

REM btcusdt_quant 패키지 확인
%PYTHON_CMD% -c "import btcusdt_quant" >nul 2>nul
if %errorlevel% neq 0 (
    echo [오류] btcusdt_quant 패키지가 설치되지 않았습니다.
    echo 다음 명령어로 설치하세요:
    echo   cd 프로젝트_폴더
    echo   pip install -e .
    pause
    exit /b 1
)

REM 기본 설정
set INPUT_FILE=%~1
set OUTPUT_DIR=%~2

if "%INPUT_FILE%"=="" (
    echo 사용법: run_experiments.bat [데이터_CSV_경로] [출력_폴더]
    echo.
    echo 예시:
    echo   run_experiments.bat artifacts/btcusdt_1m_2024_01_02.csv experiments
    echo   run_experiments.bat data.csv experiments --quick
    echo   run_experiments.bat data.csv experiments --full
    echo   run_experiments.bat data.csv experiments --with-fs
    echo.
    pause
    exit /b 1
)

if "%OUTPUT_DIR%"=="" set OUTPUT_DIR=experiments

echo 입력 데이터: %INPUT_FILE%
echo 출력 폴: %OUTPUT_DIR%
echo.

REM 추가 인자 처리
set EXTRA_ARGS=
if "%~3"=="--quick" set EXTRA_ARGS=--quick
if "%~3"=="--full" set EXTRA_ARGS=--full
if "%~3"=="--with-fs" set EXTRA_ARGS=--with-fs
if "%~3"=="--fs-only" set EXTRA_ARGS=--fs-only

echo 추가 옵션: %EXTRA_ARGS%
echo.
echo 실험 시작... 시간이 걸릴 수 있습니다.
echo ==========================================

%PYTHON_CMD% run_experiments.py --input "%INPUT_FILE%" --output "%OUTPUT_DIR%" %EXTRA_ARGS%

echo.
echo ==========================================
echo 실험 완료!
echo 결과 폴더: %OUTPUT_DIR%
echo 요약 파일: %OUTPUT_DIR%/experiment_results.json
echo ==========================================
pause
