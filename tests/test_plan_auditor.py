import json
import unittest
from pathlib import Path

from src.course_audit.plan_auditor import OccupancyGridSnapshot, PlanAuditor, WorldState


ROOT = Path(__file__).resolve().parents[1]


class PlanAuditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = WorldState.from_mapping(json.loads(
            (ROOT / "config/lesson8_fixture.json").read_text(encoding="utf-8")))
        cls.auditor = PlanAuditor(cls.world)

    @staticmethod
    def call(x=2.0, y=2.0, label="W1_door"):
        return {"name": "navigate_to", "arguments": {"x": x, "y": y, "label": label}}

    def test_eight_rule_cases(self):
        cases = [
            (self.call(), True, "PASS"),
            (self.call(5.0, 5.0), False, "R1"),
            (self.call(7.0, 7.0, "W3_podium"), False, "R2"),
            (self.call(float("nan"), 2.0), False, "R3"),
            (self.call(), True, "PASS"),
            (self.call(), False, "R4"),
            (self.call(), True, "PASS"),
            (self.call(), False, "R4"),
        ]
        from dataclasses import replace
        worlds = [self.world, self.world, self.world, self.world, self.world,
                  replace(self.world, battery_pct=10.0), self.world,
                  replace(self.world, estimated_task_s=90.0)]
        for (call, expected_allowed, expected_rule), world in zip(cases, worlds, strict=True):
            result = PlanAuditor(world).audit(call)
            self.assertEqual(result.allowed, expected_allowed)
            self.assertEqual(result.rule_id, expected_rule)
            if not result.allowed:
                self.assertTrue(result.reason)
                self.assertTrue(result.correction)

    def test_whitelist_precedes_rule_checks(self):
        result = self.auditor.audit({"name": "pick_up", "arguments": {}})
        self.assertFalse(result.allowed)
        self.assertEqual(result.rule_id, "WHITELIST")

    def test_schema_rejects_extra_fields_without_repair(self):
        result = self.auditor.audit({"name": "navigate_to", "arguments": {
            "x": 2.0, "y": 2.0, "label": "W1_door", "speed": 99.0}})
        self.assertFalse(result.allowed)
        self.assertEqual(result.rule_id, "SCHEMA")
        self.assertIn("speed", result.reason)

    def test_stop_is_available_even_with_empty_battery(self):
        from dataclasses import replace
        result = PlanAuditor(replace(self.world, battery_pct=0.0)).audit(
            {"name": "stop", "arguments": {}})
        self.assertTrue(result.allowed)
        self.assertEqual(result.rule_id, "SAFE_STOP")

    def test_occupancy_grid_rejects_occupied_and_unknown_cells(self):
        from dataclasses import replace
        grid = OccupancyGridSnapshot.from_mapping({
            "width": 2, "height": 2, "resolution_m": 1.0,
            "origin_x_m": 0.0, "origin_y_m": 0.0, "origin_yaw_rad": 0.0,
            "data": [0, 100, -1, 0], "occupied_threshold": 50,
        })
        world = replace(self.world, bounds_m=(0.0, 2.0, 0.0, 2.0), occupancy_grid=grid)
        free = PlanAuditor(world).audit(self.call(0.5, 0.5))
        occupied = PlanAuditor(world).audit(self.call(1.5, 0.5))
        unknown = PlanAuditor(world).audit(self.call(0.5, 1.5))
        self.assertTrue(free.allowed)
        self.assertFalse(occupied.allowed)
        self.assertEqual(occupied.rule_id, "R1")
        self.assertFalse(unknown.allowed)
        self.assertEqual(unknown.rule_id, "R1")

    def test_multi_call_plan_can_be_audited_atomically_by_caller(self):
        calls = [self.call(), self.call(5.0, 5.0)]
        results = [self.auditor.audit(call) for call in calls]
        self.assertFalse(all(result.allowed for result in results))
        self.assertEqual([result.allowed for result in results], [True, False])


if __name__ == "__main__":
    unittest.main()
