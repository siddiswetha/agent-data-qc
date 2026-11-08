"""Stratified sampling and defect-rate estimation.

Sampling is stratified by vendor so every vendor is covered.
Defect rate is reported with a Wilson score interval, which
is more honest than a plain rate when a sample is small.
"""
import math
import random


def wilson_interval(defects, total, z=1.96):
    """Wilson score interval for a proportion. Returns (low, high, centre)."""
    if total <= 0:
        return (0.0, 0.0, 0.0)
    p = defects / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denom
    low = max(0.0, centre - margin)
    high = min(1.0, centre + margin)
    return (round(low, 3), round(high, 3), round(centre, 3))


def stratified_sample(items, fraction, seed=42, strata_key="vendor"):
    """Deterministic stratified sample: same fraction from each stratum.

    Returns (sampled_items, coverage) where coverage is sampled/total.
    At least one item is taken from each non-empty stratum.
    """
    if not items:
        return [], 0.0
    if fraction >= 1.0:
        return list(items), 1.0
    if fraction <= 0:
        return [], 0.0
    rng = random.Random(seed)
    groups = {}
    for item in items:
        key = item.get(strata_key, "unknown") if isinstance(item, dict) else "unknown"
        groups.setdefault(key, []).append(item)
    sampled = []
    for key in sorted(groups):
        group = list(groups[key])
        rng.shuffle(group)
        take = max(1, int(round(len(group) * fraction)))
        take = min(take, len(group))
        sampled.extend(group[:take])
    coverage = round(len(sampled) / len(items), 3)
    return sampled, coverage


def defect_rate(items, is_defective):
    """Return (defect_count, total, rate, wilson_low, wilson_high)."""
    total = len(items)
    count = sum(1 for item in items if is_defective(item))
    rate = round(count / total, 3) if total else 0.0
    low, high, _ = wilson_interval(count, total)
    return count, total, rate, low, high
