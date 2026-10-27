"""Run every mandatory demonstration through compilation, target
reduction, and observation, and compare with the expected answers.

Usage, from assigns/06:
    python3 -B MySolution/demo.py [--exec-budget N] [--obs-budget N]
                                  [--out-dir DIR]

Each generated pure term is saved to DIR/DEMO-xx.txt (default
MySolution/generated/). Exits with status 1 if any demo does not match.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from examples import DEMOS, EXHAUSTED
from evaluator import Completed
from observers import Decoded, Malformed
from pipeline import EXEC_BUDGET, OBS_BUDGET, DemoReport, run_demo
from source import d0exp_pretty
from target import Lam, App, pretty

DEFAULT_OUT_DIR = Path(__file__).resolve().parent / "generated"


def show_answer(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, tuple):
        return "(" + ", ".join(show_answer(v) for v in value) + ")"
    return str(value)


def node_count(term) -> int:
    pending, count = [term], 0
    while pending:
        node = pending.pop()
        count += 1
        if isinstance(node, Lam):
            pending.append(node.body)
        elif isinstance(node, App):
            pending.extend((node.fn, node.arg))
    return count


def save_term(report: DemoReport, out_dir: Path) -> Path:
    path = out_dir / f"{report.demo.id}.txt"
    path.write_text(f"# {report.demo.id}: {report.demo.notation}\n"
                    f"# source: {d0exp_pretty(report.demo.source)}\n"
                    f"# {node_count(report.target):,} nodes\n"
                    f"{pretty(report.target)}\n")
    return path


def describe(report: DemoReport, saved: Path) -> list[str]:
    demo = report.demo
    lines = [f"{demo.id}  {demo.notation}",
             f"  source:       {d0exp_pretty(demo.source)}",
             f"  target:       {os.path.relpath(saved)} "
             f"({node_count(report.target):,} nodes)"]

    if isinstance(report.execution, Completed):
        lines.append(f"  execution:    completed in {report.execution.steps:,} steps")
    else:
        lines.append(f"  execution:    budget exhausted after {report.execution.steps:,} "
                     "steps (not a proof of nontermination)")

    match report.observation:
        case None:
            lines.append("  observation:  not run (execution did not complete)")
        case Decoded(_, steps, _):
            lines.append(f"  observation:  decoded as {demo.kind} in {steps:,} steps")
        case Malformed(reason, steps):
            lines.append(f"  observation:  malformed after {steps:,} steps: {reason}")
        case _:
            lines.append(f"  observation:  budget exhausted after "
                         f"{report.observation.steps:,} steps")

    decoded = (show_answer(report.observation.value)
               if isinstance(report.observation, Decoded) else "-")
    expected = ("execution budget exhausted" if demo.expected is EXHAUSTED
                else show_answer(demo.expected))
    source = (show_answer(report.source_answer) if report.source_ran
              else "not run (expected to exhaust the budget)")
    lines += [f"  decoded:      {decoded}",
              f"  expected:     {expected}",
              f"  source eval:  {source}",
              f"  result:       {'PASS' if report.passed else 'FAIL'}"]
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--exec-budget", type=int, default=EXEC_BUDGET)
    parser.add_argument("--obs-budget", type=int, default=OBS_BUDGET)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("Extended LAMBDA -> pure lambda-calculus: demonstrations")
    print(f"  execution budget:   {args.exec_budget:,} beta-value steps")
    print(f"  observation budget: {args.obs_budget:,} beta-value steps")
    print(f"  generated terms:    {os.path.relpath(args.out_dir)}/")
    print()

    passed = 0
    for demo in DEMOS:
        report = run_demo(demo, args.exec_budget, args.obs_budget)
        saved = save_term(report, args.out_dir)
        print("\n".join(describe(report, saved)))
        print()
        passed += report.passed

    print(f"{passed} of {len(DEMOS)} demos match their expected results")
    return 0 if passed == len(DEMOS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
