"""Bounded plan → audit → execute → report orchestration.

The executor is injected by the caller. Tests use a harmless fake executor;
physical execution is not enabled by this module.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .plan_auditor import PlanAuditor
from .task_contract import TaskContract


MAX_REPLANS = 2


@dataclass(frozen=True)
class ExecutionResult:
    ok: bool
    reason: str
    evidence: dict[str, Any]


def run_state_machine(
    instruction: str,
    planner: Callable[[str, str | None], dict[str, Any]],
    auditor: PlanAuditor,
    executor: Callable[[dict[str, Any]], ExecutionResult],
    limitations: list[str] | None = None,
    event_sink: Callable[[dict[str, Any]], None] | None = None,
    task_contract: TaskContract | None = None,
) -> dict[str, Any]:
    """Run one atomic plan; no call executes unless the whole plan passes audit."""
    events: list[dict[str, Any]] = []

    def emit(event_type: str, **payload: Any) -> None:
        event = {"type": event_type, **payload}
        events.append(event)
        if event_sink:
            event_sink(event)

    feedback: str | None = None
    replan_count = 0
    final: dict[str, Any] | None = None

    while True:
        try:
            plan = planner(instruction, feedback)
        except Exception as exc:
            final={'result':'PLANNING_FAILED','evidence':[{'kind':'planner_error','reason':str(exc)}]}
            emit('report',**final);break
        if not isinstance(plan,dict):
            final={'result':'REJECTED','evidence':[{'kind':'schema','reason':'规划器输出必须是对象'}]}
            emit('report',**final);break
        emit("plan", instruction=instruction, plan=plan, replan_count=replan_count)
        calls = plan.get("tool_calls", [])
        if not isinstance(calls, list):
            final = {"result": "REJECTED", "evidence": [{"kind": "schema", "reason": "tool_calls 必须是数组"}]}
            emit("report", result=final["result"], evidence=final["evidence"])
            break
        if not calls:
            response = plan.get("refusal") or plan.get("content") or "规划器未给出工具调用或拒绝说明。"
            final = {"result": "REJECTED", "evidence": [{"kind": "planner_response", "value": response}]}
            emit("report", result=final["result"], evidence=final["evidence"])
            break

        audits = [auditor.audit(call) for call in calls]
        for index, (call, audit) in enumerate(zip(calls, audits, strict=True)):
            emit("audit", index=index, call=call, decision=audit.as_dict())
        if not all(audit.allowed for audit in audits):
            # Atomic rejection: even earlier valid calls are not executed.
            final = {
                "result": "REJECTED",
                "evidence": [audit.as_dict() for audit in audits if not audit.allowed],
            }
            emit("report", result=final["result"], evidence=final["evidence"])
            break

        if task_contract is not None:
            decision=task_contract.check(calls)
            emit('audit',stage='task_contract',decision=decision)
            if not decision['allowed']:
                final={'result':'REJECTED','evidence':[decision]}
                emit('report',**final);break

        call_results = []
        failed = False
        for index, call in enumerate(calls):
            result = executor(call)
            record = {"index": index, "call": call, "ok": result.ok,
                      "reason": result.reason, "evidence": result.evidence}
            call_results.append(record)
            emit("exec", **record)
            if not result.ok:
                failed = True
                feedback = result.reason
                break

        if failed:
            if replan_count < MAX_REPLANS:
                replan_count += 1
                continue
            final = {"result": "REPLAN_LIMIT", "evidence": call_results,
                     "replan_count": replan_count}
            emit("report", result=final["result"], evidence=final["evidence"],
                 replan_count=replan_count)
            break

        result_name='STOPPED' if task_contract is not None and [c['name'] for c in calls]==['stop'] else 'COMPLETED'
        final = {"result": result_name, "evidence": call_results,
                 "replan_count": replan_count}
        emit("report", result=final["result"], evidence=final["evidence"],
             replan_count=replan_count)
        break

    return {
        **(final or {}),
        "report": {
            "result": (final or {}).get("result", "UNKNOWN"),
            "evidence": (final or {}).get("evidence", []),
            "limitations": limitations or [],
        },
        "events": events,
    }


def append_jsonl(path: str | Path) -> Callable[[dict[str, Any]], None]:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    def write(event: dict[str, Any]) -> None:
        with target.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")

    return write
