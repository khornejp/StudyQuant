"""One RL training run: python scripts/rl_train_window.py --window W01 --variant S1 --encoder conv --lr 3e-4 --seed 0 [--reward frozen|net] [--smoke]"""
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from btcusdt_quant.rl.train import run_config  # noqa: E402
from btcusdt_quant.sim.rolling import WINDOWS  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--window", required=True)
p.add_argument("--variant", required=True, choices=("S1", "S3", "S4"))
p.add_argument("--encoder", default="conv")
p.add_argument("--lr", type=float, default=3e-4)
p.add_argument("--seed", type=int, default=0)
p.add_argument("--reward", choices=("frozen", "net"), default="frozen")
p.add_argument("--smoke", action="store_true")
p.add_argument("--out-root", default=str(ROOT / "out/k45_rl_r2_48_20261007/rl"))
a = p.parse_args()
w = {x.name: x for x in WINDOWS}[a.window]
out = Path(a.out_root) / a.window / a.reward / f"{a.variant}_{a.encoder}_lr{a.lr:g}_s{a.seed}"
print(json.dumps(run_config(w, a.variant, a.encoder, a.lr, a.seed, out, a.smoke, a.reward), indent=1, default=str))
