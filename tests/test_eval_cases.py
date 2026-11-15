import importlib.util
from pathlib import Path

import pytest

from geoagent import geo

RUNNER = Path(__file__).parents[1] / "evals" / "run_evals.py"
spec = importlib.util.spec_from_file_location("run_evals", RUNNER)
run_evals = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_evals)

CASES = run_evals.load_cases()


def test_case_file_is_valid():
    assert run_evals.validate(CASES) == []


def test_there_are_both_answer_and_decline_cases():
    types = {c["answer_type"] for c in CASES}
    assert "decline" in types and "number" in types


def _two_places(question):
    # Cases phrase places by name, so pick the dataset names mentioned in the question.
    names = [p.name for p in geo.load_places() if p.kind == "city" and p.name in question]
    return sorted(names, key=question.index)


@pytest.mark.parametrize("case", [c for c in CASES if c["category"] == "distance"], ids=lambda c: c["id"])
def test_distance_expected_values_match_the_tools(case):
    """Guards against typos in the case file: expected values must agree with the geodesic tool."""
    a, b = (geo.find_place(n) for n in _two_places(case["question"]))
    got = geo.distance_bearing(a.lat, a.lon, b.lat, b.lon)["distance_km"]
    assert got == pytest.approx(case["expected"], abs=case["tolerance"])


def test_nearest_and_radius_expected_values_match_the_tools():
    by_id = {c["id"]: c for c in CASES}
    blr = geo.find_place("Bengaluru")
    nearest = [r["code"] for r in geo.nearest_features(blr.lat, blr.lon, 3, "airport")]
    assert nearest == by_id["nearest-002"]["expected"]
    assert nearest[:1] == by_id["nearest-001"]["expected"]
    within = {r["code"] for r in geo.features_within(blr.lat, blr.lon, 300, "airport")}
    assert within == set(by_id["within-001"]["expected"])
