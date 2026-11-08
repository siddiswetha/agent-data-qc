"""Rule-based validators. No model calls, no outside services.

Every check is a plain rule a human can read and reproduce:
schema, empty steps, duplicates, tool names and arguments,
output checks, step order, personal-data patterns, answer
leaks, and outcome checks. The result is a list of defects
plus a deterministic anomaly score between 0 and 1.
"""
import re

from .failure_modes import classify_failure_modes
from .models import REQUIRED_STEP_FIELDS, REQUIRED_TRAJECTORY_FIELDS, VALID_TOOLS

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\b\d{3}[-. ]\d{3}[-. ]\d{4}\b")
ID_NUMBER_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CARD_RE = re.compile(r"\b\d{4}[- ]\d{4}[- ]\d{4}[- ]\d{4}\b")

VAGUE_OUTCOMES = {"something", "a good result", "the answer", "done", "ok", "good"}

# Weight of each defect in the anomaly score (0-1 scale).
DEFECT_WEIGHTS = {
    "pii_leak": 3,
    "answer_leak": 3,
    "invalid_tool": 2,
    "impossible_order": 2,
    "missing_steps": 2,
    "invalid_arguments": 2,
    "output_mismatch": 1,
    "empty_observation": 1,
    "duplicate_step": 1,
    "unverifiable_outcome": 2,
    "unclear_instruction": 1,
    "unrealistic_task": 2,
    "schema_missing_field": 2,
    "empty_steps": 2,
}


def _defect(code, message, step=None, severity="high"):
    return {"code": code, "message": message, "step": step, "severity": severity}


def _contains_pii(text):
    if not isinstance(text, str):
        return False
    return bool(
        EMAIL_RE.search(text)
        or PHONE_RE.search(text)
        or ID_NUMBER_RE.search(text)
        or CARD_RE.search(text)
    )


def validate_trajectory(traj):
    """Validate one trajectory. Returns a dict with defects, score, verdict."""
    defects = []
    if not isinstance(traj, dict):
        return {
            "trajectory_id": None,
            "defective": True,
            "defects": [_defect("schema_missing_field", "Trajectory is not an object.")],
            "anomaly_score": 1.0,
            "failure_modes": ["incoherent_trajectory"],
        }

    traj_id = traj.get("trajectory_id")
    for field in REQUIRED_TRAJECTORY_FIELDS:
        if field not in traj or traj[field] is None:
            defects.append(_defect("schema_missing_field", f"Missing required field: {field}."))

    instruction = traj.get("instruction", "") or ""
    outcome = traj.get("expected_outcome", "") or ""
    steps = traj.get("steps", [])

    # Instruction checks.
    if not isinstance(instruction, str) or len(instruction.strip()) < 10:
        defects.append(_defect("unclear_instruction", "Instruction is empty or too short to act on."))
    if traj.get("task_type") not in VALID_TOOLS and traj.get("task_type") not in (
        "file_search", "arithmetic", "fact_lookup", "data_sort", "data_filter", "summary",
    ):
        defects.append(_defect("unrealistic_task", f"Unknown task type: {traj.get('task_type')!r}."))

    # Outcome checks.
    if not isinstance(outcome, str) or len(outcome.strip()) < 3:
        defects.append(_defect("unverifiable_outcome", "Expected outcome is empty."))
    elif outcome.strip().lower() in VAGUE_OUTCOMES:
        defects.append(_defect("unverifiable_outcome", "Expected outcome is too vague to check."))

    # Answer leak: instruction already contains the outcome.
    if isinstance(instruction, str) and isinstance(outcome, str) and len(outcome.strip()) >= 5:
        if outcome.strip().lower() in instruction.lower():
            defects.append(_defect("answer_leak", "Instruction contains the expected outcome."))

    # Personal-data patterns in instruction, outcome, and step text.
    for label, text in (("instruction", instruction), ("expected_outcome", outcome)):
        if _contains_pii(text):
            defects.append(_defect("pii_leak", f"Personal-data pattern found in {label}."))

    # Step checks.
    if not isinstance(steps, list):
        defects.append(_defect("schema_missing_field", "Steps field is not a list."))
        steps = []
    if len(steps) == 0:
        defects.append(_defect("empty_steps", "Trajectory has no steps."))
    if 0 < len(steps) < 2:
        defects.append(_defect("missing_steps", "Trajectory has fewer than 2 steps."))

    seen_tools = []
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            defects.append(_defect("schema_missing_field", f"Step {i + 1} is not an object.", step=i + 1))
            continue
        for field in REQUIRED_STEP_FIELDS:
            if field not in step:
                defects.append(
                    _defect("schema_missing_field", f"Step {i + 1} is missing field: {field}.", step=i + 1)
                )
        tool = step.get("tool")
        args = step.get("args", {})
        obs = step.get("observation", "")
        if tool not in VALID_TOOLS:
            defects.append(_defect("invalid_tool", f"Step {i + 1} uses unknown tool: {tool!r}.", step=i + 1))
        else:
            if not isinstance(args, dict):
                defects.append(
                    _defect("invalid_arguments", f"Step {i + 1} args are not an object.", step=i + 1)
                )
            else:
                for required in VALID_TOOLS[tool]:
                    if required not in args or args[required] in (None, ""):
                        defects.append(
                            _defect(
                                "invalid_arguments",
                                f"Step {i + 1} tool {tool} is missing argument: {required}.",
                                step=i + 1,
                            )
                        )
            # Calculator output must contain a number.
            if tool == "calculator" and isinstance(obs, str) and not re.search(r"\d", obs):
                defects.append(
                    _defect("output_mismatch", f"Step {i + 1} calculator output has no number.", step=i + 1)
                )
        if isinstance(obs, str) and obs.strip() == "":
            defects.append(_defect("empty_observation", f"Step {i + 1} has an empty observation.", step=i + 1))
        if isinstance(obs, str) and _contains_pii(obs):
            defects.append(_defect("pii_leak", f"Personal-data pattern in step {i + 1} observation.", step=i + 1))
        # Duplicate consecutive step: same tool and same args.
        key = (tool, tuple(sorted((args or {}).items())) if isinstance(args, dict) else None)
        if seen_tools and seen_tools[-1] == key:
            defects.append(_defect("duplicate_step", f"Step {i + 1} repeats the previous step exactly.", step=i + 1))
        seen_tools.append(key)

    # Impossible order rules.
    if steps and isinstance(steps[0], dict):
        first_tool = steps[0].get("tool")
        if first_tool in ("summarize", "verify"):
            defects.append(
                _defect("impossible_order", f"First step is {first_tool}, but there is nothing to summarise or verify yet.", step=1)
            )
    tool_names = [s.get("tool") for s in steps if isinstance(s, dict)]
    for tool in ("sort_data", "filter_data"):
        if tool in tool_names:
            idx = tool_names.index(tool)
            earlier = tool_names[:idx]
            if not any(t in earlier for t in ("read_file", "list_files", "search")):
                defects.append(
                    _defect("impossible_order", f"{tool} runs before any data was gathered.", step=idx + 1)
                )
    if "summarize" in tool_names:
        idx = tool_names.index("summarize")
        earlier = tool_names[:idx]
        if not any(t in earlier for t in ("read_file", "search")):
            defects.append(
                _defect("impossible_order", "Summarise runs before any content was gathered.", step=idx + 1)
            )

    # Deduplicate identical defects, keeping first occurrence.
    seen = set()
    unique = []
    for d in defects:
        key = (d["code"], d["message"], d["step"])
        if key not in seen:
            seen.add(key)
            unique.append(d)
    defects = unique

    total_weight = sum(DEFECT_WEIGHTS.get(d["code"], 1) for d in defects)
    anomaly_score = round(min(1.0, total_weight / 10.0), 3)

    return {
        "trajectory_id": traj_id,
        "defective": len(defects) > 0,
        "defects": defects,
        "anomaly_score": anomaly_score,
        "failure_modes": classify_failure_modes(defects),
    }
