"""Five-dimension human-designed rubric. Rule-based only.

Each dimension is scored 0, 1, or 2 by a written rule a human
reviewer can apply without a model. Total is 0-10. Pass is 8
or more, and no dimension may be 0 for a pass.
"""
DIMENSIONS = [
    "task_realism",
    "instruction_clarity",
    "trajectory_coherence",
    "tool_use_validity",
    "outcome_verifiability",
]

RUBRIC_RULES = {
    "task_realism": "2 = plausible real request doable with the allowed tools; 1 = plausible but contrived; 0 = impossible or not a real request.",
    "instruction_clarity": "2 = complete instruction: task, input, and answer form; 1 = understandable but missing one detail; 0 = empty, too short, or ambiguous.",
    "trajectory_coherence": "2 = steps follow logically to the outcome; 1 = one gap or odd step; 0 = steps do not lead to the outcome or order is impossible.",
    "tool_use_validity": "2 = every tool is allowed and every argument is present and correct; 1 = one minor misuse; 0 = unknown tool or missing/wrong arguments.",
    "outcome_verifiability": "2 = one specific checkable result; 1 = partly checkable; 0 = empty or too vague to check.",
}

PASS_TOTAL = 8


def rubric_score(traj, validation=None):
    """Score a trajectory on the five dimensions. Returns dict with scores and total."""
    from .validators import validate_trajectory

    if validation is None:
        validation = validate_trajectory(traj)
    defects = validation["defects"]
    codes = [d["code"] for d in defects]
    instruction = (traj.get("instruction") or "") if isinstance(traj, dict) else ""
    outcome = (traj.get("expected_outcome") or "") if isinstance(traj, dict) else ""
    steps = traj.get("steps") or [] if isinstance(traj, dict) else []

    # Task realism.
    if traj.get("task_type") not in ("file_search", "arithmetic", "fact_lookup", "data_sort", "data_filter", "summary"):
        realism = 0
    elif "unrealistic_task" in codes:
        realism = 0
    elif len(instruction.strip()) < 20:
        realism = 1
    else:
        realism = 2

    # Instruction clarity.
    if len(instruction.strip()) < 10 or "unclear_instruction" in codes:
        clarity = 0
    elif len(instruction.strip()) < 30:
        clarity = 1
    else:
        clarity = 2

    # Trajectory coherence.
    coherence_defects = [c for c in codes if c in ("impossible_order", "missing_steps", "empty_steps", "duplicate_step")]
    if len(coherence_defects) >= 2 or len(steps) < 2:
        coherence = 0
    elif len(coherence_defects) == 1:
        coherence = 1
    else:
        coherence = 2

    # Tool-use validity.
    tool_defects = [c for c in codes if c in ("invalid_tool", "invalid_arguments")]
    if len(tool_defects) >= 2:
        tool_validity = 0
    elif len(tool_defects) == 1:
        tool_validity = 1
    else:
        tool_validity = 2

    # Outcome verifiability.
    if "unverifiable_outcome" in codes or len(outcome.strip()) < 3:
        verifiability = 0
    elif len(outcome.strip()) < 10:
        verifiability = 1
    else:
        verifiability = 2

    scores = {
        "task_realism": realism,
        "instruction_clarity": clarity,
        "trajectory_coherence": coherence,
        "tool_use_validity": tool_validity,
        "outcome_verifiability": verifiability,
    }
    total = sum(scores.values())
    return {"scores": scores, "total": total, "passed": total >= PASS_TOTAL and 0 not in scores.values()}


def rubric_agreement(predicted, gold):
    """Fraction of dimensions where predicted and gold scores match exactly."""
    if not gold:
        return 0.0
    matches = sum(1 for dim in DIMENSIONS if predicted.get(dim) == gold.get(dim))
    return round(matches / len(DIMENSIONS), 3)
