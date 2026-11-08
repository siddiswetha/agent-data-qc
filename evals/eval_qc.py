"""Held-out evaluation for the QC system.

Runs the rule-based validator and rubric on the 30 held-out
trajectories and compares against the gold labels. Reports
precision, recall, F1, defect rate, rubric agreement, and
sampling coverage. Writes evals/results.json.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qc_core.rubric import rubric_agreement, rubric_score  # noqa: E402
from qc_core.sampling import stratified_sample  # noqa: E402
from qc_core.validators import validate_trajectory  # noqa: E402


def load_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def run_eval(held_out_path=None):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if held_out_path is None:
        held_out_path = os.path.join(root, "data", "held_out.jsonl")
    rows = load_jsonl(held_out_path)
    tp = fp = fn = tn = 0
    agreements = []
    rubric_totals = []
    for row in rows:
        result = validate_trajectory(row)
        predicted = result["defective"]
        gold = bool(row.get("gold_defective"))
        if predicted and gold:
            tp += 1
        elif predicted and not gold:
            fp += 1
        elif not predicted and gold:
            fn += 1
        else:
            tn += 1
        rubric = rubric_score(row, result)
        agreements.append(rubric_agreement(rubric["scores"], row.get("gold_rubric", {})))
        rubric_totals.append(rubric["total"])
    precision = round(tp / (tp + fp), 3) if (tp + fp) else 0.0
    recall = round(tp / (tp + fn), 3) if (tp + fn) else 0.0
    f1 = round(2 * precision * recall / (precision + recall), 3) if (precision + recall) else 0.0
    gold_defect_rate = round(sum(1 for r in rows if r.get("gold_defective")) / len(rows), 3) if rows else 0.0
    predicted_defect_rate = round((tp + fp) / len(rows), 3) if rows else 0.0
    sampled, coverage = stratified_sample(rows, 0.5, seed=42)
    per_vendor_sampled = {}
    for vendor in sorted({r.get("vendor") for r in rows}):
        per_vendor_sampled[vendor] = sum(1 for r in sampled if r.get("vendor") == vendor)
    results = {
        "held_out_size": len(rows),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "true_negatives": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "gold_defect_rate": gold_defect_rate,
        "predicted_defect_rate": predicted_defect_rate,
        "rubric_agreement_mean": round(sum(agreements) / len(agreements), 3) if agreements else 0.0,
        "rubric_average_total": round(sum(rubric_totals) / len(rubric_totals), 2) if rubric_totals else 0.0,
        "sampling_fraction": 0.5,
        "sampling_coverage": coverage,
        "sampled_count": len(sampled),
        "per_vendor_sampled": per_vendor_sampled,
    }
    out_path = os.path.join(root, "evals", "results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(json.dumps(results, indent=2))
    return results


if __name__ == "__main__":
    run_eval()
