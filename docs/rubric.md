# Human rubric — five dimensions, 0-2 each, total 0-10

Pass: total 8 or more, and no dimension scored 0.

## 1. Task realism

- 2 — Plausible real request, doable with the allowed tools.
- 1 — Plausible but contrived.
- 0 — Impossible, or not a request a real user would make.

## 2. Instruction clarity

- 2 — Complete: task, input, and expected form of the answer.
- 1 — Understandable, but missing one detail.
- 0 — Empty, too short, or ambiguous.

## 3. Trajectory coherence

- 2 — Steps follow logically from the instruction to the outcome.
- 1 — One gap or odd step.
- 0 — Steps do not lead to the outcome, or the order is impossible.

## 4. Tool-use validity

- 2 — Every tool is allowed, every argument is present and correct.
- 1 — One minor misuse.
- 0 — Unknown tool, or missing / wrong arguments.

## 5. Outcome verifiability

- 2 — One specific, checkable result (a file name, a number, a fact).
- 1 — Partly checkable.
- 0 — Empty, or too vague to check ("something", "a good result").

## How it is used

A human reviewer applies these rules to a sampled trajectory.
The same rules are coded in `qc_core/rubric.py`, so the
automatic score and the human score can be compared
(rubric agreement in the evaluation). Where they disagree,
the written rule is the reference, not the code.
