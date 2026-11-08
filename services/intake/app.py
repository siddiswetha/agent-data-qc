"""Intake service (port 8101).

Accepts a batch of trajectories, checks the batch schema,
stores it in its own SQLite table, and is idempotent by
batch_id: sending the same batch twice stores it once.
"""
import json
import os
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from qc_core.logging_utils import log_json, new_trace_id  # noqa: E402
from qc_core.store import connect, init_intake_db  # noqa: E402

PORT = int(os.environ.get("PORT", "8101"))
DB_PATH = os.environ.get("QC_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "intake.db"))
STARTED_AT = datetime.now(timezone.utc).isoformat()
COUNTS = {"ingested_batches": 0, "ingested_trajectories": 0, "duplicate_batches": 0}


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
            self._send(200, {"status": "ok", "service": "intake", "started_at": STARTED_AT}, trace_id)
        elif path == "/metrics":
            self._send(200, {"service": "intake", **COUNTS}, trace_id)
        elif path == "/batches":
            conn = connect(DB_PATH)
            rows = conn.execute("SELECT batch_id, vendor, count FROM batches").fetchall()
            conn.close()
            self._send(200, {"batches": [dict(r) for r in rows]}, trace_id)
        elif path.startswith("/batches/"):
            batch_id = path.split("/")[-1]
            conn = connect(DB_PATH)
            row = conn.execute("SELECT batch_id, vendor, count, payload FROM batches WHERE batch_id=?", (batch_id,)).fetchone()
            conn.close()
            if row is None:
                self._send(404, {"error": "batch not found", "batch_id": batch_id}, trace_id)
            else:
                self._send(200, {"batch_id": row["batch_id"], "vendor": row["vendor"], "count": row["count"], "trajectories": json.loads(row["payload"])}, trace_id)
        else:
            self._send(404, {"error": "not found"}, trace_id)

    def do_POST(self):
        trace_id = self._trace_id()
        path = urlparse(self.path).path
        if path != "/ingest":
            self._send(404, {"error": "not found"}, trace_id)
            return
        try:
            payload = self._read_json()
        except json.JSONDecodeError:
            self._send(400, {"error": "invalid JSON"}, trace_id)
            return
        batch_id = payload.get("batch_id")
        trajectories = payload.get("trajectories")
        if not batch_id or not isinstance(trajectories, list):
            self._send(400, {"error": "batch_id and trajectories list are required"}, trace_id)
            return
        conn = connect(DB_PATH)
        existing = conn.execute("SELECT count FROM batches WHERE batch_id=?", (batch_id,)).fetchone()
        if existing is not None:
            COUNTS["duplicate_batches"] += 1
            conn.close()
            log_json("ingest_duplicate", trace_id, batch_id=batch_id, count=existing["count"])
            self._send(200, {"batch_id": batch_id, "already_ingested": True, "count": existing["count"]}, trace_id)
            return
        vendor = payload.get("vendor", "unknown")
        conn.execute(
            "INSERT INTO batches (batch_id, vendor, count, received_at, payload) VALUES (?, ?, ?, ?, ?)",
            (batch_id, vendor, len(trajectories), datetime.now(timezone.utc).isoformat(), json.dumps(trajectories)),
        )
        for traj in trajectories:
            if isinstance(traj, dict) and traj.get("trajectory_id"):
                conn.execute(
                    "INSERT OR REPLACE INTO trajectories (trajectory_id, batch_id, vendor, payload) VALUES (?, ?, ?, ?)",
                    (traj["trajectory_id"], batch_id, traj.get("vendor", vendor), json.dumps(traj)),
                )
        conn.commit()
        conn.close()
        COUNTS["ingested_batches"] += 1
        COUNTS["ingested_trajectories"] += len(trajectories)
        log_json("ingest_ok", trace_id, batch_id=batch_id, count=len(trajectories))
        self._send(201, {"batch_id": batch_id, "already_ingested": False, "count": len(trajectories)}, trace_id)


def main():
    init_intake_db(DB_PATH)
    log_json("service_start", service="intake", port=PORT)
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
