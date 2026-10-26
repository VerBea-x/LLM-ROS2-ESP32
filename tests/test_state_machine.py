import json
import tempfile
import unittest
from pathlib import Path

from src.course_audit.plan_auditor import PlanAuditor, WorldState
from src.course_audit.state_machine import ExecutionResult, run_state_machine


ROOT = Path(__file__).resolve().parents[1]


def load_world():
    return WorldState.from_mapping(json.loads(
        (ROOT / "config/lesson8_fixture.json").read_text(encoding="utf-8")))


class StateMachineTests(unittest.TestCase):
    def test_audit_rejection_is_atomic_and_never_executes(self):
        calls = [{"name": "navigate_to", "arguments": {"x": 2.0, "y": 2.0, "label": "W1_door"}},
                 {"name": "navigate_to", "arguments": {"x": 5.0, "y": 5.0, "label": "W1_door"}}]
        executions = []
        output = run_state_machine(
            "test", lambda _instruction, _feedback: {"tool_calls": calls}, PlanAuditor(load_world()),
            lambda call: executions.append(call) or ExecutionResult(True, "ok", {}))
        self.assertEqual(output["result"], "REJECTED")
        self.assertEqual(executions, [])
        self.assertTrue(all(event["type"] != "exec" for event in output["events"]))

    def test_replanning_is_bounded_to_two_replans(self):
        plans = []
        executions = []

        def planner(_instruction, feedback):
            plans.append(feedback)
            return {"tool_calls": [{"name": "navigate_to", "arguments": {
                "x": 2.0, "y": 2.0, "label": "W1_door"}}]}

        def executor(call):
            executions.append(call)
            return ExecutionResult(False, "synthetic execution failure", {"fixture_only": True})

        output = run_state_machine("test", planner, PlanAuditor(load_world()), executor)
        self.assertEqual(output["result"], "REPLAN_LIMIT")
        self.assertEqual(len(plans), 3)  # initial plan + at most two replans
        self.assertEqual(len(executions), 3)
        self.assertEqual(output["replan_count"], 2)  # third failure terminates; no third replan

    def test_success_produces_four_event_types_and_three_part_report(self):
        output = run_state_machine(
            "test", lambda _instruction, _feedback: {"tool_calls": [
                {"name": "navigate_to", "arguments": {"x": 2.0, "y": 2.0, "label": "W1_door"}}]},
            PlanAuditor(load_world()),
            lambda _call: ExecutionResult(True, "arrived", {"simulated": True}),
            limitations=["synthetic fixture only"],
        )
        self.assertEqual(output["result"], "COMPLETED")
        self.assertEqual({event["type"] for event in output["events"]},
                         {"plan", "audit", "exec", "report"})
        self.assertEqual(set(output["report"]), {"result", "evidence", "limitations"})


if __name__ == "__main__":
    unittest.main()
