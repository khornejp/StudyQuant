# btcusdt_quant v7.18 — Python Virtual Environment

## Setup

### 1. 가상 환경 생성

```bash
# Windows
python -m venv venv_btcusdt

# macOS/Linux
python3 -m venv venv_btcusdt
```

### 2. 가상 환경 활성화

```bash
# Windows (PowerShell)
venv_btcusdt\Scripts\activate

# Windows (CMD)
venv_btcusdt\Scripts\activate.bat

# macOS/Linux
source venv_btcusdt/bin/activate
```

### 3. 의존성 설치

```bash
# 기본 의존성 (필수)
pip install -r requirements.txt

# 개발 의존성 (선택)
pip install -r requirements-dev.txt

# ML 모델 (선택)
pip install -r requirements-ml.txt
```

### 4. 환경 확인

```bash
python -c "import numpy; print('NumPy:', numpy.__version__)"
python -c "import lightgbm; print('LightGBM:', lightgbm.__version__)"
python -c "import pyarrow; print('PyArrow:', pyarrow.__version__)"
```

### 5. 환경 비활성화

```bash
deactivate
```

---

## 프로젝트 구조

```
btcusdt_quant/
├── venv_btcusdt/          # 가상 환경 (gitignore)
├── requirements.txt        # 기본 의존성
├── requirements-dev.txt    # 개발 도구
├── requirements-ml.txt     # ML 모델
├── environment.yml         # Conda 환경 (선택)
└── README.md
```

---

## 주의사항

- **venv_btcusdt/** 디렉토리는 git에 커밋하지 마세요
- **requirements.txt**는 git에 커밋하세요
- NumPy 버전: **1.26.4** (LightGBM/CatBoost 호환성)
- Python 버전: **3.10**

---

## 문제 해결

### NumPy 2.0 충돌

```bash
pip uninstall numpy -y
pip install numpy==1.26.4
```

### LightGBM 설치 실패

```bash
pip install lightgbm --no-deps
pip install numpy==1.26.4 scikit-learn
```

### 가상 환경 재생성

```bash
deactivate
rmdir /s /q venv_btcusdt
python -m venv venv_btcusdt
venv_btcusdt\Scripts\activate
pip install -r requirements.txt
```
