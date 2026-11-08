"""Command-line interface for Agent Training Data Quality Control.

Commands:
  generate   build the synthetic data set (120 trajectories, 90 dev / 30 held out)
  validate   validate trajectories from a JSONL file
  audit      audit a JSONL file: sampling, defect rate, rubric, per-vendor report
  eval       run the held-out evaluation and print precision / recall / F1
  canary     run the canary check from scripts/canary.py
  flags      show the current feature flags
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evals.eval_qc import load_jsonl, run_eval  # noqa: E402
from qc_core.flags import load_flags  # noqa: E402
from qc_core.validators import validate_trajectory  # noqa: E402
from services.auditor.app import build_report  # noqa: E402


def cmd_generate(_args):
    from scripts.generate_data import main as gen_main
    gen_main()


def cmd_validate(args):
    rows = load_jsonl(args.file)
    flagged = 0
    for row in rows:
        result = validate_trajectory(row)
        if result["defective"]:
            flagged += 1
        print(json.dumps({"trajectory_id": row.get("trajectory_id"), "defective": result["defective"], "anomaly_score": result["anomaly_score"], "failure_modes": result["failure_modes"]}))
    print(f"Validated {len(rows)} trajectories, {flagged} flagged as defective.")


def cmd_audit(args):
    rows = load_jsonl(args.file)
    report = build_report(args.batch_id, rows, sample_fraction=args.sample_fraction, seed=args.seed)
    print(json.dumps({k: v for k, v in report.items() if k != "results"}, indent=2))
    print(f"Sampled {report['sampled']} of {report['total_trajectories']} (coverage {report['sampling_coverage']}). Defect rate {report['defect_rate']} (Wilson {report['wilson_low']}-{report['wilson_high']}).")


def cmd_eval(_args):
    run_eval()


def cmd_canary(_args):
    from scripts.canary import main as canary_main
    canary_main()


def cmd_flags(_args):
    print(json.dumps(load_flags(), indent=2))


def main():
    parser = argparse.ArgumentParser(description="Agent Training Data Quality Control")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("generate")
    p = sub.add_parser("validate")
    p.add_argument("file")
    p = sub.add_parser("audit")
    p.add_argument("file")
    p.add_argument("--batch-id", default="BATCH-CLI")
    p.add_argument("--sample-fraction", type=float, default=0.5)
    p.add_argument("--seed", type=int, default=42)
    sub.add_parser("eval")
    sub.add_parser("canary")
    sub.add_parser("flags")
    args = parser.parse_args()
    {"generate": cmd_generate, "validate": cmd_validate, "audit": cmd_audit, "eval": cmd_eval, "canary": cmd_canary, "flags": cmd_flags}[args.command](args)


if __name__ == "__main__":
    main()
