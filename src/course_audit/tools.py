"""OpenAI-compatible function schemas used by the course planner."""
from __future__ import annotations


TOOLS = [
    {"type": "function", "function": {
        "name": "navigate_to",
        "description": "导航到地图坐标点。只能使用语义地图中存在且未过期的位置。不要编造坐标或目标。",
        "parameters": {"type": "object", "properties": {
            "x": {"type": "number"}, "y": {"type": "number"}, "label": {"type": "string"}},
            "required": ["x", "y", "label"], "additionalProperties": False},
    }},
    {"type": "function", "function": {
        "name": "get_semantic_map", "description": "读取当前语义地图及目标新鲜度。",
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
    }},
    {"type": "function", "function": {
        "name": "capture_and_describe", "description": "请求获取图像并描述；不得假称已看到未提供的图像。",
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
    }},
    {"type": "function", "function": {
        "name": "say", "description": "向用户播报简短文本，不控制底盘。",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}},
                        "required": ["text"], "additionalProperties": False},
    }},
    {"type": "function", "function": {
        "name": "stop", "description": "立即请求安全停止；始终可用。",
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
    }},
]


def to_course_call(tool_call: dict) -> dict:
    """Normalize one OpenAI tool_call; malformed arguments stay malformed."""
    fn = tool_call.get("function", {})
    raw_args = fn.get("arguments", {})
    if isinstance(raw_args, str):
        import json
        try:
            raw_args = json.loads(raw_args)
        except json.JSONDecodeError:
            raw_args = {"_invalid_json": raw_args}
    return {"name": fn.get("name"), "arguments": raw_args}
