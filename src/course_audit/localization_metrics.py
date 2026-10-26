"""Score localization estimates against independent truth without counting stale repeats."""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev


REQUIRED = {"point_id", "condition", "amcl_stamp_ns", "est_x", "est_y", "est_yaw",
            "truth_x", "truth_y", "truth_yaw", "truth_source", "estimate_frame", "truth_frame"}


def angle_error_deg(a: float, b: float) -> float:
    return math.degrees(math.atan2(math.sin(a - b), math.cos(a - b)))


def analyze(rows: list[dict[str, str]]) -> dict:
    if rows and not REQUIRED.issubset(rows[0]):
        raise ValueError("缺少列: " + ", ".join(sorted(REQUIRED - set(rows[0])))
                         + "; 需要记录 AMCL 时间戳和真值出处")
    seen: set[tuple[str, str, str]] = set()
    groups = defaultdict(list)
    stale = []
    for line_no, row in enumerate(rows, start=2):
        point, condition = row["point_id"].strip(), row["condition"].strip().upper()
        stamp = row["amcl_stamp_ns"].strip()
        if not point or condition not in {"A", "B"} or not stamp:
            raise ValueError(f"line {line_no}: point_id/condition/amcl_stamp_ns 无效")
        key = (point, condition, stamp)
        if key in seen:
            stale.append({"line": line_no, "point_id": point, "condition": condition,
                          "amcl_stamp_ns": stamp, "reason": "same estimate timestamp repeated; excluded"})
            continue
        seen.add(key)
        if not row["truth_source"].strip():
            raise ValueError(f"line {line_no}: truth_source is required")
        if row["estimate_frame"].strip() != row["truth_frame"].strip():
            raise ValueError(f"line {line_no}: frame mismatch; apply and record a validated transform first")
        values = {key: float(row[key]) for key in ("est_x", "est_y", "est_yaw", "truth_x", "truth_y", "truth_yaw")}
        if any(not math.isfinite(value) for value in values.values()):
            raise ValueError(f"line {line_no}: non-finite pose value")
        position_error = math.hypot(values["est_x"] - values["truth_x"],
                                    values["est_y"] - values["truth_y"])
        yaw_error = angle_error_deg(values["est_yaw"], values["truth_yaw"])
        groups[(point, condition)].append({"position_error_m": position_error,
                                           "yaw_error_deg": yaw_error,
                                           "truth_source": row["truth_source"].strip()})
    summaries = []
    for point in sorted({key[0] for key in groups}):
        for condition in ("A", "B"):
            values = groups.get((point, condition), [])
            if values:
                errors = [item["position_error_m"] for item in values]
                yaw = [abs(item["yaw_error_deg"]) for item in values]
                summaries.append({"point_id": point, "condition": condition,
                                  "n_fresh": len(values), "mean_position_error_m": mean(errors),
                                  "max_position_error_m": max(errors),
                                  "position_error_population_sd_m": pstdev(errors) if len(errors)>1 else None,
                                  "mean_abs_yaw_error_deg": mean(yaw),
                                  "truth_sources": sorted({item["truth_source"] for item in values})})
            else:
                summaries.append({"point_id": point, "condition": condition, "n_fresh": 0,
                                  "status": "missing samples"})
    expected_groups = {(f"P{i}", condition) for i in range(1, 6) for condition in ("A", "B")}
    present_groups = set(groups)
    missing_groups = sorted([f"{point}{condition}" for point, condition in expected_groups - present_groups])
    return {"schema_version": 1, "source_kind": "localization_estimate_vs_independent_truth",
            "fresh_sample_count": sum(len(v) for v in groups.values()),
            "stale_repeated_rows_excluded": stale, "group_summaries": summaries,
            "required_course_groups_present": not missing_groups,
            "missing_course_groups": missing_groups,
            "note": "AMCL covariance is not used as true position error; stale repeated timestamps are excluded. Fresh timestamps do not prove statistical independence; a single sample has no dispersion estimate."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        with args.input.open(newline="", encoding="utf-8-sig") as stream:
            result = analyze(list(csv.DictReader(stream)))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                               encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0 if result["required_course_groups_present"] else 1
    except (OSError, KeyError, ValueError) as exc:
        parser.exit(2, f"无法计算定位指标：{exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
