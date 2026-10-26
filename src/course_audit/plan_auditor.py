"""Fail-closed Plan Auditor for the course's five-tool proposal interface.

This module is deliberately independent of ROS. It can be tested offline and
later supplied with a real map, semantic map, and resource snapshot.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


WHITELIST = {
    "navigate_to",
    "get_semantic_map",
    "capture_and_describe",
    "say",
    "stop",
}

SCHEMAS: dict[str, dict[str, Any]] = {
    "navigate_to": {
        "required": {"x", "y", "label"},
        "properties": {"x": (int, float), "y": (int, float), "label": str},
    },
    "get_semantic_map": {"required": set(), "properties": {}},
    "capture_and_describe": {"required": set(), "properties": {}},
    "say": {"required": {"text"}, "properties": {"text": str}},
    "stop": {"required": set(), "properties": {}},
}


@dataclass(frozen=True)
class Circle:
    x: float
    y: float
    radius: float


@dataclass(frozen=True)
class SemanticItem:
    last_seen_s: float
    x_m: float | None = None
    y_m: float | None = None


@dataclass(frozen=True)
class OccupancyGridSnapshot:
    width: int
    height: int
    resolution_m: float
    origin_x_m: float
    origin_y_m: float
    origin_yaw_rad: float
    data: tuple[int, ...]
    occupied_threshold: int = 50

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "OccupancyGridSnapshot":
        grid = cls(
            width=int(data["width"]), height=int(data["height"]),
            resolution_m=float(data["resolution_m"]),
            origin_x_m=float(data.get("origin_x_m", 0.0)),
            origin_y_m=float(data.get("origin_y_m", 0.0)),
            origin_yaw_rad=float(data.get("origin_yaw_rad", 0.0)),
            data=tuple(int(value) for value in data["data"]),
            occupied_threshold=int(data.get("occupied_threshold", 50)),
        )
        if grid.width <= 0 or grid.height <= 0 or grid.resolution_m <= 0:
            raise ValueError("occupancy grid dimensions/resolution must be positive")
        if len(grid.data) != grid.width * grid.height:
            raise ValueError("occupancy grid data length does not match width × height")
        return grid

    def cell_value(self, x_m: float, y_m: float) -> int | None:
        """Return occupancy at world coordinates; None means outside the grid."""
        dx, dy = x_m - self.origin_x_m, y_m - self.origin_y_m
        c, s = math.cos(self.origin_yaw_rad), math.sin(self.origin_yaw_rad)
        local_x, local_y = c * dx + s * dy, -s * dx + c * dy
        mx, my = math.floor(local_x / self.resolution_m), math.floor(local_y / self.resolution_m)
        if mx < 0 or my < 0 or mx >= self.width or my >= self.height:
            return None
        return self.data[my * self.width + mx]


@dataclass(frozen=True)
class WorldState:
    """Current facts consumed by the auditor; missing facts fail closed."""

    bounds_m: tuple[float, float, float, float]
    obstacles: tuple[Circle, ...]
    semantic_items: dict[str, SemanticItem]
    tau_s: dict[str, float]
    now_s: float
    battery_pct: float | None
    estimated_task_s: float | None
    remaining_budget_s: float | None
    max_linear_speed_mps: float
    max_angular_speed_rps: float
    occupancy_grid: OccupancyGridSnapshot | None = None
    provenance: dict[str, Any] = field(default_factory=dict)
    fixture_only: bool = False

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "WorldState":
        b = data["bounds_m"]
        if len(b) != 4:
            raise ValueError("bounds_m must be [xmin, xmax, ymin, ymax]")
        return cls(
            bounds_m=tuple(float(x) for x in b),
            obstacles=tuple(Circle(float(o["x"]), float(o["y"]), float(o["radius"]))
                            for o in data.get("obstacles", [])),
            semantic_items={k: SemanticItem(float(v["last_seen_s"]),
                                           float(v['x_m']) if v.get('x_m') is not None else None,
                                           float(v['y_m']) if v.get('y_m') is not None else None)
                            for k, v in data.get("semantic_items", {}).items()},
            tau_s={k: float(v) for k, v in data.get("tau_s", {}).items()},
            now_s=float(data["now_s"]),
            battery_pct=None if data.get("battery_pct") is None else float(data["battery_pct"]),
            estimated_task_s=(None if data.get("estimated_task_s") is None
                               else float(data["estimated_task_s"])),
            remaining_budget_s=(None if data.get("remaining_budget_s") is None
                                else float(data["remaining_budget_s"])),
            max_linear_speed_mps=float(data["max_linear_speed_mps"]),
            max_angular_speed_rps=float(data["max_angular_speed_rps"]),
            occupancy_grid=(OccupancyGridSnapshot.from_mapping(data["occupancy_grid"])
                            if data.get("occupancy_grid") else None),
            provenance=dict(data.get("provenance", {})),
            fixture_only=bool(data.get("fixture_only", False)),
        )


@dataclass(frozen=True)
class AuditResult:
    allowed: bool
    rule_id: str
    reason: str
    evidence: dict[str, Any] = field(default_factory=dict)
    correction: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "rule_id": self.rule_id,
            "reason": self.reason,
            "evidence": self.evidence,
            "correction": self.correction,
        }


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _schema_error(name: str, args: Any) -> str | None:
    schema = SCHEMAS[name]
    if not isinstance(args, dict):
        return "arguments 必须是 JSON 对象"
    unknown = set(args) - set(schema["properties"])
    if unknown:
        return f"不允许的字段: {', '.join(sorted(unknown))}"
    missing = schema["required"] - set(args)
    if missing:
        return f"缺少必填字段: {', '.join(sorted(missing))}"
    for key, value in args.items():
        expected = schema["properties"][key]
        if expected in ((int, float),):
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return f"字段 {key} 必须是数值"
        elif not isinstance(value, expected):
            return f"字段 {key} 类型错误"
    return None


def schema_check(call: dict[str, Any]) -> tuple[bool, str]:
    """Week-7 hard gate: whitelist first, exact fields/types second; never repairs."""
    if not isinstance(call, dict):
        return False, "工具调用必须是对象"
    name = call.get("name")
    if not isinstance(name, str) or name not in WHITELIST:
        return False, f"编造工具: {name}"
    error = _schema_error(name, call.get("arguments", {}))
    if error:
        return False, f"参数非法: {error}"
    return True, "OK"


class PlanAuditor:
    """Whitelist + four evidence-linked checks; no guessing or auto-repair."""

    MIN_BATTERY_PCT = 15.0

    def __init__(self, world: WorldState):
        self.world = world

    def audit(self, call: dict[str, Any]) -> AuditResult:
        if not isinstance(call, dict):
            return AuditResult(False, "SCHEMA", "工具调用必须是对象；未执行。", {"received_type": type(call).__name__})
        name = call.get("name")
        args = call.get("arguments", {})

        # Course rule: unknown tool names are rejected before the four rules.
        if not isinstance(name, str) or name not in WHITELIST:
            return AuditResult(
                False, "WHITELIST",
                f"缺少可执行工具 `{name}`；当前允许工具为 {', '.join(sorted(WHITELIST))}；请改用清单内工具或重新描述任务。",
                {"tool_name": name, "allowed_tools": sorted(WHITELIST)},
                "选择已列出的能力，或提出系统当前支持的任务。",
            )

        valid_schema, schema_reason = schema_check(call)
        if not valid_schema:
            # The schema is the hard parameter allowlist introduced in week 7.
            return AuditResult(
                False, "SCHEMA",
                f"参数未满足工具契约：{schema_reason}；`{name}` 的字段定义见冻结 Schema；请按字段和类型重提，不会自动补值。",
                {"tool_name": name, "schema_error": schema_reason},
                "按已声明字段重提；缺失值不得由系统猜测。",
            )

        # stop remains available regardless of map, battery, or task budget.
        if name == "stop":
            return AuditResult(True, "SAFE_STOP", "stop 属于无条件安全工具，允许调用。", {"tool_name": name})
        if name != "navigate_to":
            return AuditResult(True, "WHITELIST", f"工具 `{name}` 在白名单且参数符合 Schema。", {"tool_name": name})

        x, y, label = args["x"], args["y"], args["label"]
        # R3 finite/type check is performed before map math so NaN cannot reach it.
        if not _finite_number(x) or not _finite_number(y):
            return AuditResult(
                False, "R3",
                "缺少有限坐标值；地图数值域要求 x、y 为有限数；请从语义地图选择有效坐标，不要使用 NaN/Infinity。",
                {"x": repr(x), "y": repr(y)},
                "重新选择有限、可验证的目标坐标。",
            )

        xmin, xmax, ymin, ymax = self.world.bounds_m
        if not (xmin <= x <= xmax and ymin <= y <= ymax):
            return AuditResult(
                False, "R1",
                f"目标 ({x:.3f}, {y:.3f}) 超出地图边界；可行范围 x=[{xmin:.3f},{xmax:.3f}], y=[{ymin:.3f},{ymax:.3f}]；请改选边界内目标。",
                {"target_m": [x, y], "bounds_m": list(self.world.bounds_m)},
                "改选地图范围内的目标。",
            )
        if self.world.occupancy_grid is not None:
            cell = self.world.occupancy_grid.cell_value(x, y)
            if cell is None or cell < 0 or cell >= self.world.occupancy_grid.occupied_threshold:
                if cell is None or cell < 0:
                    occupancy_reason = "目标位于地图外或未知栅格"
                else:
                    occupancy_reason = "目标栅格不是已确认空闲区"
                return AuditResult(
                    False, "R1",
                    f"{occupancy_reason}；目标 ({x:.3f}, {y:.3f}) 的占据值为 {cell}（放行阈值 < {self.world.occupancy_grid.occupied_threshold}）；请改选已知空闲区。",
                    {"target_m": [x, y], "occupancy_value": cell,
                     "occupied_threshold": self.world.occupancy_grid.occupied_threshold,
                     "map_source": self.world.provenance.get("map_source")},
                    "选择地图中明确标记为空闲的可行点。",
                )
        else:
            for obstacle in self.world.obstacles:
                distance = math.hypot(x - obstacle.x, y - obstacle.y)
                if distance <= obstacle.radius:
                    return AuditResult(
                        False, "R1",
                        f"目标 ({x:.3f}, {y:.3f}) 落在占据区；目标到障碍中心距离 {distance:.3f} m，障碍半径 {obstacle.radius:.3f} m；请改选空闲区域。",
                        {"target_m": [x, y], "obstacle_center_m": [obstacle.x, obstacle.y],
                         "distance_m": distance, "radius_m": obstacle.radius,
                         "map_source": self.world.provenance.get("map_source")},
                        "选择地图中未占据的可行点。",
                    )

        if label not in self.world.semantic_items or label not in self.world.tau_s:
            labels = sorted(self.world.semantic_items)
            return AuditResult(
                False, "R2",
                f"语义目标 `{label}` 不存在或没有新鲜度阈值；当前清单为 {labels}；请改用清单中的有效目标。",
                {"label": label, "available_labels": labels, "tau_defined": label in self.world.tau_s},
                "改用清单内且有 τ 依据的目标。",
            )
        item = self.world.semantic_items[label]
        tau = self.world.tau_s[label]
        age = self.world.now_s - item.last_seen_s
        if not all(_finite_number(v) for v in (tau, age)) or tau <= 0 or age < 0 or age > tau:
            return AuditResult(
                False, "R2",
                f"语义目标 `{label}` 已过期；age={age:.1f}s，τ={tau:.1f}s；当前可用目标为 {labels_with_freshness(self.world)}；请改选新鲜目标或重新观测。",
                {"label": label, "age_s": age, "tau_s": tau,
                 "last_seen_s": item.last_seen_s, "now_s": self.world.now_s},
                "重新观测目标或改选仍在有效期内的目标。",
            )
        if item.x_m is not None or item.y_m is not None:
            if (not _finite_number(item.x_m) or not _finite_number(item.y_m) or
                    math.hypot(x-item.x_m,y-item.y_m)>0.05):
                return AuditResult(False,'R3',f'目标坐标与语义登记不一致；{label}登记为({item.x_m},{item.y_m})，请求为({x},{y})，允许差≤0.05m。',
                                   {'label':label,'registered':[item.x_m,item.y_m],'requested':[x,y],'tolerance_m':.05},
                                   '使用语义地图登记坐标，不猜测修复。')

        missing = [key for key, value in {
            "battery_pct": self.world.battery_pct,
            "estimated_task_s": self.world.estimated_task_s,
            "remaining_budget_s": self.world.remaining_budget_s,
        }.items() if value is None]
        if missing:
            return AuditResult(
                False, "R4",
                f"缺少资源可行性数据：{missing}；放行要求电量≥{self.MIN_BATTERY_PCT:.0f}%且预估耗时不超过剩余预算；请先刷新资源状态。",
                {"missing_fields": missing, "minimum_battery_pct": self.MIN_BATTERY_PCT},
                "先取得电量和任务预算的当前读数，再重新规划。",
            )
        assert self.world.battery_pct is not None
        assert self.world.estimated_task_s is not None
        assert self.world.remaining_budget_s is not None
        resources = (self.world.battery_pct, self.world.estimated_task_s, self.world.remaining_budget_s)
        if (not all(_finite_number(v) for v in resources) or
                not 0 <= self.world.battery_pct <= 100 or
                self.world.estimated_task_s < 0 or self.world.remaining_budget_s < 0):
            return AuditResult(False, "R4", "资源数据含非有限数或超出有效范围；请刷新状态。",
                               {"battery_pct": repr(resources[0]), "estimated_task_s": repr(resources[1]),
                                "remaining_budget_s": repr(resources[2])})
        if self.world.battery_pct < self.MIN_BATTERY_PCT:
            return AuditResult(
                False, "R4",
                f"电量 {self.world.battery_pct:.1f}% 低于放行阈值 {self.MIN_BATTERY_PCT:.1f}%；当前任务需要 {self.world.estimated_task_s:.1f}s，任务预算 {self.world.remaining_budget_s:.1f}s；请先充电或改选无需移动的任务。",
                {"battery_pct": self.world.battery_pct,
                 "minimum_battery_pct": self.MIN_BATTERY_PCT,
                 "estimated_task_s": self.world.estimated_task_s,
                 "remaining_budget_s": self.world.remaining_budget_s},
                "充电后刷新状态，或选择不需要移动的任务。",
            )
        if self.world.estimated_task_s > self.world.remaining_budget_s:
            return AuditResult(
                False, "R4",
                f"预估耗时 {self.world.estimated_task_s:.1f}s 超出剩余预算 {self.world.remaining_budget_s:.1f}s；电量为 {self.world.battery_pct:.1f}%（阈值 {self.MIN_BATTERY_PCT:.1f}%）；请缩短任务或增加可用预算。",
                {"battery_pct": self.world.battery_pct,
                 "estimated_task_s": self.world.estimated_task_s,
                 "remaining_budget_s": self.world.remaining_budget_s},
                "拆短任务或在条件允许时重新规划预算。",
            )

        return AuditResult(
            True, "PASS",
            f"目标 `{label}` 在边界内且未落入已知占据区；age={age:.1f}s≤τ={tau:.1f}s；电量 {self.world.battery_pct:.1f}%，预估耗时 {self.world.estimated_task_s:.1f}s/预算 {self.world.remaining_budget_s:.1f}s。",
            {"label": label, "target_m": [x, y], "age_s": age, "tau_s": tau,
             "battery_pct": self.world.battery_pct,
             "estimated_task_s": self.world.estimated_task_s,
             "remaining_budget_s": self.world.remaining_budget_s},
        )


def labels_with_freshness(world: WorldState) -> list[str]:
    result = []
    for label, item in world.semantic_items.items():
        tau = world.tau_s.get(label)
        age = world.now_s - item.last_seen_s
        if tau is not None and 0 <= age <= tau:
            result.append(label)
    return sorted(result)


def _json_safe(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _fixture_cases(world: WorldState) -> dict[str, dict[str, Any]]:
    good = {"name": "navigate_to", "arguments": {"x": 2.0, "y": 2.0, "label": "W1_door"}}
    cases = {
        "R1_GOOD": (good, world),
        "R1_BAD_OCCUPIED": ({"name": "navigate_to", "arguments": {"x": 5.0, "y": 5.0, "label": "W1_door"}}, world),
        "R2_GOOD": (good, world),
        "R2_BAD_STALE": ({"name": "navigate_to", "arguments": {"x": 7.0, "y": 7.0, "label": "W3_podium"}}, world),
        "R2_BAD_UNKNOWN": ({"name": "navigate_to", "arguments": {"x": 2.0, "y": 2.0, "label": "W9_unknown"}}, world),
        "R3_GOOD": (good, world),
        "R3_BAD_NONFINITE": ({"name": "navigate_to", "arguments": {"x": float("nan"), "y": 2.0, "label": "W1_door"}}, world),
        "R4_GOOD": (good, world),
        "R4_BAD_LOW_BATTERY": (good, WorldState(**{**world.__dict__, "battery_pct": 10.0})),
        "R4_BAD_BUDGET": (good, WorldState(**{**world.__dict__, "estimated_task_s": 90.0})),
        "WHITELIST_BAD": ({"name": "pick_up", "arguments": {}}, world),
        "STOP_LOW_BATTERY": ({"name": "stop", "arguments": {}}, WorldState(**{**world.__dict__, "battery_pct": 0.0})),
    }
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, help="load a world state JSON; synthetic fixtures are not evidence")
    parser.add_argument("--case", help="run a named built-in fixture case")
    args = parser.parse_args()
    try:
        if args.fixture:
            data = json.loads(args.fixture.read_text(encoding="utf-8"))
            world = WorldState.from_mapping(data)
        else:
            raise ValueError("--fixture is required; never assume live world state")
        if args.case:
            call, case_world = _fixture_cases(world)[args.case]
            result = PlanAuditor(case_world).audit(call)
            print(json.dumps({"fixture_only": world.fixture_only, "case": args.case,
                              "call": _json_safe(call), "audit": _json_safe(result.as_dict())}, ensure_ascii=False, indent=2,
                             allow_nan=False))
            return 0
        call = json.load(sys.stdin)
        result = PlanAuditor(world).audit(call)
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2, allow_nan=False))
        return 0 if result.allowed else 2
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
