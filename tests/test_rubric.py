import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qc_core.rubric import DIMENSIONS, rubric_agreement, rubric_score
from tests.test_validators import clean_traj


def test_clean_trajectory_scores_ten_and_passes():
    result = rubric_score(clean_traj())
    assert result["total"] == 10
    assert result["passed"] is True
    assert set(result["scores"]) == set(DIMENSIONS)


def test_unverifiable_outcome_drops_verifiability_to_zero():
    traj = clean_traj()
    traj["expected_outcome"] = "something"
    result = rubric_score(traj)
    assert result["scores"]["outcome_verifiability"] == 0
    assert result["passed"] is False


def test_invalid_tool_drops_tool_validity():
    traj = clean_traj()
    traj["steps"][1]["tool"] = "teleport"
    result = rubric_score(traj)
    assert result["scores"]["tool_use_validity"] < 2


def test_impossible_order_drops_coherence():
    traj = clean_traj()
    traj["steps"] = [traj["steps"][2], traj["steps"][0], traj["steps"][1]]
    result = rubric_score(traj)
    assert result["scores"]["trajectory_coherence"] == 0


def test_rubric_agreement_exact_match_is_one():
    gold = {"task_realism": 2, "instruction_clarity": 2, "trajectory_coherence": 2, "tool_use_validity": 2, "outcome_verifiability": 2}
    assert rubric_agreement(gold, gold) == 1.0


def test_rubric_agreement_partial():
    predicted = {"task_realism": 2, "instruction_clarity": 2, "trajectory_coherence": 1, "tool_use_validity": 2, "outcome_verifiability": 2}
    gold = {"task_realism": 2, "instruction_clarity": 2, "trajectory_coherence": 2, "tool_use_validity": 2, "outcome_verifiability": 2}
    assert rubric_agreement(predicted, gold) == 0.8
