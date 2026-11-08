import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qc_core.sampling import defect_rate, stratified_sample, wilson_interval


def make_items():
    items = []
    for vendor in ("Vendor-A", "Vendor-B", "Vendor-C"):
        for i in range(10):
            items.append({"trajectory_id": f"{vendor}-{i}", "vendor": vendor})
    return items


def test_wilson_interval_contains_rate_and_stays_in_bounds():
    low, high, centre = wilson_interval(5, 20)
    assert 0.0 <= low <= centre <= high <= 1.0
    assert low <= 0.25 <= high


def test_wilson_interval_empty_sample():
    assert wilson_interval(0, 0) == (0.0, 0.0, 0.0)


def test_wilson_interval_narrows_with_more_data():
    _, high_small, _ = wilson_interval(5, 20)
    low_small, _, _ = wilson_interval(5, 20)
    low_big, high_big, _ = wilson_interval(50, 200)
    assert (high_big - low_big) < (high_small - low_small)


def test_stratified_sample_covers_every_vendor():
    items = make_items()
    sampled, coverage = stratified_sample(items, 0.5, seed=42)
    assert len(sampled) == 15
    assert coverage == 0.5
    vendors = {item["vendor"] for item in sampled}
    assert vendors == {"Vendor-A", "Vendor-B", "Vendor-C"}


def test_stratified_sample_is_deterministic():
    items = make_items()
    first, _ = stratified_sample(items, 0.5, seed=42)
    second, _ = stratified_sample(items, 0.5, seed=42)
    assert [i["trajectory_id"] for i in first] == [i["trajectory_id"] for i in second]


def test_stratified_sample_full_fraction():
    items = make_items()
    sampled, coverage = stratified_sample(items, 1.0, seed=42)
    assert len(sampled) == 30
    assert coverage == 1.0


def test_defect_rate_and_wilson():
    items = [{"defective": True}, {"defective": False}, {"defective": True}, {"defective": False}]
    count, total, rate, low, high = defect_rate(items, lambda r: r["defective"])
    assert (count, total, rate) == (2, 4, 0.5)
    assert 0.0 <= low <= high <= 1.0
