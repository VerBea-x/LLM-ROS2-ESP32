"""Week-7 one-shot planner. It writes plan logs only and has no ROS executor."""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

from .deepseek_client import chat_completion
from .tools import TOOLS, to_course_call


SYSTEM = (
    "你是具身机器人规划器，只能使用给定工具。不得编造地图坐标、物品、传感器结果或技能。"
    "清单外/过期目标应说明原因或请求澄清；缺字段不得猜测补齐。stop 始终可用。"
    "当前是离线完整计划生成：一次返回整条指令需要的全部tool_calls，严格按执行顺序，不能只返回第一步而在文字里承诺剩余步骤。"
    "语义地图已注入，已知明确目标不必再次查询；指代不明应先用文字追问。"
    "capture_and_describe尚无返回结果，say只能陈述计划或说明局限，不得编造观测内容。"
)


def plan_once(instruction: str, world_state: dict[str, Any], temperature: float = 0.2) -> dict[str, Any]:
    if not 0 <= temperature <= 2:
        raise ValueError("temperature must be in [0,2]")
    messages = [
        {"role": "system", "content": SYSTEM + "\n当前世界状态 JSON：\n" +
         json.dumps(world_state, ensure_ascii=False, allow_nan=False)},
        {"role": "user", "content": instruction},
    ]
    response = chat_completion(messages, TOOLS, temperature)
    choices = response.get("choices") or []
    if not choices:
        raise ValueError("模型响应没有 choices")
    message = choices[0].get("message") or {}
    tool_calls = [to_course_call(item) for item in (message.get("tool_calls") or [])]
    return {"tool_calls": tool_calls, "refusal": message.get("refusal"),
            "content": message.get("content"), "raw_response": response}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instruction")
    parser.add_argument("--world-state", type=Path, required=True,
                        help="frozen JSON snapshot; fixture state must be labeled synthetic")
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--run-real", action="store_true", help="make exactly one API request")
    parser.add_argument("--log", type=Path, default=Path("evidence/raw/lesson7_plan_log.jsonl"))
    args = parser.parse_args()
    if not args.run_real:
        parser.error("此工具不提供假模型输出；真实规划需显式添加 --run-real")
    try:
        world = json.loads(args.world_state.read_text(encoding="utf-8"))
        plan = plan_once(args.instruction, world, args.temperature)
        row = {"timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
               "instruction": args.instruction, "temperature": args.temperature,
               "world_state": world, **plan}
        args.log.parent.mkdir(parents=True, exist_ok=True)
        with args.log.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
        # Raw output is already logged; print only the normalized proposal.
        print(json.dumps({"tool_calls": plan["tool_calls"], "refusal": plan["refusal"],
                          "content": plan["content"]}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        parser.exit(2, f"规划失败；未执行任何工具：{exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
