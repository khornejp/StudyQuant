"""Minimal AST mutation test for btcusdt_quant/sim (spec A3).

mutmut 3 refuses to run on native Windows, so this applies one operator/constant
mutation at a time, runs the sim test suite, and restores the file.
Usage: python scripts/sim_mutation.py [--out PATH]
"""
from __future__ import annotations
import argparse, ast, copy, json, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ["btcusdt_quant/sim/orders.py", "btcusdt_quant/sim/reference.py", "btcusdt_quant/sim/schema.py"]
TEST_CMD = [sys.executable, "-m", "pytest", "tests/sim", "-x", "-q", "-p", "no:cacheprovider",
            "-m", "not slow", "--basetemp", str(ROOT / ".superpowers/mutation_pt")]
SWAP = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt, ast.Eq: ast.NotEq,
        ast.NotEq: ast.Eq, ast.Is: ast.IsNot, ast.IsNot: ast.Is, ast.In: ast.NotIn, ast.NotIn: ast.In,
        ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult, ast.And: ast.Or, ast.Or: ast.And}


def _sites(tree: ast.Module) -> list[tuple[int, str, int | None]]:
    """(walk position, kind, operator index) for every mutable node."""
    docstrings = {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)}
    sites = []
    for position, node in enumerate(ast.walk(tree)):
        if isinstance(node, ast.Compare):
            sites += [(position, "ops", k) for k, op in enumerate(node.ops) if type(op) in SWAP]
        elif isinstance(node, (ast.BinOp, ast.BoolOp)) and type(node.op) in SWAP:
            sites.append((position, "op", None))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.Not)):
            sites.append((position, "unary", None))
        elif isinstance(node, ast.Constant) and type(node.value) in (int, float) and id(node) not in docstrings:
            sites.append((position, "const", None))
    return sites


def mutants(tree: ast.Module):
    """Yield (description, mutated tree), one change per mutant."""
    for position, kind, k in _sites(tree):
        clone = copy.deepcopy(tree)
        nodes = list(ast.walk(clone))
        node = nodes[position]
        if kind == "ops":
            old = type(node.ops[k]); node.ops[k] = SWAP[old](); desc = f"{old.__name__}->{SWAP[old].__name__}"
        elif kind == "op":
            old = type(node.op); node.op = SWAP[old](); desc = f"{old.__name__}->{SWAP[old].__name__}"
        elif kind == "const":
            desc = f"{node.value!r}->{node.value + 1!r}"; node.value = node.value + 1
        else:
            desc = f"drop {type(node.op).__name__}"
            parent = next(p for p in nodes for _, v in ast.iter_fields(p)
                          if v is node or (isinstance(v, list) and any(x is node for x in v)))
            for field, value in ast.iter_fields(parent):
                if value is node:
                    setattr(parent, field, node.operand)
                elif isinstance(value, list):
                    value[:] = [node.operand if x is node else x for x in value]
        yield f"line {node.lineno}: {desc}", clone


def run_tests(timeout: int, target: Path | None = None) -> str:
    if target is not None:   # drop the stale bytecode of the mutated module only (pyc mtime has 1 s resolution)
        for pyc in (target.parent / "__pycache__").glob(f"{target.stem}.*.pyc"):
            pyc.unlink()
    try:
        result = subprocess.run(TEST_CMD, cwd=ROOT, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return "killed_timeout"
    return "survived" if result.returncode == 0 else "killed"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / "out/sim_mutation_20261007/mutation.json"))
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--files", nargs="*", default=TARGETS)
    args = parser.parse_args()
    if run_tests(args.timeout) != "survived":
        raise SystemExit("baseline test suite fails; fix before mutation testing")
    report = {"started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "files": {}}
    for rel in args.files:
        path = ROOT / rel
        source = path.read_text(encoding="utf-8")
        backup = path.with_suffix(".py.mutation_backup")
        if backup.exists():
            raise SystemExit(f"{backup} exists: a previous run was killed; restore it first")
        backup.write_text(source, encoding="utf-8")
        results = []
        try:
            for desc, mutated in mutants(ast.parse(source)):
                path.write_text(ast.unparse(ast.fix_missing_locations(mutated)), encoding="utf-8")
                status = run_tests(args.timeout, path)
                results.append({"mutant": desc, "status": status})
                print(rel, desc, status, flush=True)
        finally:
            path.write_text(source, encoding="utf-8")
            for pyc in (path.parent / "__pycache__").glob(f"{path.stem}.*.pyc"):
                pyc.unlink()
            backup.unlink()
        killed = sum(r["status"] != "survived" for r in results)
        report["files"][rel] = {"total": len(results), "killed": killed,
                                "score": killed / len(results) if results else None,
                                "survived": [r["mutant"] for r in results if r["status"] == "survived"],
                                "results": results}
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    for rel, value in report["files"].items():
        print(rel, value["killed"], "/", value["total"], "survived:", value["survived"])


if __name__ == "__main__":
    main()
