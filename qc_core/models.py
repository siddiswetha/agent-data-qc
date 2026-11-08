"""Data model for a supplier-generated agent training trajectory.

A trajectory is one worked example for training an agent:
an instruction, a task, a sequence of tool steps, and an
expected outcome. Every record in this project is synthetic.
"""

VALID_TOOLS = {
    "search": ["query"],
    "calculator": ["expression"],
    "read_file": ["path"],
    "write_file": ["path", "content"],
    "list_files": ["directory"],
    "sort_data": ["field"],
    "filter_data": ["field", "value"],
    "summarize": ["text"],
    "verify": ["claim"],
}

TASK_TYPES = ["file_search", "arithmetic", "fact_lookup", "data_sort", "data_filter", "summary"]

VENDORS = ["Vendor-A", "Vendor-B", "Vendor-C"]

REQUIRED_TRAJECTORY_FIELDS = [
    "trajectory_id",
    "vendor",
    "task_type",
    "instruction",
    "expected_outcome",
    "steps",
]

REQUIRED_STEP_FIELDS = ["step", "tool", "args", "observation"]


def is_valid_vendor(vendor):
    return vendor in VENDORS


def is_valid_task_type(task_type):
    return task_type in TASK_TYPES
