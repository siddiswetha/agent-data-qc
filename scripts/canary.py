"""Canary check for the validator.

Routes a small, deterministic share of held-out trajectories
(the canary_percent from flags.json) through validation and
compares the defect rate on the canary slice with the rate on
the rest. A large gap is a warning that the new path behaves
differently; it does not by itself prove a defect.
"""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evals.eval_qc import load_jsonl  # noqa: E402
from qc_core.flags import load_flags  # noqa: E402
from qc_core.validators import validate_trajectory  # noqa: E402


def in_canary(trajectory_id, percent):
    digest = int(hashlib.sha256(trajectory_id.encode("utf-8")).hexdigest(), 16)
    return (digest % 100) < percent


def main():
    flags = load_flags()
    percent = int(flags.get("canary_percent", 10))
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rows = load_jsonl(os.path.join(root, "data", "held_out.jsonl"))
    canary = [r for r in rows if in_canary(r["trajectory_id"], percent)]
    rest = [r for r in rows if not in_canary(r["trajectory_id"], percent)]
    def rate(subset):
        if not subset:
            return 0.0
        flagged = sum(1 for r in subset if validate_trajectory(r)["defective"])
        return round(flagged / len(subset), 3)
    report = {
        "canary_percent": percent,
        "canary_size": len(canary),
        "rest_size": len(rest),
        "canary_defect_rate": rate(canary),
        "rest_defect_rate": rate(rest),
    }
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    main()
