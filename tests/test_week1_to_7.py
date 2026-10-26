import csv
import json
import unittest
from pathlib import Path

from src.course_audit.localization_metrics import analyze as analyze_localization
from src.course_audit.plan_auditor import schema_check
from src.course_audit.semantic_map import query, validate
from src.course_audit.vision_metrics import calculate as calculate_vision


ROOT = Path(__file__).resolve().parents[1]


class Week1To7Tests(unittest.TestCase):
    def test_week5_metrics_compute_three_thresholds_from_independent_truth(self):
        rows = []
        for index in range(20):
            rows.append({"sample_id": f"I{index:02}",
                         "source_group": "public" if index < 10 else "custom",
                         "truth_positive": "true" if index % 2 == 0 else "false",
                         "score": "0.9" if index % 2 == 0 else "0.1",
                         "truth_source": f"label-{index}"})
        result = calculate_vision(rows, [0.2, 0.5, 0.8])
        self.assertEqual(result["n_scenes"], 20)
        self.assertEqual([r["precision"] for r in result["results"]], [1.0, 1.0, 1.0])
        self.assertEqual([r["recall"] for r in result["results"]], [1.0, 1.0, 1.0])

    def test_week5_rejects_untraceable_labels(self):
        rows = [{"sample_id": str(i), "source_group": "public" if i < 10 else "custom",
                 "truth_positive": "false", "score": "0.1", "truth_source": ""}
                for i in range(20)]
        with self.assertRaisesRegex(ValueError, "独立真值"):
            calculate_vision(rows, [0.2, 0.5, 0.8])

    def test_week6_semantic_map_age_state_is_computed_at_query_time(self):
        document = json.loads((ROOT / "config/semantic_map_fixture.json").read_text(encoding="utf-8"))
        self.assertEqual(validate(document), [])
        self.assertEqual(query(document, "W1_door", 100.0)["state"], "fresh")
        self.assertEqual(query(document, "W3_podium", 100.0)["state"], "stale")
        self.assertIsNone(query(document, "W9_unknown", 100.0))

    def test_week7_schema_rejects_three_bad_call_classes_without_repair(self):
        bad_calls = [
            {"name": "pick_up", "arguments": {}},
            {"name": "navigate_to", "arguments": {"x": 1.0, "label": "W1_door"}},
            {"name": "navigate_to", "arguments": {"x": "1", "y": 1.0, "label": "W1_door"}},
        ]
        for call in bad_calls:
            valid, reason = schema_check(call)
            self.assertFalse(valid)
            self.assertTrue(reason)
        valid, reason = schema_check({"name": "stop", "arguments": {}})
        self.assertTrue(valid)
        self.assertEqual(reason, "OK")

    def test_week3_repeated_amcl_stamp_is_not_an_independent_sample(self):
        base = {"point_id": "P1", "condition": "A", "est_x": "1.1", "est_y": "2.0",
                "est_yaw": "0.1", "truth_x": "1.0", "truth_y": "2.0", "truth_yaw": "0.0",
                "truth_source": "simulator_health", "estimate_frame": "map", "truth_frame": "map"}
        rows = [{**base, "amcl_stamp_ns": "100"}, {**base, "amcl_stamp_ns": "100"},
                {**base, "amcl_stamp_ns": "200"}]
        result = analyze_localization(rows)
        self.assertEqual(result["fresh_sample_count"], 2)
        self.assertEqual(len(result["stale_repeated_rows_excluded"]), 1)
        self.assertFalse(result["required_course_groups_present"])


if __name__ == "__main__":
    unittest.main()
