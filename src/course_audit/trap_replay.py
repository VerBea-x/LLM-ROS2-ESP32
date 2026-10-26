"""Create the paired week-8 audit-off/audit-on 12-cell record from frozen plans.

This utility only audits or records proposals. The audit-off path is explicitly
dry-run and has no executor. Input JSONL rows are {trap_id, tool_calls, raw}.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from .plan_auditor import PlanAuditor, WorldState


TRAPS = ("T1", "T2", "T3", "T4", "T5", "T6")


def create_matrix(plans_path: Path, world_path: Path, output_path: Path) -> None:
    world = WorldState.from_mapping(json.loads(world_path.read_text(encoding="utf-8")))
    plans = {}
    for line_number, line in enumerate(plans_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        trap_id = row["trap_id"]
        if trap_id in plans:
            raise ValueError(f"duplicate {trap_id} at line {line_number}")
        plans[trap_id] = row
    missing = set(TRAPS) - set(plans)
    if missing:
        raise ValueError(f"missing frozen model outputs for: {', '.join(sorted(missing))}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["trap_id", "condition", "raw_model_output", "tool_calls", "auditor_decision",
              "rule_ids", "reasons", "executor_used", "source_kind"]
    auditor = PlanAuditor(world)
    with output_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for trap_id in TRAPS:
            record = plans[trap_id]
            calls = record.get("tool_calls", [])
            raw = json.dumps(record.get("raw", record), ensure_ascii=False)
            # Audit-off is a captured proposal only. It never calls any executor.
            writer.writerow({"trap_id": trap_id, "condition": "audit_off_dry_run",
                             "raw_model_output": raw,
                             "tool_calls": json.dumps(calls, ensure_ascii=False),
                             "auditor_decision": "NOT_RUN",
                             "rule_ids": "", "reasons": "", "executor_used": "no",
                             "source_kind": "frozen_model_output"})
            results = [auditor.audit(call) for call in calls]
            allowed = bool(results) and all(result.allowed for result in results)
            writer.writerow({"trap_id": trap_id, "condition": "audit_on",
                             "raw_model_output": raw,
                             "tool_calls": json.dumps(calls, ensure_ascii=False),
                             "auditor_decision": ("ALLOW" if allowed else "REJECT") if calls else "NO_TOOL_CALLS",
                             "rule_ids": ";".join(result.rule_id for result in results),
                             "reasons": json.dumps([result.as_dict() for result in results if not result.allowed],
                                                   ensure_ascii=False),
                             "executor_used": "no", "source_kind": "frozen_model_output"})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plans", type=Path, required=True)
    parser.add_argument("--world", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("evidence/raw/lesson8_trap_results.csv"))
    args = parser.parse_args()
    try:
        create_matrix(args.plans, args.world, args.output)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(2, f"无法生成对照表：{exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
