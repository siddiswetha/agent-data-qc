"""Failure-mode taxonomy for defective trajectories.

Twelve modes. Each mode has a plain description, a typical
cause, and an actionable fix a vendor can apply. This is the
shared language used by the validator, the auditor, and the
per-vendor feedback report.
"""

FAILURE_MODES = {
    "missing_steps": {
        "description": "Trajectory has no steps, or too few steps to reach the outcome.",
        "typical_cause": "Generation stopped early, or steps were dropped in export.",
        "fix": "Regenerate the trajectory and require at least 3 steps before the final step.",
    },
    "duplicate_step": {
        "description": "The same tool call with the same arguments appears twice in a row.",
        "typical_cause": "Generator looped, or a retry was recorded as a new step.",
        "fix": "Deduplicate consecutive identical calls; record retries as one step with a retry note.",
    },
    "invalid_tool": {
        "description": "A step uses a tool name that is not in the allowed tool list.",
        "typical_cause": "Vendor used a tool name from a different task family.",
        "fix": "Use only the allowed tool list in the task specification.",
    },
    "invalid_arguments": {
        "description": "A step is missing a required argument, or an argument has the wrong type.",
        "typical_cause": "Argument schema was not checked before the step was written.",
        "fix": "Validate every step against the tool argument schema before saving.",
    },
    "output_mismatch": {
        "description": "A step observation is empty, or does not match what the tool should return.",
        "typical_cause": "Observation was not captured, or a placeholder was left in place.",
        "fix": "Capture the real tool output for every step; reject empty observations.",
    },
    "impossible_order": {
        "description": "Steps are in an order that cannot work, for example summarising before searching.",
        "typical_cause": "Steps were shuffled, or a step that depends on an earlier result came first.",
        "fix": "Order steps by dependency: gather data first, then transform, then summarise or verify last.",
    },
    "pii_leak": {
        "description": "A step, instruction, or outcome contains personal data such as an email, phone number, or ID number.",
        "typical_cause": "Real-looking example data was used instead of synthetic placeholders.",
        "fix": "Replace all personal data with clearly synthetic placeholders such as user@example.test.",
    },
    "answer_leak": {
        "description": "The instruction already contains the expected outcome, so the task gives away its own answer.",
        "typical_cause": "The expected outcome was copied into the instruction during generation.",
        "fix": "Rewrite the instruction so it states the task only, never the answer.",
    },
    "incoherent_trajectory": {
        "description": "Steps do not form a logical path from the instruction to the outcome.",
        "typical_cause": "Steps from different tasks were mixed, or a middle step is missing.",
        "fix": "Check that each step follows from the previous one and leads to the stated outcome.",
    },
    "unverifiable_outcome": {
        "description": "The expected outcome is empty or too vague to check, so a grader cannot tell if the agent succeeded.",
        "typical_cause": "Outcome was written as a general phrase instead of a specific result.",
        "fix": "Write the outcome as one specific, checkable result, for example a file name or a number.",
    },
    "unclear_instruction": {
        "description": "The instruction is empty, too short, or ambiguous about what the agent should do.",
        "typical_cause": "Instruction was truncated, or it assumes context the agent does not have.",
        "fix": "Write a complete instruction with the task, the input, and the expected form of the answer.",
    },
    "unrealistic_task": {
        "description": "The task is not a plausible real task, or it asks for something impossible.",
        "typical_cause": "Task was invented without checking whether a real user would ask for it.",
        "fix": "Base each task on a plausible real request and check that it can be done with the allowed tools.",
    },
}

# Defect code (from the validator) -> failure mode.
DEFECT_TO_MODE = {
    "schema_missing_field": "incoherent_trajectory",
    "missing_steps": "missing_steps",
    "empty_steps": "missing_steps",
    "duplicate_step": "duplicate_step",
    "invalid_tool": "invalid_tool",
    "invalid_arguments": "invalid_arguments",
    "output_mismatch": "output_mismatch",
    "empty_observation": "output_mismatch",
    "impossible_order": "impossible_order",
    "pii_leak": "pii_leak",
    "answer_leak": "answer_leak",
    "unverifiable_outcome": "unverifiable_outcome",
    "unclear_instruction": "unclear_instruction",
    "unrealistic_task": "unrealistic_task",
}


def mode_for_defect(code):
    return DEFECT_TO_MODE.get(code, "incoherent_trajectory")


def classify_failure_modes(defects):
    """Return a sorted list of distinct failure modes for a defect list."""
    modes = {mode_for_defect(d["code"]) for d in defects}
    return sorted(modes)
