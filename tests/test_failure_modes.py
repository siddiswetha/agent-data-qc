import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qc_core.failure_modes import FAILURE_MODES, classify_failure_modes, mode_for_defect


def test_taxonomy_has_at_least_eight_modes():
    assert len(FAILURE_MODES) >= 8


def test_every_mode_has_description_cause_and_fix():
    for mode, info in FAILURE_MODES.items():
        assert info["description"], mode
        assert info["typical_cause"], mode
        assert info["fix"], mode


def test_mode_for_known_defect():
    assert mode_for_defect("pii_leak") == "pii_leak"
    assert mode_for_defect("invalid_tool") == "invalid_tool"
    assert mode_for_defect("answer_leak") == "answer_leak"


def test_mode_for_unknown_defect_defaults_to_incoherent():
    assert mode_for_defect("no_such_code") == "incoherent_trajectory"


def test_classify_returns_sorted_distinct_modes():
    defects = [
        {"code": "pii_leak"},
        {"code": "invalid_tool"},
        {"code": "pii_leak"},
    ]
    assert classify_failure_modes(defects) == ["invalid_tool", "pii_leak"]


def test_classify_empty_defects_is_empty():
    assert classify_failure_modes([]) == []
