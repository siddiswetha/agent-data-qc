"""Feature flags, read from flags.json at the project root."""
import json
import os

DEFAULT_FLAGS = {
    "validator_strict": True,
    "rubric_v2": False,
    "sampling_enabled": True,
    "canary_percent": 10,
}


def load_flags(path=None):
    if path is None:
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(here, "flags.json")
    flags = dict(DEFAULT_FLAGS)
    try:
        with open(path, encoding="utf-8") as f:
            flags.update(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return flags
