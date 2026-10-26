"""Compute binary detector confusion metrics from independently labeled scenes."""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path


def _as_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "positive"}:
        return True
    if normalized in {"0", "false", "no", "negative"}:
        return False
    raise ValueError(f"truth_positive must be boolean-like, got {value!r}")


def calculate(rows: list[dict[str, str]], thresholds: list[float], min_scenes: int = 20) -> dict:
    if len(thresholds) != 3 or len(set(thresholds)) != 3:
        raise ValueError("预注册必须恰好提供三个不同阈值")
    if any(not math.isfinite(x) or x < 0 or x > 1 for x in thresholds):
        raise ValueError("阈值必须是[0,1]内的有限数")
    if len(rows) < min_scenes:
        raise ValueError(f"只有{len(rows)}个场景，少于要求的{min_scenes}个")
    seen: set[str] = set()
    parsed = []
    source_counts = defaultdict(int)
    for row in rows:
        sample_id = row.get("sample_id", "").strip()
        source_group = row.get("source_group", "").strip().lower()
        truth_source = row.get("truth_source", "").strip()
        if not sample_id or sample_id in seen:
            raise ValueError(f"sample_id 缺失或重复: {sample_id!r}")
        seen.add(sample_id)
        if source_group not in {"public", "custom"}:
            raise ValueError(f"{sample_id}: source_group 必须是 public 或 custom")
        if not truth_source:
            raise ValueError(f"{sample_id}: 缺少独立真值出处 truth_source")
        score = float(row["score"])
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError(f"{sample_id}: score 必须在[0,1]")
        truth = _as_bool(row["truth_positive"])
        source_counts[source_group] += 1
        parsed.append((sample_id, source_group, truth, score, truth_source))
    if source_counts["public"] < 10 or source_counts["custom"] < 10:
        raise ValueError("课程基线要求至少10个 public + 10个 custom 场景")

    results = []
    for threshold in thresholds:
        tp = fp = fn = tn = 0
        for _, _, truth, score, _ in parsed:
            predicted = score >= threshold
            tp += int(truth and predicted)
            fp += int(not truth and predicted)
            fn += int(truth and not predicted)
            tn += int(not truth and not predicted)
        results.append({
            "threshold": threshold, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "n_scenes": len(parsed),
        })
    return {
        "schema_version": 1, "source_kind": "labeled_image_evaluation",
        "n_scenes": len(parsed), "source_counts": dict(source_counts),
        "thresholds": thresholds, "results": results,
        "truth_source_ids": sorted({item[4] for item in parsed}),
        "warning": "只有输入图像/标注确实采集并独立复核后，本报告才可计作课程证据。",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--thresholds", type=float, nargs=3, required=True,
                        help="预注册的三个阈值，运行后不得为迎合结果而改动")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        with args.input.open(newline="", encoding="utf-8-sig") as stream:
            report = calculate(list(csv.DictReader(stream)), args.thresholds)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                               encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (OSError, KeyError, ValueError) as exc:
        parser.exit(2, f"无法计算：{exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
