# Design — Agent Training Data Quality Control

## Problem

Suppliers send batches of agent training trajectories: an
instruction, a task, a sequence of tool steps, and an expected
outcome. Some batches are good. Some contain broken steps,
leaked answers, personal data, or outcomes nobody can check.
If bad trajectories reach training, the agent learns the wrong
behaviour. This system audits supplier batches before they are
accepted, using rules a human can read — not a model judging
its own kind of output.

## What counts as good data

Good data is: complete, plausible, ordered by dependency,
using only allowed tools with correct arguments, with real
tool outputs, a clear instruction that does not give away the
answer, no personal data, and one specific outcome a grader
can check. See `docs/rubric.md` for the five dimensions.

## Architecture

Three services, each with its own HTTP API, SQLite table,
`/health`, `/metrics`, JSON logging, and Dockerfile:

- **Intake (8101)** — accepts a batch, checks the batch
  schema, stores it. Idempotent by `batch_id`: the same batch
  sent twice is stored once. Trace ids are accepted on
  `X-Trace-Id` and echoed in responses.
- **Validator (8102)** — rule-based checks only. Returns
  defects, failure modes, and a deterministic anomaly score
  (0-1) for each trajectory. No model calls.
- **Auditor (8103)** — stratified sampling by vendor,
  defect-rate estimation with a Wilson interval, rubric
  scoring, failure-mode counts, and a per-vendor report with
  one actionable fix per top failure mode.

Shared code lives in `qc_core/`: validators, rubric,
sampling, failure-mode taxonomy, SQLite helpers, flags,
and JSON logging. Python standard library only.

## Data flow

1. A vendor batch arrives at Intake (`POST /ingest`).
2. Validator checks each trajectory (`POST /validate`).
3. Auditor samples the batch, scores the sample, and writes
   a report (`POST /audit`, `GET /reports/<batch_id>`).
4. The report goes back to the vendor as feedback, and the
   next batch is expected to improve on the named modes.

## Sampling and statistics

Sampling is stratified by vendor with a fixed seed, so every
vendor is covered and a re-run gives the same sample. Defect
rate is reported with a Wilson score interval (95%), which is
more honest than a plain rate on a small sample. See
`qc_core/sampling.py`.

## Experiments and metrics

The auditor is designed, not just run: the sample fraction
and seed are inputs, the rubric is written down before
scoring, and the evaluation compares the validator against
gold labels on a held-out set (precision, recall, F1, defect
rate, rubric agreement, sampling coverage). See `evals/eval_qc.py`.

## Failure modes

Twelve modes, defined in `qc_core/failure_modes.py`, each
with a description, a typical cause, and a fix. The auditor
reports the top modes per vendor so feedback is specific,
not a generic "improve quality".

## Feature flags and canary

`flags.json` holds `validator_strict`, `rubric_v2`,
`sampling_enabled`, and `canary_percent` (10). The canary
script (`scripts/canary.py`) routes a deterministic 10%
slice of held-out trajectories through validation and
compares its defect rate with the rest, so a change in the
validator can be spotted before it is rolled out fully.

## Limits

- Rule-based checks cannot judge meaning: a step can be
  valid in form and still not lead to the outcome. The
  generator plants one such case type ("incoherent") on
  purpose; human review is still needed for those.
- The Wilson interval assumes the sample is representative;
  stratified sampling helps, but a biased batch stays biased.
- SQLite is fine for audit batches at this scale; it is not
  a design for very high write volume.
- Docker images are provided but were not run here, and the
  Kubernetes manifests were YAML-validated only, not applied
  to a cluster.
