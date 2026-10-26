"""Run the eight prescribed positive/negative cases against a supplied world."""
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import replace
from pathlib import Path

from .plan_auditor import PlanAuditor, WorldState


def run_cases(world: WorldState, case_inputs: dict | None = None) -> list[dict]:
    inputs=case_inputs or {}
    normal = inputs.get('normal',{"name": "navigate_to", "arguments": {"x": 2.0, "y": 2.0, "label": "W1_door"}})
    occupied=inputs.get('occupied',{"name": "navigate_to", "arguments": {"x": 5.0, "y": 5.0, "label": "W1_door"}})
    stale=inputs.get('stale',{"name": "navigate_to", "arguments": {"x": 7.0, "y": 7.0, "label": "W3_podium"}})
    cases = [
        ("R1_POSITIVE", normal, world, True, "R1"),
        ("R1_NEGATIVE_OCCUPIED", occupied, world, False, "R1"),
        ("R2_POSITIVE", normal, world, True, "R2"),
        ("R2_NEGATIVE_STALE", stale, world, False, "R2"),
        ("R3_POSITIVE", normal, world, True, "R3"),
        ("R3_NEGATIVE_NONFINITE", {"name": "navigate_to", "arguments": {"x": float("nan"), "y": 2.0, "label": "W1_door"}}, world, False, "R3"),
        ("R4_POSITIVE", normal, world, True, "R4"),
        ("R4_NEGATIVE_LOW_BATTERY", normal, replace(world, battery_pct=10.0), False, "R4"),
    ]
    rows = []
    for case_id, call, case_world, expected_allowed, expected_rule in cases:
        result = PlanAuditor(case_world).audit(call)
        rows.append({
            "case_id": case_id,
            "expected_allowed": expected_allowed,
            "actual_allowed": result.allowed,
            "expected_rule": expected_rule,
            "actual_rule": result.rule_id,
            "matched": result.allowed == expected_allowed and
                      (result.allowed or result.rule_id == expected_rule),
            "reason": result.reason,
            "evidence": result.evidence,
            "fixture_only": case_world.fixture_only,
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="optional JSON report path")
    parser.add_argument('--case-inputs',type=Path,help='frozen actual-world good/occupied/stale inputs')
    args = parser.parse_args()
    try:
        world = WorldState.from_mapping(json.loads(args.world.read_text(encoding="utf-8")))
        inputs=json.loads(args.case_inputs.read_text()) if args.case_inputs else None
        rows = run_cases(world,inputs)
        report = {"suite": "week8_rule_positive_negative_8", "fixture_only": world.fixture_only,
                  "passed": all(row["matched"] for row in rows), "cases": rows}
        rendered = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered + "\n", encoding="utf-8")
        print(rendered)
        return 0 if report["passed"] else 2
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(1, f"错误：{exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
