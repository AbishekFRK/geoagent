import importlib.util
from pathlib import Path

import pytest

RUNNER = Path(__file__).parents[1] / "evals" / "run_evals.py"
spec = importlib.util.spec_from_file_location("run_evals", RUNNER)
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)

CASES = {c["id"]: c for c in ev.load_cases()}


@pytest.mark.parametrize(
    "case_id,answer,ok",
    [
        ("dist-001", "The distance between Chennai and Bengaluru is approximately 290.543 km.", True),
        ("dist-001", "It is about 350 km.", False),
        ("dist-003", "Roughly 1,022 km", False),
        ("bearing-001", "The initial bearing is 203.58 degrees.", True),
        ("bearing-001", "The bearing is 23.6 degrees.", False),
    ],
)
def test_number_scoring(case_id, answer, ok):
    assert ev.score_answer(CASES[case_id], answer) is ok


def test_ordered_list_scoring_uses_order_and_ignores_prose():
    good = "1. **BLR (Kempegowda)** 28 km\n2. **CJB** 222 km\n3. **MAA** 279 km"
    assert ev.score_answer(CASES["nearest-002"], good) is True
    assert ev.score_answer(CASES["nearest-002"], "MAA, CJB, BLR") is False
    # IATA is not a dataset code, so the word in the prose must not count.
    assert ev.score_answer(CASES["nearest-001"], "The IATA code is BLR.") is True
    assert ev.score_answer(CASES["nearest-001"], "BLR and CJB") is False


def test_set_scoring_ignores_order():
    assert ev.score_answer(CASES["within-001"], "IXE, MAA, BLR and CJB") is True
    assert ev.score_answer(CASES["within-001"], "BLR and MAA") is False


@pytest.mark.parametrize(
    "case_id,answer,ok",
    [
        ("pip-001", "Yes, the point is inside the polygon.", True),
        ("pip-001", "No, the point is outside the polygon.", False),
        ("pip-002", "The point is not inside the polygon.", True),
        ("pip-002", "No, it lies outside.", True),
        ("pip-002", "Yes, it is inside.", False),
    ],
)
def test_boolean_scoring(case_id, answer, ok):
    assert ev.score_answer(CASES[case_id], answer) is ok


def test_decline_scoring_rejects_invented_distances():
    asks = "Which two airports do you mean? Could you please specify?"
    refuses = 'There is no place named "Atlantis" in our dataset.'
    invents = "I couldn't find Atlantis, but it is roughly 5,000 km from Delhi."
    assert ev.score_answer(CASES["decline-002"], asks) is True
    assert ev.score_answer(CASES["decline-001"], refuses) is True
    assert ev.score_answer(CASES["decline-001"], invents) is False
    assert ev.score_answer(CASES["decline-001"], "The distance is 100 km.") is False


def test_tool_selection_allows_extra_calls_but_not_missing_ones():
    assert ev.score_tools(["geocode", "distance_bearing"], ["geocode", "geocode", "distance_bearing"]) is True
    assert ev.score_tools(["geocode", "distance_bearing"], ["geocode"]) is False
    assert ev.score_tools([], ["geocode"]) is True


def test_score_case_and_summary():
    result = {"answer": "About 290.5 km.", "tool_calls": [{"name": "geocode"}, {"name": "distance_bearing"}], "steps": 3, "seconds": 2.0}
    row = ev.score_case(CASES["dist-001"], result)
    assert row["tools_ok"] and row["answer_ok"]
    bad = ev.score_case(CASES["dist-001"], {"answer": "", "tool_calls": [], "seconds": 1.0})
    summary = ev.summarize([row, bad])
    assert summary == {"cases": 2, "tool_selection": 0.5, "answer_accuracy": 0.5, "mean_seconds": 1.5}


def test_boolean_answer_needs_a_successful_tool_run():
    failed = {"answer": "The input polygon is not in the correct format.",
              "tool_calls": [{"name": "point_in_polygon", "result": "ERROR: bad arguments"}]}
    assert ev.score_case(CASES["pip-002"], failed)["answer_ok"] is False
    ok = {"answer": "The point is outside the polygon.",
          "tool_calls": [{"name": "point_in_polygon", "result": "false"}]}
    assert ev.score_case(CASES["pip-002"], ok)["answer_ok"] is True
    no_tool = {"answer": "The point is outside the polygon.", "tool_calls": []}
    assert ev.score_case(CASES["pip-002"], no_tool)["answer_ok"] is False


def _row(case_id, run, tools_ok, answer_ok, seconds=1.0):
    return {"id": case_id, "run": run, "tools_ok": tools_ok, "answer_ok": answer_ok, "seconds": seconds}


def test_summarize_repeats_reports_mean_min_and_max_across_runs():
    rows = [
        _row("a", 1, True, True), _row("b", 1, True, False),    # run 1: tools 100%, answers 50%
        _row("a", 2, False, True), _row("b", 2, False, True),   # run 2: tools 0%, answers 100%
    ]
    s = ev.summarize_repeats(rows)
    assert s["runs"] == 2 and s["cases"] == 2
    assert s["tool_selection"] == {"mean": 0.5, "min": 0.0, "max": 1.0}
    assert s["answer_accuracy"] == {"mean": 0.75, "min": 0.5, "max": 1.0}


def test_repeat_report_shows_pass_counts_per_case():
    rows = [_row("a", 1, True, True), _row("a", 2, True, False), _row("a", 3, False, False)]
    md = ev.markdown_report({"m1": rows})
    assert "3 runs per model" in md
    assert "| a | 2/3 / 1/3 |" in md


def test_single_run_rows_without_a_run_field_still_work():
    rows = [{"id": "a", "tools_ok": True, "answer_ok": True, "seconds": 1.0}]
    assert ev.summarize_repeats(rows)["runs"] == 1


def test_markdown_report_has_a_row_per_model_and_case():
    rows = [ev.score_case(CASES["dist-001"], {"answer": "290.5 km", "tool_calls": [{"name": "geocode"}, {"name": "distance_bearing"}], "seconds": 1.0})]
    md = ev.markdown_report({"m1": rows})
    assert "`m1`" in md and "dist-001" in md and "100%" in md
