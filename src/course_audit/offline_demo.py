"""Demonstrate the state-machine event/report contract without ROS or a model."""
from __future__ import annotations

import json
from pathlib import Path

from .plan_auditor import PlanAuditor, WorldState
from .state_machine import ExecutionResult, run_state_machine


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    world_data = json.loads((root / "config/lesson8_fixture.json").read_text(encoding="utf-8"))
    world = WorldState.from_mapping(world_data)
    call = {"name": "navigate_to", "arguments": {"x": 2.0, "y": 2.0, "label": "W1_door"}}
    result = run_state_machine(
        "fixture demonstration only",
        lambda _instruction, _feedback: {"tool_calls": [call]},
        PlanAuditor(world),
        lambda _call: ExecutionResult(False, "offline demo: no ROS or robot was contacted",
                                       {"fixture_only": True, "simulated_execution": False}),
        limitations=["合成数据；没有调用 ROS、Nav2、模型 API 或实体小车。"],
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
