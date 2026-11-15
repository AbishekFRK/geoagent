"""Eval runner for GeoAgent.

    python evals/run_evals.py --validate                       # check the case file only
    python evals/run_evals.py --models qwen2.5:14b llama3.1:8b # run every case on each model
    python evals/run_evals.py --models qwen2.5:14b --cases dist-001 nearest-002
    python evals/run_evals.py --models qwen2.5:14b --repeats 3  # measure run-to-run variance

Two scores per case:
  * tool selection: every tool in `expected_tools` was called (extra calls are allowed)
  * answer: the final text matches the ground truth (rules below)

Answer rules, kept deliberately simple and deterministic (no LLM judge):
  number        any number in the answer is within `tolerance` of `expected`
  ordered_list  the dataset codes mentioned, in order of first mention, equal `expected`
  set           the dataset codes mentioned, as a set, equal `expected`
  boolean       the answer says inside/yes (True) or outside/no/not (False)
  decline       the answer refuses or asks a question AND states no distance in km
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

CASES = Path(__file__).with_name("cases.jsonl")
RESULTS_DIR = Path(__file__).with_name("results")
ANSWER_TYPES = {"number", "ordered_list", "set", "boolean", "decline"}
KNOWN_TOOLS = {"geocode", "distance_bearing", "features_within", "nearest_features", "point_in_polygon"}


# ----------------------------------------------------------------------------- cases


def load_cases(path: Path = CASES) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate(cases: list[dict]) -> list[str]:
    """Return a list of problems; empty means the case file is well formed."""
    problems: list[str] = []
    seen: set[str] = set()
    for c in cases:
        cid = c.get("id", "<missing id>")
        if cid in seen:
            problems.append(f"{cid}: duplicate id")
        seen.add(cid)
        for key in ("id", "category", "question", "expected_tools", "answer_type", "expected"):
            if key not in c:
                problems.append(f"{cid}: missing '{key}'")
        if c.get("answer_type") not in ANSWER_TYPES:
            problems.append(f"{cid}: unknown answer_type {c.get('answer_type')!r}")
        unknown = set(c.get("expected_tools", [])) - KNOWN_TOOLS
        if unknown:
            problems.append(f"{cid}: unknown tools {sorted(unknown)}")
        if c.get("answer_type") == "number" and "tolerance" not in c:
            problems.append(f"{cid}: number answers need a 'tolerance'")
    return problems


# --------------------------------------------------------------------------- scoring


def _dataset_codes() -> set[str]:
    from geoagent import geo

    return {p.code for p in geo.load_places() if p.code}


def extract_numbers(text: str) -> list[float]:
    out = []
    for raw in re.findall(r"-?\d[\d,]*\.?\d*", text):
        try:
            out.append(float(raw.replace(",", "").rstrip(".")))
        except ValueError:
            pass
    return out


def extract_codes(text: str) -> list[str]:
    """Dataset codes in order of first mention, without repeats."""
    known = _dataset_codes()
    seen: list[str] = []
    for token in re.findall(r"\b[A-Z]{3}\b", text):
        if token in known and token not in seen:
            seen.append(token)
    return seen


def extract_boolean(text: str) -> bool | None:
    t = text.lower()
    if re.search(r"\b(not inside|not within|outside|is not|isn't|no)\b", t):
        return False
    if re.search(r"\b(yes|inside|within|true)\b", t):
        return True
    return None


_DECLINE_CUES = re.compile(
    r"(not in (the|our) (sample )?dataset|no place|not found|couldn't find|could not find|"
    r"unable to|don't have|do not have|which |please (provide|specify|clarify)|"
    r"could you|can you (specify|clarify)|clarify|specify|\?)",
    re.IGNORECASE,
)


def is_decline(text: str) -> bool:
    invented_distance = re.search(r"\d[\d,]*\.?\d*\s*(km|kilomet)", text, re.IGNORECASE)
    return bool(_DECLINE_CUES.search(text)) and not invented_distance


def score_tools(expected: list[str], called: list[str]) -> bool:
    return set(expected) <= set(called)


def score_answer(case: dict, answer: str) -> bool:
    kind, expected = case["answer_type"], case["expected"]
    if kind == "number":
        return any(abs(n - expected) <= case["tolerance"] for n in extract_numbers(answer))
    if kind == "ordered_list":
        return extract_codes(answer) == expected
    if kind == "set":
        return set(extract_codes(answer)) == set(expected)
    if kind == "boolean":
        return extract_boolean(answer) is expected
    if kind == "decline":
        return is_decline(answer)
    raise ValueError(f"unknown answer_type {kind!r}")


def score_case(case: dict, result: dict) -> dict:
    calls = result.get("tool_calls", [])
    called = [c["name"] for c in calls]
    answer_ok = score_answer(case, result.get("answer", ""))
    if case["answer_type"] == "boolean":
        # A yes/no can only be trusted if the tool actually ran. Otherwise an error
        # message such as "the input is not valid" could be misread as an answer.
        ran = any(c["name"] == "point_in_polygon" and not c.get("result", "").startswith("ERROR") for c in calls)
        answer_ok = answer_ok and ran
    return {
        "id": case["id"],
        "category": case["category"],
        "tools_ok": score_tools(case["expected_tools"], called),
        "answer_ok": answer_ok,
        "tools_called": called,
        "tool_results": [c.get("result", "")[:200] for c in calls],
        "answer": result.get("answer", ""),
        "steps": result.get("steps"),
        "seconds": result.get("seconds"),
        "error": result.get("error"),
    }


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    return {
        "cases": n,
        "tool_selection": round(sum(r["tools_ok"] for r in rows) / n, 3) if n else 0,
        "answer_accuracy": round(sum(r["answer_ok"] for r in rows) / n, 3) if n else 0,
        "mean_seconds": round(sum(r["seconds"] or 0 for r in rows) / n, 1) if n else 0,
    }


def _by_run(rows: list[dict]) -> list[list[dict]]:
    runs: dict[int, list[dict]] = {}
    for r in rows:
        runs.setdefault(r.get("run", 1), []).append(r)
    return [runs[k] for k in sorted(runs)]


def summarize_repeats(rows: list[dict]) -> dict:
    """Summarise a model's rows across repeated runs: mean, min and max of each run's score."""
    per_run = [summarize(group) for group in _by_run(rows)]

    def stat(key: str) -> dict:
        vals = [s[key] for s in per_run]
        return {"mean": round(sum(vals) / len(vals), 3), "min": min(vals), "max": max(vals)}

    return {
        "runs": len(per_run),
        "cases": per_run[0]["cases"],
        "tool_selection": stat("tool_selection"),
        "answer_accuracy": stat("answer_accuracy"),
        "mean_seconds": round(sum(s["mean_seconds"] for s in per_run) / len(per_run), 1),
    }


# ----------------------------------------------------------------------------- running


def run_model(model: str, cases: list[dict], repeats: int = 1) -> list[dict]:
    from geoagent import agent

    rows = []
    for run in range(1, repeats + 1):
        for case in cases:
            start = time.perf_counter()
            try:
                result = agent.ask(case["question"], model=model)
            except Exception as exc:  # an unreachable model or crashed run counts as a failed case
                result = {"answer": "", "tool_calls": [], "steps": None, "error": f"{type(exc).__name__}: {exc}"}
            result["seconds"] = round(time.perf_counter() - start, 1)
            row = score_case(case, result)
            row["run"] = run
            rows.append(row)
            mark = lambda ok: "PASS" if ok else "FAIL"  # noqa: E731
            label = f"[run {run}/{repeats}] " if repeats > 1 else ""
            print(
                f"  {label}{case['id']:<13} tools {mark(row['tools_ok'])}  answer {mark(row['answer_ok'])}  {row['seconds']}s",
                flush=True,
            )
    return rows


def markdown_report(results: dict[str, list[dict]]) -> str:
    n_runs = max(len(_by_run(rows)) for rows in results.values())
    if n_runs == 1:
        return _single_run_report(results)

    pct = lambda s: f"{s['mean']:.0%} ({s['min']:.0%}-{s['max']:.0%})"  # noqa: E731
    first = next(iter(results.values()))
    lines = [
        f"{n_runs} runs per model. Scores are the mean across runs, with the lowest and highest run in brackets.",
        "",
        "| Model | Cases per run | Tool selection | Answer accuracy | Mean time per case |",
        "|---|---|---|---|---|",
    ]
    for model, rows in results.items():
        s = summarize_repeats(rows)
        lines.append(f"| `{model}` | {s['cases']} | {pct(s['tool_selection'])} | {pct(s['answer_accuracy'])} | {s['mean_seconds']} s |")

    ids = list(dict.fromkeys(r["id"] for r in first))
    lines += ["", f"Per case: runs passed out of {n_runs} (tools / answer).", ""]
    lines += ["| Case | " + " | ".join(f"`{m}`" for m in results) + " |", "|---|" + "---|" * len(results)]
    for cid in ids:
        cells = []
        for rows in results.values():
            mine = [r for r in rows if r["id"] == cid]
            cells.append(f"{sum(r['tools_ok'] for r in mine)}/{len(mine)} / {sum(r['answer_ok'] for r in mine)}/{len(mine)}")
        lines.append(f"| {cid} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def _single_run_report(results: dict[str, list[dict]]) -> str:
    lines = ["| Model | Cases | Tool selection | Answer accuracy | Mean time per case |", "|---|---|---|---|---|"]
    for model, rows in results.items():
        s = summarize(rows)
        lines.append(
            f"| `{model}` | {s['cases']} | {s['tool_selection']:.0%} | {s['answer_accuracy']:.0%} | {s['mean_seconds']} s |"
        )
    ids = [r["id"] for r in next(iter(results.values()))]
    lines += ["", "Per case (tools / answer):", "", "| Case | " + " | ".join(f"`{m}`" for m in results) + " |"]
    lines.append("|---|" + "---|" * len(results))
    for i, cid in enumerate(ids):
        cells = []
        for rows in results.values():
            r = rows[i]
            cells.append(("✅" if r["tools_ok"] else "❌") + " / " + ("✅" if r["answer_ok"] else "❌"))
        lines.append(f"| {cid} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--validate", action="store_true", help="only check the case file")
    parser.add_argument("--models", nargs="+", help="model names served by your OpenAI-compatible endpoint")
    parser.add_argument("--cases", nargs="+", help="run only these case ids")
    parser.add_argument("--repeats", type=int, default=1, help="run every case this many times to measure variance")
    parser.add_argument("--markdown", type=Path, help="also write the results tables to this file")
    parser.add_argument("--report", type=Path, help="rebuild the tables from a saved results JSON, without running models")
    args = parser.parse_args()

    # The tables contain emoji; the default Windows console encoding cannot print them.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if args.report:
        saved = json.loads(args.report.read_text(encoding="utf-8"))
        report = markdown_report(saved["runs"])
        print(report)
        if args.markdown:
            args.markdown.write_text(report, encoding="utf-8")
        return 0

    cases = load_cases()
    problems = validate(cases)
    if problems:
        print("\n".join(problems))
        return 1
    print(f"{len(cases)} cases OK")
    if args.validate or not args.models:
        return 0

    if args.cases:
        cases = [c for c in cases if c["id"] in set(args.cases)]
        if not cases:
            print("No matching case ids.")
            return 1

    results: dict[str, list[dict]] = {}
    for model in args.models:
        print(f"\n{model}", flush=True)
        results[model] = run_model(model, cases, args.repeats)

    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = RESULTS_DIR / f"run-{stamp}.json"
    summary = {m: summarize_repeats(r) for m, r in results.items()}
    out.write_text(json.dumps({"summary": summary, "runs": results}, indent=2), encoding="utf-8")

    report = markdown_report(results)
    if args.markdown:
        args.markdown.write_text(report, encoding="utf-8")
    print("\n" + report)
    print(f"Raw results: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
