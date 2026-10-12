"""A6 SMDP reward (Codex A6): reward = net4 - idle - inventory - turnover, every term configured (no hard-coded
values; the idle / inventory magnitudes await the user's decision and default to UNSET).

Per 5-minute block b of a decision step (minutes i+1 .. j):
  idle_b      = idle_bps_per_h / 12 x m(t_b) x f(k_b) x I(|executed_b| < 0.125)
  inventory_b = inventory_bps_per_h / 12 x |executed_b|
  turnover    = turnover_bps x |d target| (first block of the step)
m(t) = clip(RV24h(t) / RV_ref(t), m_lo, m_hi), RV_ref = expanding past median of RV24h fixed per UTC month
(maker_kernel.rv_ref_monthly); k = consecutive flat hours, reset after 60 consecutive executed non-flat minutes
(kernel kpath); f(k) is an increasing function chosen by f_kind / f_param. State is taken at each block's last minute.
Discounting inside the step: gamma(5 m x b) (maker_kernel.gamma); gamma(d) is returned for the SMDP GAE."""
from __future__ import annotations
from dataclasses import asdict, dataclass
import numpy as np
from . import maker_kernel as MK

UNSET = None


@dataclass(frozen=True)
class RewardConfig:
    idle_bps_per_h: float | None = UNSET
    inventory_bps_per_h: float | None = UNSET
    turnover_bps: float | None = UNSET
    f_kind: str = "linear"                 # "const" | "linear" | "sqrt" | "log1p"
    f_param: float | None = UNSET
    k_cap_h: float | None = None           # f(k) uses min(k, k_cap_h) when set
    m_lo: float = 0.25
    m_hi: float = 4.0
    quadratic_inventory: bool = False

    def is_set(self) -> bool:
        base = all(v is not None for v in (self.idle_bps_per_h, self.inventory_bps_per_h, self.turnover_bps))
        return base and (self.f_kind == "const" or self.f_param is not None)

    def values(self) -> dict:
        return asdict(self)


def f_of_k(k_hours: np.ndarray, cfg: RewardConfig) -> np.ndarray:
    p = 0.0 if cfg.f_param is None else float(cfg.f_param)
    if cfg.k_cap_h is not None:
        k_hours = np.minimum(k_hours, float(cfg.k_cap_h))
    if cfg.f_kind == "const":
        return np.ones_like(k_hours)
    if cfg.f_kind == "linear":
        return 1.0 + p * k_hours
    if cfg.f_kind == "sqrt":
        return 1.0 + p * np.sqrt(k_hours)
    if cfg.f_kind == "log1p":
        return 1.0 + p * np.log1p(k_hours)
    raise ValueError(f"unknown f_kind {cfg.f_kind!r}")


def m_of_t(rv: np.ndarray, rv_ref: np.ndarray, cfg: RewardConfig) -> np.ndarray:
    with np.errstate(invalid="ignore", divide="ignore"):
        x = rv / rv_ref
    return np.clip(np.where(np.isfinite(x), x, 1.0), cfg.m_lo, cfg.m_hi)


def block_terms(net_b, u_b, k_b, m_b, d_target: float, cfg: RewardConfig, require_set: bool = True) -> dict:
    """Vectorized terms from per-block arrays (net4 sum, executed U, k minutes, m) of one step."""
    if require_set and not cfg.is_set():
        raise ValueError("reward magnitudes are UNSET (idle / inventory await the user's decision)")
    z = lambda v: 0.0 if v is None else float(v)  # noqa: E731  (diagnostic runs with unset values report 0)
    nb = len(net_b)
    flat = np.abs(u_b) < MK.FLAT_ABS
    idle = z(cfg.idle_bps_per_h) / 12.0 * m_b * f_of_k(np.asarray(k_b, float) / 60.0, cfg) * flat
    inv = z(cfg.inventory_bps_per_h) / 12.0 * ((m_b * m_b * u_b * u_b) if cfg.quadratic_inventory
                                               else np.abs(u_b))
    turn = np.zeros(nb)
    if nb:
        turn[0] = z(cfg.turnover_bps) * d_target
    r = net_b - idle - inv - turn
    disc = np.array([MK.gamma(5.0 * b) for b in range(nb)])
    return {"net4": float(np.sum(net_b)), "idle": float(idle.sum()), "inventory": float(inv.sum()),
            "turnover": float(turn.sum()), "reward": float(r.sum()), "reward_discounted": float((disc * r).sum()),
            "blocks": int(nb), "flat_blocks": int(flat.sum()), "m_mean": float(m_b.mean()) if nb else None,
            "k_hours_end": float(k_b[-1] / 60.0) if nb else None, "reward_values_set": bool(cfg.is_set())}


def step_reward(pnl, upath, kpath, mpath, i: int, j: int, d_target: float, cfg: RewardConfig,
                require_set: bool = True) -> dict:
    """Scalar-kernel step (minute arrays): blocks of 5 minutes over i+1 .. j."""
    minutes = max(j - i, 0)
    nb = (minutes + 4) // 5
    if nb:
        seg = pnl[i + 1:j + 1]
        net = np.add.reduceat(seg, np.arange(0, len(seg), 5))
        end = np.minimum(i + 5 * (np.arange(nb) + 1), j)
    else:
        net, end = np.zeros(0), np.zeros(0, dtype=int)
    out = block_terms(net, upath[end], kpath[end], mpath[end], d_target, cfg, require_set)
    out["gamma_d"] = MK.gamma(float(j - i))
    return out


# A6 user choice (option 3, 2026-10-11): idle 0.4167 bps per flat hour (10 bps/day at median volatility), f(k) = 1 +
# 0.05 min(k, 20) (x2 after 20 flat hours), inventory 0.15 bps/h x |U|, turnover 0.25 bps x |d target|
A6_REWARD = RewardConfig(idle_bps_per_h=0.4167, inventory_bps_per_h=0.15, turnover_bps=0.25, f_kind="linear",
                         f_param=0.05, k_cap_h=20.0)

# A6b (user 2026-10-11): idle lowered to 0.25 bps per flat hour (6 bps/day at median volatility); everything else = A6
A6B_REWARD = RewardConfig(idle_bps_per_h=0.25, inventory_bps_per_h=0.15, turnover_bps=0.25, f_kind="linear",
                          f_param=0.05, k_cap_h=20.0)
