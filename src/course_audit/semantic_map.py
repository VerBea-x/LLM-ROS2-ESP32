"""Validate a small, auditable semantic-map JSON and compute age/state on read."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def validate(document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if document.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    if document.get("frame_id") != "map":
        errors.append("frame_id must be 'map'")
    items = document.get("items")
    if not isinstance(items, list):
        return errors + ["items must be a list"]
    labels: set[str] = set()
    for index, item in enumerate(items):
        prefix = f"items[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        label = item.get("label")
        if not isinstance(label, str) or not label.strip():
            errors.append(f"{prefix}.label is required")
        elif label in labels:
            errors.append(f"duplicate label: {label}")
        else:
            labels.add(label)
        if not isinstance(item.get("class"), str) or not item["class"].strip():
            errors.append(f"{prefix}.class is required")
        for key in ("x_m", "y_m", "last_seen_s", "tau_s"):
            value = item.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                errors.append(f"{prefix}.{key} must be a finite number")
        if isinstance(item.get("tau_s"), (int, float)) and item["tau_s"] <= 0:
            errors.append(f"{prefix}.tau_s must be > 0")
        if not isinstance(item.get("evidence_id"), str) or not item["evidence_id"].strip():
            errors.append(f"{prefix}.evidence_id is required")
    return errors


def query(document: dict[str, Any], label: str, now_s: float) -> dict[str, Any] | None:
    errors = validate(document)
    if errors:
        raise ValueError("invalid semantic map: " + "; ".join(errors))
    for item in document["items"]:
        if item["label"] == label:
            age = now_s - float(item["last_seen_s"])
            return {**item, "age_s": age,
                    "state": "fresh" if 0 <= age <= float(item["tau_s"]) else "stale"}
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("map_json", type=Path)
    parser.add_argument("--query")
    parser.add_argument("--now-s", type=float, help="current clock in the same units as last_seen_s")
    args = parser.parse_args()
    try:
        document = json.loads(args.map_json.read_text(encoding="utf-8"))
        errors = validate(document)
        if errors:
            print(json.dumps({"valid": False, "errors": errors}, ensure_ascii=False, indent=2))
            return 2
        result: dict[str, Any] = {"valid": True, "items": len(document["items"])}
        if args.query:
            if args.now_s is None or not math.isfinite(args.now_s):
                parser.error("--query requires a finite --now-s")
            result["query"] = query(document, args.query, args.now_s)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(2, f"错误：{exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
