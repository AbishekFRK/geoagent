"""Eval runner for GeoAgent.

    python evals/run_evals.py --validate     # check the case file (works today)
    python evals/run_evals.py --mode agent   # run the agent over every case (milestone 4)

Scoring (planned):
  * tool selection: every tool in `expected_tools` was called (extra calls allowed)
  * answer: number within `tolerance`; ordered_list/set/boolean compared exactly;
    decline cases are checked for a refusal or clarifying question
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CASES = Path(__file__).with_name("cases.jsonl")
ANSWER_TYPES = {"number", "ordered_list", "set", "boolean", "decline"}
KNOWN_TOOLS = {"geocode", "distance_bearing", "features_within", "nearest_features", "point_in_polygon"}


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate", action="store_true", help="only check the case file")
    parser.add_argument("--mode", choices=["agent"], help="run cases through the agent")
    args = parser.parse_args()

    cases = load_cases()
    problems = validate(cases)
    if problems:
        print("\n".join(problems))
        return 1
    print(f"{len(cases)} cases OK")
    if args.mode == "agent":
        raise NotImplementedError("Agent mode is planned for milestone 4.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
