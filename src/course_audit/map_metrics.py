"""Compare two ROS map images only when their declared geometry matches exactly."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml
from PIL import Image
import numpy as np


def _load_map(yaml_path: Path) -> tuple[np.ndarray, dict[str, Any]]:
    config = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    image_path = (yaml_path.parent / config["image"]).resolve()
    image = np.asarray(Image.open(image_path).convert("L"), dtype=np.uint8)
    return image, config


def compare(truth_yaml: Path, estimate_yaml: Path) -> dict:
    truth, truth_meta = _load_map(truth_yaml)
    estimate, estimate_meta = _load_map(estimate_yaml)
    if truth.shape != estimate.shape:
        raise ValueError(f"map dimensions differ: {truth.shape} vs {estimate.shape}; no implicit resampling")
    for key in ("resolution", "origin", "negate", "occupied_thresh", "free_thresh"):
        if truth_meta.get(key) != estimate_meta.get(key):
            raise ValueError(f"map metadata mismatch at {key}; align/register explicitly before scoring")
    threshold = int(round((1.0 - float(truth_meta["occupied_thresh"])) * 255))
    truth_occ, estimate_occ = truth < threshold, estimate < threshold
    tp = int(np.logical_and(truth_occ, estimate_occ).sum())
    fp = int(np.logical_and(~truth_occ, estimate_occ).sum())
    fn = int(np.logical_and(truth_occ, ~estimate_occ).sum())
    tn = int(np.logical_and(~truth_occ, ~estimate_occ).sum())
    union = tp + fp + fn
    return {"schema_version": 1, "source_kind": "map_image_comparison",
            "truth_yaml": str(truth_yaml), "estimate_yaml": str(estimate_yaml),
            "dimensions_px": list(truth.shape), "resolution_m": truth_meta["resolution"],
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "iou": tp / union if union else None,
            "warning": "像素指标不替代互评、拓扑检查或定位可信度；坐标系/尺寸不匹配时拒绝自动配准。"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth", type=Path, required=True)
    parser.add_argument("--estimate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = compare(args.truth, args.estimate)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                               encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (OSError, KeyError, ValueError, TypeError) as exc:
        parser.exit(2, f"无法比较地图：{exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
