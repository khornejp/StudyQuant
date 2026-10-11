"""G3-IDLE-EXTRATREES-4H-r1 (Codex spec 2026-10-11): trade only while both G3 sleeves are strictly idle (open =
pending = signal_active = 0). ExtraTrees regression of the 4h long price return minus actual PESS funding (bps);
directional P&L = side x target - 4 bps. Side mode {LONG, SHORT, BOTH} x |prediction| quantile {0.50, 0.65, 0.80}
chosen by inner blocked OOF. Pure helpers; data and execution in scripts/precompute_rl_allocator.py (g3-idle-et)."""
from __future__ import annotations
import numpy as np

FEATURES = ("ret_1h", "ret_4h", "ret_24h", "ret_7d", "rv_1h", "rv_4h", "rv_24h", "rv_7d", "range_1h", "logvol_1h",
            "taker_share_1h", "oi_chg_1h", "oi_chg_4h", "oi_chg_24h", "oi_z", "global_ls_z", "top_ls_z", "taker_lsr_z",
            "premium_z", "premium_mean_1h", "funding_rate_last", "funding_z90", "funding_age_h", "g3_score_F",
            "g3_score_S", "g3_svi42", "g3_svi180", "g3_sigma_ann")
IDLE_COLS = tuple(f"G3_{s}_{k}" for s in ("LONG", "SHORT") for k in ("open", "pending", "signal_active"))
ET_PARAMS = dict(n_estimators=256, max_depth=6, min_samples_leaf=64, max_features=0.7, criterion="squared_error",
                 random_state=20261012, n_jobs=1)
MODES = ("LONG", "SHORT", "BOTH")
QUANTILES = (0.50, 0.65, 0.80)
HOLD = 240


def idle(frame) -> np.ndarray:
    """Strict idle: every G3 open / pending / signal_active flag is exactly 0 (NaN -> not idle)."""
    return np.all(frame[list(IDLE_COLS)].to_numpy(float) == 0, axis=1)


class Model:
    """ExtraTrees with train-median imputation (medians from the rows it is fitted on)."""

    def __init__(self, X: np.ndarray, y: np.ndarray):
        from sklearn.ensemble import ExtraTreesRegressor
        med = np.nanmedian(X, axis=0)
        self.med = np.where(np.isfinite(med), med, 0.0)
        self.et = ExtraTreesRegressor(**ET_PARAMS).fit(self._fill(X), y)

    def _fill(self, X: np.ndarray) -> np.ndarray:
        return np.where(np.isfinite(X), X, self.med)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.et.predict(self._fill(X))


def sides(pred: np.ndarray, mode: str, thr: float) -> np.ndarray:
    long_, short_ = pred > thr, pred < -thr
    if mode == "LONG":
        short_ = np.zeros_like(short_)
    elif mode == "SHORT":
        long_ = np.zeros_like(long_)
    return long_.astype(int) - short_.astype(int)
