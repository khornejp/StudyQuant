"""A7-RPBT (Codex final spec .superpowers/sdd/rl_allocator/a7_rpbt_spec_2026-10-11.md): population-based training
pieces that do not touch the GPU — genotypes, Latin-hypercube init, exploit mutation, weight transfer, lexicographic
fitness, Romano-Wolf stepdown gate, lr decay, replay projection, atomic checkpoint IO. The run itself lives in
scripts/precompute_rl_allocator.py (smdp-a7)."""
from __future__ import annotations
import copy, hashlib, io, json, math, os
from dataclasses import asdict, dataclass, replace
from pathlib import Path
import numpy as np

INF = float("inf")
BOUNDS = {"idle": (0.005, 0.60), "slope": (0.005, 0.05), "inventory": (0.02, 0.20), "turnover": (0.02, 0.25),
          "lr": (1e-4, 6e-4), "beta_t": (0.001, 0.020), "beta_w": (0.002, 0.050), "half_life": (3.0, 24.0)}
REPLAY_BOUNDS = ((0.15, 0.55), (0.20, 0.45), (0.25, 0.60))       # latest, recent6, earlier
ZERO_GENES = ("idle", "slope", "inventory", "turnover")            # {0} U range
LOG_GENES = ("idle", "inventory", "turnover", "lr", "beta_t", "beta_w", "half_life")
REWARD_GENES = ("idle", "slope", "inventory", "turnover")
N_MUTABLE, N_SENTINEL = 10, 3


@dataclass(frozen=True)
class Genotype:
    name: str
    idle: float
    slope: float
    inventory: float
    turnover: float
    lr: float
    beta_t: float
    beta_w: float
    half_life: float                 # months; INF = no decay
    replay: tuple = (0.50, 0.25, 0.25)
    sentinel: bool = False

    def reward_cfg(self):
        from .smdp_reward import RewardConfig
        slope = 0.0 if self.idle == 0 else self.slope                  # idle 0 -> slope void
        return RewardConfig(idle_bps_per_h=float(self.idle), inventory_bps_per_h=float(self.inventory),
                            turnover_bps=float(self.turnover), f_kind="linear", f_param=float(slope), k_cap_h=20.0)

    def to_json(self) -> dict:
        d = asdict(self)
        d["half_life"] = "inf" if self.half_life == INF else self.half_life
        d["replay"] = list(self.replay)
        return d

    @staticmethod
    def from_json(d: dict) -> "Genotype":
        d = dict(d)
        d["half_life"] = INF if d["half_life"] in ("inf", None) else float(d["half_life"])
        d["replay"] = tuple(d["replay"])
        return Genotype(**d)


SENTINELS = (
    Genotype("RAW", 0.0, 0.0, 0.0, 0.0, 3e-4, 0.00732, 0.020, INF, (0.50, 0.25, 0.25), True),
    Genotype("A6", 0.4167, 0.05, 0.15, 0.25, 3e-4, 0.00732, 0.020, INF, (0.50, 0.25, 0.25), True),
    Genotype("A6b", 0.25, 0.05, 0.15, 0.25, 3e-4, 0.00732, 0.020, INF, (0.50, 0.25, 0.25), True),
)


def project_replay(x) -> tuple:
    """Euclidean-ish projection onto {sum = 1, lo_i <= x_i <= hi_i}: clip, then spread the residual over the free
    coordinates, repeated until feasible."""
    x = np.asarray(x, float)
    lo = np.array([b[0] for b in REPLAY_BOUNDS])
    hi = np.array([b[1] for b in REPLAY_BOUNDS])
    x = np.clip(x, lo, hi)
    for _ in range(20):
        r = 1.0 - x.sum()
        if abs(r) < 1e-12:
            break
        free = (x < hi - 1e-12) if r > 0 else (x > lo + 1e-12)
        if not free.any():
            break
        x[free] += r / free.sum()
        x = np.clip(x, lo, hi)
    return tuple(float(v) for v in x)


def _log_uniform(u, lo, hi):
    return float(math.exp(math.log(lo) + u * (math.log(hi) - math.log(lo))))


def lhs_init(seed: int, n: int = N_MUTABLE) -> list:
    """Latin-hypercube init of the mutable members: per zero-able gene exactly 2/10 members at 0, lr half-life INF for
    2/10, every continuous gene stratified over n strata (log-uniform where the gene is log-scaled)."""
    rng = np.random.default_rng(seed)
    genes = ("idle", "slope", "inventory", "turnover", "lr", "beta_t", "beta_w", "half_life", "r0", "r1", "r2")
    strata = {g: (rng.permutation(n) + rng.random(n)) / n for g in genes}
    zero = {g: set(rng.choice(n, 2, replace=False).tolist()) for g in ZERO_GENES}
    inf_hl = set(rng.choice(n, 2, replace=False).tolist())
    out = []
    for i in range(n):
        v = {}
        for g in ("idle", "inventory", "turnover", "lr", "beta_t", "beta_w"):
            v[g] = _log_uniform(strata[g][i], *BOUNDS[g])
        v["slope"] = BOUNDS["slope"][0] + strata["slope"][i] * (BOUNDS["slope"][1] - BOUNDS["slope"][0])
        for g in ZERO_GENES:
            if i in zero[g]:
                v[g] = 0.0
        hl = INF if i in inf_hl else _log_uniform(strata["half_life"][i], *BOUNDS["half_life"])
        rp = [REPLAY_BOUNDS[k][0] + strata[f"r{k}"][i] * (REPLAY_BOUNDS[k][1] - REPLAY_BOUNDS[k][0]) for k in range(3)]
        out.append(Genotype(f"M{i:02d}", v["idle"], v["slope"], v["inventory"], v["turnover"], v["lr"], v["beta_t"],
                            v["beta_w"], hl, project_replay(rp), False))
    return out


def population(seed: int) -> list:
    return list(SENTINELS) + lhs_init(seed)


def mutate(g: Genotype, rng, allow_replay: bool) -> Genotype:
    """Exploit mutation: each log gene x0.8 / x1.25 with p = 0.5 (clipped to its bounds); slope the same then clipped
    to [0.005, 0.05]; zero toggle p = 0.10 per zero-able gene; half-life INF toggle p = 0.10; replay logits + N(0,
    0.2^2), softmax, bound projection (only when allowed)."""
    d = {k: getattr(g, k) for k in ("idle", "slope", "inventory", "turnover", "lr", "beta_t", "beta_w", "half_life")}
    for k in ("idle", "inventory", "turnover", "lr", "beta_t", "beta_w", "half_life", "slope"):
        if d[k] in (0.0, INF):
            continue
        if rng.random() < 0.5:
            d[k] = float(np.clip(d[k] * (0.8 if rng.random() < 0.5 else 1.25), *BOUNDS[k]))
    for k in ZERO_GENES:
        if rng.random() < 0.10:
            if d[k] == 0.0:
                d[k] = _log_uniform(rng.random(), *BOUNDS[k]) if k != "slope" else float(
                    BOUNDS["slope"][0] + rng.random() * (BOUNDS["slope"][1] - BOUNDS["slope"][0]))
            else:
                d[k] = 0.0
    if rng.random() < 0.10:
        d["half_life"] = _log_uniform(rng.random(), *BOUNDS["half_life"]) if d["half_life"] == INF else INF
    rp = g.replay
    if allow_replay:
        z = np.log(np.asarray(rp)) + rng.normal(0.0, 0.20, 3)
        e = np.exp(z - z.max())
        rp = project_replay(e / e.sum())
    return replace(g, **d, replay=rp)


def reward_changed(a: Genotype, b: Genotype) -> bool:
    return any(getattr(a, k) != getattr(b, k) for k in REWARD_GENES)


def lr_at(g: Genotype, months_since_2022_01: int) -> float:
    if g.half_life == INF:
        return g.lr
    return g.lr * max(0.10, 2.0 ** (-months_since_2022_01 / g.half_life))


def exploit_weights(recipient_model, donor_state: dict, reinit_value: bool, seed: int):
    """Copy donor trunk + target head + wait head into the recipient; re-init the value head when the recipient's reward
    differs from the donor's (reward genes or slope changed). The caller re-creates AdamW (state always reset)."""
    import torch
    sd = recipient_model.state_dict()
    for k, v in donor_state.items():
        if k.startswith("trunk.") or k.startswith("pt.") or k.startswith("pw."):
            sd[k] = v.clone()
        elif k.startswith("v.") and not reinit_value:
            sd[k] = v.clone()
    recipient_model.load_state_dict(sd)
    if reinit_value:
        g = torch.Generator().manual_seed(seed)
        for m in recipient_model.v.modules():
            if isinstance(m, torch.nn.Linear):
                bound = 1.0 / math.sqrt(m.in_features)
                with torch.no_grad():
                    m.weight.uniform_(-bound, bound, generator=g)
                    m.bias.uniform_(-bound, bound, generator=g)
    return recipient_model


# ---------------------------------------------------------------- fitness and the Romano-Wolf gate
def boot_means(x: np.ndarray, block: int, n_boot: int, seed: int) -> np.ndarray:
    """Stationary-bootstrap means (Politis-Romano) of the columns of x [T, K] with shared resampling indices."""
    x = np.asarray(x, float)
    if x.ndim == 1:
        x = x[:, None]
    T = len(x)
    rng = np.random.default_rng(seed)
    out = np.empty((n_boot, x.shape[1]))
    for c in range(0, n_boot, 500):
        k = min(500, n_boot - c)
        new = rng.random((k, T)) < 1.0 / block
        new[:, 0] = True
        starts = rng.integers(0, T, size=(k, T))
        pos = np.broadcast_to(np.arange(T), (k, T))
        last = np.maximum.accumulate(np.where(new, pos, 0), axis=1)
        idx = (np.take_along_axis(starts, last, axis=1) + pos - last) % T
        out[c:c + k] = x[idx].mean(axis=1)
    return out


def p05(x: np.ndarray, block: int = 60, n_boot: int = 10_000, seed: int = 20261011) -> float:
    return float(np.quantile(boot_means(x, block, n_boot, seed)[:, 0], 0.05))


def fitness(raw_daily: dict, anchor_daily: dict, n_boot: int = 10_000) -> tuple:
    """Lexicographic: (min_cell p05(raw daily), min_cell p05(raw - own anchor), min_cell cumulative raw, mean_cell
    cumulative raw). Inputs: cell -> daily raw net4 arrays (candidate / own anchor)."""
    cells = sorted(raw_daily)
    f1 = min(p05(raw_daily[c], n_boot=n_boot) for c in cells)
    f2 = min(p05(raw_daily[c] - anchor_daily[c], n_boot=n_boot) for c in cells)
    cum = [float(np.sum(raw_daily[c])) for c in cells]
    return (f1, f2, min(cum), float(np.mean(cum)))


def romano_wolf(diffs: np.ndarray, block: int = 60, n_boot: int = 10_000, alpha: float = 0.05,
                seed: int = 20261011) -> np.ndarray:
    """Stepdown max-t (Romano-Wolf) for H0_j: mean(diff_j) <= 0, one-sided, on diffs [T, J] with a joint stationary
    bootstrap. Returns a boolean rejection vector."""
    d = np.asarray(diffs, float)
    T, J = d.shape
    m = d.mean(0)
    bm = boot_means(d, block, n_boot, seed)
    se = bm.std(0, ddof=1)
    se = np.where(se > 0, se, np.inf)
    t = m / se
    tb = (bm - m) / se
    rej = np.zeros(J, bool)
    order = np.argsort(-t)
    active = np.ones(J, bool)
    for j in order:
        crit = np.quantile(tb[:, active].max(1), 1 - alpha)
        if t[j] > crit:
            rej[j] = True
            active[j] = False
            if not active.any():
                break
        else:
            break
    return rej


def exploit_plan(fit: dict, genos: dict, daily: dict, n_boot: int = 10_000, seed: int = 20261011) -> dict:
    """Top-3 donors (any member, sentinels included) and bottom-3 mutable recipients by fitness; every donor x recipient x
    cell transfer is one hypothesis (paired daily raw net4 donor - recipient), jointly Romano-Wolf corrected at block 60;
    a transfer needs all 6 cells rejected plus p05 > 0 of the mean difference at blocks 20 and 120 for every cell. Each
    recipient takes the best-ranked significant donor; none -> no exploit for that recipient."""
    ranked = sorted(fit, key=lambda k: fit[k], reverse=True)
    donors = ranked[:3]
    recips = [k for k in reversed(ranked) if not genos[k].sentinel][:3]
    cells = sorted(next(iter(daily.values())))
    pairs = [(d_, r_) for r_ in recips for d_ in donors if d_ != r_]
    cols, keys = [], []
    for d_, r_ in pairs:
        for c in cells:
            cols.append(daily[d_][c] - daily[r_][c])
            keys.append((d_, r_, c))
    plan = {"donors": donors, "recipients": recips, "transfers": {}, "hypotheses": len(keys)}
    if not keys:
        return plan
    D = np.column_stack(cols)
    rej = romano_wolf(D, 60, n_boot, 0.05, seed)
    p20 = np.quantile(boot_means(D, 20, n_boot, seed + 1), 0.05, axis=0)
    p120 = np.quantile(boot_means(D, 120, n_boot, seed + 2), 0.05, axis=0)
    ok = {}
    for j, (d_, r_, c) in enumerate(keys):
        ok.setdefault((d_, r_), []).append(bool(rej[j] and p20[j] > 0 and p120[j] > 0))
    for r_ in recips:
        for d_ in donors:
            if d_ != r_ and all(ok.get((d_, r_), [False])):
                plan["transfers"][r_] = d_
                break
    plan["detail"] = {f"{d_}->{r_}": v for (d_, r_), v in ok.items()}
    return plan


# ---------------------------------------------------------------- atomic IO
def atomic_write_bytes(path: Path, data: bytes) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    return hashlib.sha256(data).hexdigest()


def atomic_json(path: Path, obj) -> str:
    return atomic_write_bytes(path, (json.dumps(obj, indent=2, default=str) + "\n").encode("utf-8"))


def save_checkpoint(path: Path, state: dict, hashes: dict) -> str:
    """Full member checkpoint (model, optimizer, genotype, lr month, decisions, RNG states, eval ledger, hashes, last
    committed month) written atomically; returns its sha256."""
    import torch
    buf = io.BytesIO()
    torch.save({**state, "hashes": hashes}, buf)
    return atomic_write_bytes(path, buf.getvalue())


def load_checkpoint(path: Path, hashes: dict) -> dict:
    """Refuses a checkpoint whose recorded code / input / spec hashes differ from the current ones."""
    import torch
    st = torch.load(path, map_location="cpu", weights_only=False)
    if st.get("hashes") != hashes:
        raise RuntimeError(f"checkpoint hash mismatch: {path}")
    return st


def copy_genotype(g: Genotype, name: str) -> Genotype:
    return replace(copy.deepcopy(g), name=name)
