"""Validator service (port 8102).

Rule-based checks only. No model calls. Accepts one trajectory
or a list, returns defects, failure modes, and a deterministic
anomaly score for each, and records the result in its own
SQLite table.
"""
import json
import os
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from qc_core.logging_utils import log_json, new_trace_id  # noqa: E402
from qc_core.store import connect, init_validator_db  # noqa: E402
from qc_core.validators import validate_trajectory  # noqa: E402

PORT = int(os.environ.get("PORT", "8102"))
DB_PATH = os.environ.get("QC_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "validator.db"))
STARTED_AT = datetime.now(timezone.utc).isoformat()
COUNTS = {"validated": 0, "defective": 0}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _trace_id(self):
        return self.headers.get("X-Trace-Id") or new_trace_id()

    def _send(self, status, payload, trace_id):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Trace-Id", trace_id)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8") or "{}")

    def do_GET(self):
        trace_id = self._trace_id()
        path = urlparse(self.path).path
        if path == "/health":
            self._send(200, {"status": "ok", "service": "validator", "started_at": STARTED_AT}, trace_id)
        elif path == "/metrics":
            self._send(200, {"service": "validator", **COUNTS}, trace_id)
        else:
            self._send(404, {"error": "not found"}, trace_id)

    def do_POST(self):
        trace_id = self._trace_id()
        path = urlparse(self.path).path
        if path != "/validate":
            self._send(404, {"error": "not found"}, trace_id)
            return
        try:
            payload = self._read_json()
        except json.JSONDecodeError:
            self._send(400, {"error": "invalid JSON"}, trace_id)
            return
        if "trajectory" in payload:
            trajectories = [payload["trajectory"]]
        elif "trajectories" in payload:
            trajectories = payload["trajectories"]
        else:
            self._send(400, {"error": "trajectory or trajectories is required"}, trace_id)
            return
        if not isinstance(trajectories, list):
            self._send(400, {"error": "trajectories must be a list"}, trace_id)
            return
        results = []
        conn = connect(DB_PATH)
        for traj in trajectories:
            result = validate_trajectory(traj)
            results.append(result)
            traj_id = result.get("trajectory_id") or "unknown"
            conn.execute(
                "INSERT OR REPLACE INTO validations (trajectory_id, defective, anomaly_score, defects, checked_at) VALUES (?, ?, ?, ?, ?)",
                (traj_id, 1 if result["defective"] else 0, result["anomaly_score"], json.dumps(result["defects"]), datetime.now(timezone.utc).isoformat()),
            )
            COUNTS["validated"] += 1
            if result["defective"]:
                COUNTS["defective"] += 1
        conn.commit()
        conn.close()
        log_json("validate_ok", trace_id, count=len(results), defective=sum(1 for r in results if r["defective"]))
        self._send(200, {"results": results}, trace_id)


def main():
    init_validator_db(DB_PATH)
    log_json("service_start", service="validator", port=PORT)
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
