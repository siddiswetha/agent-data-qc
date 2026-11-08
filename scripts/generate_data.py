"""Generate synthetic supplier trajectories. All data is synthetic.

120 trajectories from 3 fictional vendors (40 each). Planted
defects are known and stored as gold labels. Split: 90 for
development, 30 held out for evaluation. Deterministic: seed 42
for generation, seed 7 for the split.
"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

VENDORS = ["Vendor-A", "Vendor-B", "Vendor-C"]
TASK_TYPES = ["file_search", "arithmetic", "fact_lookup", "data_sort", "data_filter", "summary"]
# Higher defect probability for Vendor-B, lower for Vendor-A: a real
# pattern an auditor should be able to see in the per-vendor report.
DEFECT_PROB = {"Vendor-A": 0.25, "Vendor-B": 0.55, "Vendor-C": 0.35}
DEFECT_TYPES = [
    "missing_steps", "duplicate_step", "invalid_tool", "invalid_arguments",
    "output_mismatch", "impossible_order", "pii_leak", "answer_leak",
    "unverifiable_outcome", "unclear_instruction", "unrealistic_task", "incoherent",
]

TASK_TEXT = {
    "file_search": ("Find the file named {name} in the project folder and report its size in lines.",
                    "File {name} has 120 lines."),
    "arithmetic": ("Calculate the total cost of {n} items at {price} each, including a 10 percent charge.",
                   "Total cost is {total}."),
    "fact_lookup": ("Look up the capital of {place} and report it in one sentence.",
                    "The capital of {place} is {capital}."),
    "data_sort": ("Sort the list of {n} product names alphabetically and report the first name.",
                  "First name after sorting is {first}."),
    "data_filter": ("Filter the list of {n} orders to those over {amount} and report how many remain.",
                    "There are {count} orders over {amount}."),
    "summary": ("Read the note about {topic} and summarise it in one sentence.",
                "Summary: {topic} is described in one sentence."),
}

NAMES = ["report.txt", "notes.md", "data.csv", "plan.txt"]
PLACES = [("France", "Paris"), ("Japan", "Tokyo"), ("Canada", "Ottawa"), ("Brazil", "Brasilia")]
TOPICS = ["the release plan", "the onboarding guide", "the backup policy", "the meeting notes"]


def clean_steps(task_type, rng):
    if task_type == "file_search":
        name = rng.choice(NAMES)
        return [
            {"step": 1, "tool": "list_files", "args": {"directory": "/project"}, "observation": "Found report.txt, notes.md, data.csv, plan.txt."},
            {"step": 2, "tool": "read_file", "args": {"path": f"/project/{name}"}, "observation": f"File {name} opened. It has 120 lines."},
            {"step": 3, "tool": "summarize", "args": {"text": f"Contents of {name}"}, "observation": f"Summary: file {name} has 120 lines."},
        ]
    if task_type == "arithmetic":
        n = rng.randint(3, 9)
        price = rng.randint(5, 20)
        total = round(n * price * 1.1, 2)
        return [
            {"step": 1, "tool": "calculator", "args": {"expression": f"{n} * {price}"}, "observation": f"Result is {n * price}."},
            {"step": 2, "tool": "calculator", "args": {"expression": f"{n * price} * 1.1"}, "observation": f"Result is {total}."},
            {"step": 3, "tool": "verify", "args": {"claim": f"Total is {total}"}, "observation": f"Verified: total is {total}."},
        ]
    if task_type == "fact_lookup":
        place, capital = rng.choice(PLACES)
        return [
            {"step": 1, "tool": "search", "args": {"query": f"capital of {place}"}, "observation": f"Search result: the capital of {place} is {capital}."},
            {"step": 2, "tool": "read_file", "args": {"path": "/project/facts.txt"}, "observation": f"Facts file confirms the capital of {place} is {capital}."},
            {"step": 3, "tool": "summarize", "args": {"text": f"Capital of {place}"}, "observation": f"Summary: the capital of {place} is {capital}."},
        ]
    if task_type == "data_sort":
        return [
            {"step": 1, "tool": "list_files", "args": {"directory": "/project"}, "observation": "Found products.csv with 40 rows."},
            {"step": 2, "tool": "read_file", "args": {"path": "/project/products.csv"}, "observation": "Read 40 product names."},
            {"step": 3, "tool": "sort_data", "args": {"field": "name"}, "observation": "Sorted 40 names. First name is Apple."},
            {"step": 4, "tool": "verify", "args": {"claim": "First name after sorting is Apple"}, "observation": "Verified: first name is Apple."},
        ]
    if task_type == "data_filter":
        return [
            {"step": 1, "tool": "search", "args": {"query": "orders over 100"}, "observation": "Search found the orders file."},
            {"step": 2, "tool": "read_file", "args": {"path": "/project/orders.csv"}, "observation": "Read 30 orders."},
            {"step": 3, "tool": "filter_data", "args": {"field": "amount", "value": "100"}, "observation": "Filtered to 7 orders over 100."},
            {"step": 4, "tool": "summarize", "args": {"text": "Filtered orders"}, "observation": "Summary: 7 orders are over 100."},
        ]
    topic = rng.choice(TOPICS)
    return [
        {"step": 1, "tool": "search", "args": {"query": topic}, "observation": f"Search found the note about {topic}."},
        {"step": 2, "tool": "read_file", "args": {"path": "/project/notes.md"}, "observation": f"Read the note about {topic}."},
        {"step": 3, "tool": "summarize", "args": {"text": f"Note about {topic}"}, "observation": f"Summary: {topic} is described in one sentence."},
    ]


def make_trajectory(index, rng):
    vendor = VENDORS[index % 3]
    task_type = TASK_TYPES[index % len(TASK_TYPES)]
    name = rng.choice(NAMES)
    place, capital = rng.choice(PLACES)
    topic = rng.choice(TOPICS)
    n = rng.randint(3, 9)
    price = rng.randint(5, 20)
    total = round(n * price * 1.1, 2)
    if task_type == "file_search":
        instruction = f"Find the file named {name} in the project folder and report its size in lines."
        outcome = f"File {name} has 120 lines."
    elif task_type == "arithmetic":
        instruction = f"Calculate the total cost of {n} items at {price} each, including a 10 percent charge."
        outcome = f"Total cost is {total}."
    elif task_type == "fact_lookup":
        instruction = f"Look up the capital of {place} and report it in one sentence."
        outcome = f"The capital of {place} is {capital}."
    elif task_type == "data_sort":
        instruction = "Sort the list of 40 product names alphabetically and report the first name."
        outcome = "First name after sorting is Apple."
    elif task_type == "data_filter":
        instruction = "Filter the list of 30 orders to those over 100 and report how many remain."
        outcome = "There are 7 orders over 100."
    else:
        instruction = f"Read the note about {topic} and summarise it in one sentence."
        outcome = f"Summary: {topic} is described in one sentence."
    steps = clean_steps(task_type, rng)
    traj = {
        "trajectory_id": f"TRAJ-{index + 1:03d}",
        "vendor": vendor,
        "batch_id": f"BATCH-{(index // 40) + 1}",
        "task_type": task_type,
        "instruction": instruction,
        "expected_outcome": outcome,
        "steps": steps,
        "synthetic": True,
        "gold_defective": False,
        "gold_defect_types": [],
        "gold_rubric": {"task_realism": 2, "instruction_clarity": 2, "trajectory_coherence": 2, "tool_use_validity": 2, "outcome_verifiability": 2},
    }
    # Plant a defect with the vendor-specific probability.
    if rng.random() < DEFECT_PROB[vendor]:
        defect = rng.choice(DEFECT_TYPES)
        traj["gold_defective"] = True
        traj["gold_defect_types"] = [defect]
        rubric = dict(traj["gold_rubric"])
        if defect == "missing_steps":
            traj["steps"] = traj["steps"][:1]
            rubric["trajectory_coherence"] = 0
        elif defect == "duplicate_step":
            traj["steps"] = traj["steps"][:2] + [dict(traj["steps"][1], step=3)] + traj["steps"][2:]
            for i, s in enumerate(traj["steps"]):
                s["step"] = i + 1
            rubric["trajectory_coherence"] = 1
        elif defect == "invalid_tool":
            traj["steps"][1]["tool"] = "teleport"
            rubric["tool_use_validity"] = 1
        elif defect == "invalid_arguments":
            traj["steps"][0]["args"] = {}
            rubric["tool_use_validity"] = 1
        elif defect == "output_mismatch":
            traj["steps"][0]["observation"] = ""
            rubric["trajectory_coherence"] = 1
        elif defect == "impossible_order":
            traj["steps"] = [traj["steps"][-1]] + traj["steps"][:-1]
            for i, s in enumerate(traj["steps"]):
                s["step"] = i + 1
            rubric["trajectory_coherence"] = 0
        elif defect == "pii_leak":
            traj["steps"][0]["observation"] = "Contact person@example.test for the file."
        elif defect == "answer_leak":
            traj["instruction"] = traj["instruction"] + " The answer is " + traj["expected_outcome"]
        elif defect == "unverifiable_outcome":
            traj["expected_outcome"] = "something"
            rubric["outcome_verifiability"] = 0
        elif defect == "unclear_instruction":
            traj["instruction"] = "Do it."
            rubric["instruction_clarity"] = 0
            rubric["task_realism"] = 1
        elif defect == "unrealistic_task":
            traj["task_type"] = "time_travel"
            rubric["task_realism"] = 0
        elif defect == "incoherent":
            # A step from an unrelated task: valid tool and args, but it
            # does not lead to the outcome. Rule checks alone may miss
            # this one; that is an honest limit of rule-based QC.
            traj["steps"].insert(1, {"step": 2, "tool": "calculator", "args": {"expression": "9 * 9"}, "observation": "Result is 81."})
            for i, s in enumerate(traj["steps"]):
                s["step"] = i + 1
            rubric["trajectory_coherence"] = 0
        traj["gold_rubric"] = rubric
    return traj


def main():
    rng = random.Random(42)
    all_trajs = [make_trajectory(i, rng) for i in range(120)]
    rng_split = random.Random(7)
    shuffled = list(all_trajs)
    rng_split.shuffle(shuffled)
    dev, held_out = shuffled[:90], shuffled[90:]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name, rows in (("dev.jsonl", dev), ("held_out.jsonl", held_out)):
        path = os.path.join(root, "data", name)
        with open(path, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")
    print(f"Generated 120 synthetic trajectories: dev={len(dev)}, held_out={len(held_out)}")
    print(f"Gold defective: dev={sum(1 for r in dev if r['gold_defective'])}, held_out={sum(1 for r in held_out if r['gold_defective'])}")
    for vendor in VENDORS:
        rows = [r for r in all_trajs if r["vendor"] == vendor]
        print(f"{vendor}: {len(rows)} trajectories, {sum(1 for r in rows if r['gold_defective'])} defective (gold)")


if __name__ == "__main__":
    main()
