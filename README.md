# Agent Training Data Quality Control

A rule-based quality-control system that audits supplier-generated
agent training trajectories before they are accepted for training.
No model calls, no outside services, Python standard library only.
All data is synthetic and labelled as such.

## What it does

A vendor sends a batch of trajectories: an instruction, a task,
a sequence of tool steps, and an expected outcome. This system
checks each trajectory with plain rules a human can read,
samples batches by vendor, estimates the defect rate with a
confidence interval, scores a five-dimension rubric, and sends
each vendor a report naming its top failure modes and the fix
for each one.

## Architecture

- **Intake (port 8101)** — `services/intake/app.py`. Accepts a
  batch (`POST /ingest`), checks the batch schema, stores it in
  its own SQLite table. Idempotent by `batch_id`: sending the
  same batch twice stores it once. Trace ids are accepted on
  `X-Trace-Id` and echoed in responses.
- **Validator (port 8102)** — `services/validator/app.py`.
  Rule-based checks only: schema, missing / empty steps,
  duplicate steps, invalid tool names and arguments, tool
  output mismatch, impossible step order, personal-data
  patterns, leaked answers in instructions, and unverifiable
  outcomes. Returns defects, failure modes, and a
  deterministic anomaly score (0-1). No model calls.
- **Auditor (port 8103)** — `services/auditor/app.py`.
  Stratified sampling by vendor, defect-rate estimation with
  a Wilson interval, five-dimension rubric scoring, failure-mode
  counts, and a per-vendor report with actionable feedback.
  Reports are stored and readable at `GET /reports/<batch_id>`.
- **Shared core** — `qc_core/`: validators, rubric, sampling
  (Wilson interval), a 12-mode failure taxonomy, SQLite
  helpers, feature flags, and JSON logging.
- **Data** — `scripts/generate_data.py` builds 120 synthetic
  trajectories from 3 fictional vendors (Vendor-A, Vendor-B,
  Vendor-C), with planted defects of known types. Split:
  90 development, 30 held out.
- **Evaluation** — `evals/eval_qc.py` compares the validator
  against gold labels on the held-out set.
- **CLI, flags, canary** — `cli.py` (generate / validate /
  audit / eval / canary / flags), `flags.json`, and
  `scripts/canary.py` (deterministic 10% canary slice).

Each service has its own API, SQLite table, `/health`,
`/metrics`, JSON logging, and Dockerfile. `docker-compose.yml`
runs all three. Kubernetes manifests are in `k8s/`.

## How to run

```bash
python scripts/generate_data.py
python cli.py validate data/held_out.jsonl
python cli.py audit data/held_out.jsonl --batch-id BATCH-HELDOUT --sample-fraction 0.5
python scripts/run_eval.py
python -m pytest tests -q
```

Run the services (three terminals, or `docker compose up`):

```bash
python services/intake/app.py     # port 8101
python services/validator/app.py  # port 8102
python services/auditor/app.py    # port 8103
```

Example flow:

```bash
curl -X POST localhost:8101/ingest -H 'Content-Type: application/json' \
  -d '{"batch_id": "BATCH-1", "vendor": "Vendor-A", "trajectories": [...]}'
curl -X POST localhost:8102/validate -H 'Content-Type: application/json' \
  -d '{"trajectories": [...]}'
curl -X POST localhost:8103/audit -H 'Content-Type: application/json' \
  -d '{"batch_id": "BATCH-1", "trajectories": [...], "sample_fraction": 0.5}'
```

## Verified results

Tests (run locally, Python 3.12, pytest 9.2.0):

- **36 passed, 0 failed** — unit tests for validators, rubric,
  sampling / Wilson interval, failure-mode taxonomy, plus an
  end-to-end integration test over real HTTP:
  intake -> validate -> audit, including idempotence and
  trace-id propagation.

Held-out evaluation (`python scripts/run_eval.py`, 30 trajectories,
13 gold-defective, 17 clean):

- Precision **1.000**, Recall **1.000**, F1 **1.000**
  (TP 13, FP 0, FN 0, TN 17)
- Gold defect rate **0.433**, predicted defect rate **0.433**
- Rubric agreement (mean, per dimension) **0.993**,
  rubric average total **9.37 / 10**
- Sampling coverage **0.5** at fraction 0.5 (15 sampled:
  Vendor-A 5, Vendor-B 4, Vendor-C 6)

Canary check (`python scripts/canary.py`, 10% slice of held out):
canary size 5, defect rate 0.6; rest size 25, defect rate 0.4.
The gap is expected on a slice of 5 and is reported, not hidden.

Gold defect rates in the full synthetic set: Vendor-A 10/40,
Vendor-B 25/40, Vendor-C 15/40 — the per-vendor report
surfaces exactly this kind of difference.

## Honest limits

- The held-out 1.000 recall is partly luck of the split: no
  "incoherent" case landed in the 30 held-out trajectories.
  On the 90-trajectory development set the same validator
  scores precision 1.000, recall **0.919**, F1 **0.958**
  (TP 34, FP 0, FN 3, TN 53). The 3 misses are all
  "incoherent" trajectories — a step that is valid in form
  but does not lead to the outcome. Rule checks alone cannot
  judge meaning; human review is still needed for those.
- The Wilson interval assumes the sample is representative;
  stratified sampling helps, but a biased batch stays biased.
- SQLite fits audit batches at this scale; it is not a design
  for very high write volume.
- Docker images are provided but were not run here, and the
  Kubernetes manifests were YAML-validated only, not applied
  to a cluster.
