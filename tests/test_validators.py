import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qc_core.validators import validate_trajectory


def clean_traj():
    return {
        "trajectory_id": "T-1",
        "vendor": "Vendor-A",
        "task_type": "file_search",
        "instruction": "Find the file named report.txt in the project folder and report its size in lines.",
        "expected_outcome": "File report.txt has 120 lines.",
        "steps": [
            {"step": 1, "tool": "list_files", "args": {"directory": "/project"}, "observation": "Found report.txt."},
            {"step": 2, "tool": "read_file", "args": {"path": "/project/report.txt"}, "observation": "File opened, 120 lines."},
            {"step": 3, "tool": "summarize", "args": {"text": "Contents of report.txt"}, "observation": "Summary: 120 lines."},
        ],
    }


def codes(result):
    return [d["code"] for d in result["defects"]]


def test_clean_trajectory_passes():
    result = validate_trajectory(clean_traj())
    assert result["defective"] is False
    assert result["defects"] == []
    assert result["anomaly_score"] == 0.0


def test_invalid_tool_flagged():
    traj = clean_traj()
    traj["steps"][1]["tool"] = "teleport"
    result = validate_trajectory(traj)
    assert result["defective"] is True
    assert "invalid_tool" in codes(result)


def test_invalid_arguments_flagged():
    traj = clean_traj()
    traj["steps"][0]["args"] = {}
    result = validate_trajectory(traj)
    assert "invalid_arguments" in codes(result)


def test_duplicate_step_flagged():
    traj = clean_traj()
    traj["steps"].insert(2, dict(traj["steps"][1], step=3))
    result = validate_trajectory(traj)
    assert "duplicate_step" in codes(result)


def test_empty_steps_flagged():
    traj = clean_traj()
    traj["steps"] = []
    result = validate_trajectory(traj)
    assert "empty_steps" in codes(result)


def test_missing_steps_flagged():
    traj = clean_traj()
    traj["steps"] = traj["steps"][:1]
    result = validate_trajectory(traj)
    assert "missing_steps" in codes(result)


def test_pii_in_observation_flagged():
    traj = clean_traj()
    traj["steps"][0]["observation"] = "Contact person@example.test for help."
    result = validate_trajectory(traj)
    assert "pii_leak" in codes(result)


def test_answer_leak_flagged():
    traj = clean_traj()
    traj["instruction"] = traj["instruction"] + " The answer is File report.txt has 120 lines."
    result = validate_trajectory(traj)
    assert "answer_leak" in codes(result)


def test_impossible_order_summarize_first():
    traj = clean_traj()
    traj["steps"] = [traj["steps"][2], traj["steps"][0], traj["steps"][1]]
    result = validate_trajectory(traj)
    assert "impossible_order" in codes(result)


def test_unverifiable_outcome_flagged():
    traj = clean_traj()
    traj["expected_outcome"] = "something"
    result = validate_trajectory(traj)
    assert "unverifiable_outcome" in codes(result)


def test_unclear_instruction_flagged():
    traj = clean_traj()
    traj["instruction"] = "Do it."
    result = validate_trajectory(traj)
    assert "unclear_instruction" in codes(result)


def test_calculator_output_without_number_flagged():
    traj = clean_traj()
    traj["steps"] = [
        {"step": 1, "tool": "calculator", "args": {"expression": "2 * 3"}, "observation": "Result is ready."},
        {"step": 2, "tool": "verify", "args": {"claim": "Total is 6"}, "observation": "Verified."},
    ]
    result = validate_trajectory(traj)
    assert "output_mismatch" in codes(result)


def test_anomaly_score_between_zero_and_one():
    result = validate_trajectory(clean_traj())
    assert 0.0 <= result["anomaly_score"] <= 1.0
    bad = clean_traj()
    bad["steps"] = []
    bad["instruction"] = ""
    bad["expected_outcome"] = ""
    result2 = validate_trajectory(bad)
    assert result2["anomaly_score"] > result["anomaly_score"]
    assert result2["anomaly_score"] <= 1.0


def test_non_dict_trajectory_is_defective():
    result = validate_trajectory("not a trajectory")
    assert result["defective"] is True
