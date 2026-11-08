"""Run the held-out evaluation. Wrapper around evals/eval_qc.py."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evals.eval_qc import run_eval  # noqa: E402

if __name__ == "__main__":
    run_eval()
