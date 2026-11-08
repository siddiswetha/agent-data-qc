"""JSON logging with trace-id propagation. Standard library only."""
import json
import sys
import uuid


def new_trace_id():
    return str(uuid.uuid4())


def log_json(event, trace_id=None, **fields):
    record = {"event": event, "trace_id": trace_id or new_trace_id()}
    record.update(fields)
    sys.stdout.write(json.dumps(record) + "\n")
    sys.stdout.flush()
