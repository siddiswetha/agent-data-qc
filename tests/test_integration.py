"""End-to-end test: intake -> validate -> audit over real HTTP.

Starts the three services on test ports 18101-18103 with
temporary SQLite files, then exercises the full flow.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASES = {"intake": "http://127.0.0.1:18101", "validator": "http://127.0.0.1:18102", "auditor": "http://127.0.0.1:18103"}
PORTS = {"intake": "18101", "validator": "18102", "auditor": "18103"}


def _request(base, path, method="GET", payload=None, headers=None):
    req = urllib.request.Request(
        base + path,
        method=method,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8")), resp.headers.get("X-Trace-Id")


def _wait_healthy(base, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            status, _, _ = _request(base, "/health")
            if status == 200:
                return True
        except Exception:
            time.sleep(0.3)
    return False


@pytest.fixture(scope="module")
def servers(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("dbs")
    procs = []
    env = dict(os.environ)
    try:
        for name in ("intake", "validator", "auditor"):
            proc_env = dict(env)
            proc_env["PORT"] = PORTS[name]
            proc_env["QC_DB"] = str(tmp / f"{name}.db")
            proc = subprocess.Popen(
                [sys.executable, os.path.join(ROOT, "services", name, "app.py")],
                env=proc_env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            procs.append(proc)
        for base in BASES.values():
            assert _wait_healthy(base), f"service at {base} did not start"
        yield
    finally:
        for proc in procs:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def _sample_batch():
    from tests.test_validators import clean_traj
    good = clean_traj()
    bad = clean_traj()
    bad["trajectory_id"] = "T-2"
    bad["vendor"] = "Vendor-B"
    bad["steps"][1]["tool"] = "teleport"
    return [good, bad]


def test_health_and_metrics(servers):
    for base in BASES.values():
        status, body, _ = _request(base, "/health")
        assert status == 200
        assert body["status"] == "ok"
        status, body, _ = _request(base, "/metrics")
        assert status == 200


def test_trace_id_propagated(servers):
    status, _, trace_id = _request(BASES["intake"], "/health", headers={"X-Trace-Id": "trace-123"})
    assert status == 200
    assert trace_id == "trace-123"


def test_end_to_end_intake_validate_audit(servers):
    batch = _sample_batch()
    status, body, _ = _request(BASES["intake"], "/ingest", method="POST", payload={"batch_id": "BATCH-E2E", "vendor": "Vendor-A", "trajectories": batch})
    assert status == 201
    assert body["count"] == 2
    # Idempotence: same batch again is stored once.
    status, body, _ = _request(BASES["intake"], "/ingest", method="POST", payload={"batch_id": "BATCH-E2E", "vendor": "Vendor-A", "trajectories": batch})
    assert status == 200
    assert body["already_ingested"] is True
    assert body["count"] == 2
    status, body, _ = _request(BASES["intake"], "/batches/BATCH-E2E")
    assert status == 200
    assert len(body["trajectories"]) == 2

    status, body, _ = _request(BASES["validator"], "/validate", method="POST", payload={"trajectories": batch})
    assert status == 200
    assert len(body["results"]) == 2
    assert body["results"][0]["defective"] is False
    assert body["results"][1]["defective"] is True

    status, report, _ = _request(BASES["auditor"], "/audit", method="POST", payload={"batch_id": "BATCH-E2E", "trajectories": batch, "sample_fraction": 1.0, "seed": 42})
    assert status == 200
    assert report["total_trajectories"] == 2
    assert report["sampled"] == 2
    assert report["sampling_coverage"] == 1.0
    assert report["defective_in_sample"] == 1
    assert report["defect_rate"] == 0.5
    assert 0.0 <= report["wilson_low"] <= report["wilson_high"] <= 1.0
    assert "Vendor-A" in report["per_vendor"]
    assert "Vendor-B" in report["per_vendor"]
    assert report["per_vendor"]["Vendor-B"]["feedback"]

    status, stored, _ = _request(BASES["auditor"], "/reports/BATCH-E2E")
    assert status == 200
    assert stored["batch_id"] == "BATCH-E2E"
