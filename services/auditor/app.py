"""Auditor service (port 8103).

Stratified sampling, defect-rate estimation with a Wilson
interval, five-dimension rubric scoring, failure-mode counts,
and a per-vendor defect report with actionable feedback.
Rule-based only; no model calls.
"""
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from qc_core.failure_modes import FAILURE_MODES  # noqa: E402
from qc_core.logging_utils import log_json, new_trace_id  # noqa: E402
from qc_core.rubric import rubric_score  # noqa: E402
from qc_core.sampling import defect_rate, stratified_sample, wilson_interval  # noqa: E402
from qc_core.store import connect, init_auditor_db  # noqa: E402
from qc_core.validators import validate_trajectory  # noqa: E402

PORT = int(os.environ.get("PORT", "8103"))
DB_PATH = os.environ.get("QC_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "auditor.db"))
STARTED_AT = datetime.now(timezone.utc).isoformat()
COUNTS = {"audits": 0}


def build_report(batch_id, trajectories, sample_fraction=0.5, seed=42):
    sampled, coverage = stratified_sample(trajectories, sample_fraction, seed=seed)
    results = []
    for traj in sampled:
        validation = validate_trajectory(traj)
        rubric = rubric_score(traj, validation)
        results.append({"trajectory_id": traj.get("trajectory_id"), "vendor": traj.get("vendor"), "validation": validation, "rubric": rubric})

    def _is_defective(r):
        return r["validation"]["defective"]

    count, total, rate, low, high = defect_rate(results, _is_defective)
    mode_counts = Counter()
    for r in results:
        for mode in r["validation"]["failure_modes"]:
            mode_counts[mode] += 1

    per_vendor = {}
    vendors = sorted({r["vendor"] for r in results if r["vendor"]})
    for vendor in vendors:
        subset = [r for r in results if r["vendor"] == vendor]
        v_count, v_total, v_rate, v_low, v_high = defect_rate(subset, _is_defective)
        v_modes = Counter()
        for r in subset:
            for mode in r["validation"]["failure_modes"]:
                v_modes[mode] += 1
        top_modes = [m for m, _ in v_modes.most_common(3)]
        feedback = []
        for mode in top_modes:
            feedback.append({"mode": mode, "fix": FAILURE_MODES[mode]["fix"]})
        if not feedback:
            feedback.append({"mode": "none", "fix": "No defects found in the sample. Keep the current generation checks."})
        rubric_avg = round(sum(r["rubric"]["total"] for r in subset) / len(subset), 2) if subset else 0.0
        per_vendor[vendor] = {
            "sampled": v_total,
            "defective": v_count,
            "defect_rate": v_rate,
            "wilson_low": v_low,
            "wilson_high": v_high,
            "rubric_average_total": rubric_avg,
            "top_failure_modes": top_modes,
            "feedback": feedback,
        }

    rubric_avg_all = round(sum(r["rubric"]["total"] for r in results) / len(results), 2) if results else 0.0
    rubric_pass = sum(1 for r in results if r["rubric"]["passed"])
    return {
        "batch_id": batch_id,
        "total_trajectories": len(trajectories),
        "sampled": len(sampled),
        "sampling_coverage": coverage,
        "sample_fraction": sample_fraction,
        "seed": seed,
        "defective_in_sample": count,
        "defect_rate": rate,
        "wilson_low": low,
        "wilson_high": high,
        "rubric_average_total": rubric_avg_all,
        "rubric_pass_count": rubric_pass,
        "failure_mode_counts": dict(mode_counts),
        "per_vendor": per_vendor,
        "results": results,
    }


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
            self._send(200, {"status": "ok", "service": "auditor", "started_at": STARTED_AT}, trace_id)
        elif path == "/metrics":
            self._send(200, {"service": "auditor", **COUNTS}, trace_id)
        elif path.startswith("/reports/"):
            batch_id = path.split("/")[-1]
            conn = connect(DB_PATH)
            row = conn.execute("SELECT report FROM reports WHERE batch_id=?", (batch_id,)).fetchone()
            conn.close()
            if row is None:
                self._send(404, {"error": "report not found", "batch_id": batch_id}, trace_id)
            else:
                self._send(200, json.loads(row["report"]), trace_id)
        else:
            self._send(404, {"error": "not found"}, trace_id)

    def do_POST(self):
        trace_id = self._trace_id()
        path = urlparse(self.path).path
        if path != "/audit":
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
        report = build_report(batch_id, trajectories, sample_fraction=float(payload.get("sample_fraction", 0.5)), seed=int(payload.get("seed", 42)))
        conn = connect(DB_PATH)
        conn.execute(
            "INSERT OR REPLACE INTO reports (batch_id, report, created_at) VALUES (?, ?, ?)",
            (batch_id, json.dumps(report), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        conn.close()
        COUNTS["audits"] += 1
        log_json("audit_ok", trace_id, batch_id=batch_id, sampled=report["sampled"], defect_rate=report["defect_rate"])
        self._send(200, report, trace_id)


def main():
    init_auditor_db(DB_PATH)
    log_json("service_start", service="auditor", port=PORT)
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
