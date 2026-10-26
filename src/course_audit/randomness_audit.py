"""Run the frozen week-7 2-instruction × 2-temperature × 10-call protocol.

Requires --run-real and all three model environment variables. No retries are
performed; an interrupted run is incomplete and must be reported as such.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import time
from pathlib import Path

from .deepseek_client import chat_completion, request_options
from .tools import TOOLS
from .llm_planner import SYSTEM


COMMON_INSTRUCTION = "到桌子那，看看上面有什么"


def _messages(instruction: str, world_state: str) -> list[dict[str, str]]:
    system = (
        SYSTEM + "\n世界状态如下：\n" + world_state
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": instruction}]


def run(custom_instruction: str, world_state: str, output: Path, transport_attempts: int = 1,
        resume_after_network: bool = False) -> None:
    if transport_attempts not in (1,2):raise ValueError('transport_attempts must be1 or2')
    protocol = {
        "instructions": [("common", COMMON_INSTRUCTION), ("custom", custom_instruction)],
        "temperatures": [0.2, 0.8], "repetitions": 10,
        "tools": TOOLS,
        "system_message": _messages("", world_state)[0],
        "model": os.environ.get("LLM_MODEL", ""),
        "base_url": os.environ.get("LLM_BASE_URL", ""),
        "request_options": request_options(),
        "transport_policy": {"max_attempts_per_cell":transport_attempts,
                             "retry_only":"network/timeout without received model output; never resample an answer",
                             "error_log":output.name+'.transport.jsonl'},
    }
    fingerprint = hashlib.sha256(json.dumps(protocol, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    existing=[]
    if output.exists() and not resume_after_network:
        raise FileExistsError("结果文件已存在；为避免重复调用或混入不同实验，请使用新的输出路径")
    protocol_path=output.with_suffix(output.suffix+'.protocol.json')
    if resume_after_network:
        frozen=json.loads(protocol_path.read_text())
        if frozen['protocol_sha256']!=fingerprint:raise ValueError('Frozen protocol mismatch; refuse continuation')
        existing=[json.loads(s) for s in output.read_text().splitlines() if s.strip()]
        expected=[(i,t,r) for i,_ in protocol['instructions'] for t in protocol['temperatures'] for r in range(1,11)]
        actual=[(r['instruction_id'],r['temperature'],r['repetition']) for r in existing]
        if actual!=expected[:len(actual)] or len(actual)>=40:raise ValueError('Not a valid incomplete prefix')
        if any(r['protocol_sha256']!=fingerprint for r in existing):raise ValueError('Mixed protocol hashes')
        errors=[json.loads(s) for s in output.with_suffix(output.suffix+'.transport.jsonl').read_text().splitlines()]
        last=errors[-1]
        if not last['network_failure'] or (last['instruction_id'],last['temperature'],last['repetition'])!=expected[len(actual)]:
            raise ValueError('Continuation only after logged network failure without model output')
        amendment={'timestamp_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'reason':'resume missing cells after logged network interruption',
                   'sampling_protocol_sha256':fingerprint,'received_rows_preserved':len(existing),
                   'transport_policy_amendment':f'At most {transport_attempts} extra transport attempts per remaining cell in this invocation',
                   'no_received_model_answer_resampled':True}
        with output.with_suffix(output.suffix+'.resume.jsonl').open('a') as f:f.write(json.dumps(amendment,ensure_ascii=False)+'\n')
    else:
        protocol_path.write_text(json.dumps({"protocol_sha256": fingerprint, **protocol}, ensure_ascii=False, indent=2) + "\n")
    completed={(r['instruction_id'],r['temperature'],r['repetition']) for r in existing}
    with output.open("a" if resume_after_network else "x", encoding="utf-8") as stream:
        for instruction_id, instruction in protocol["instructions"]:
            for temperature in protocol["temperatures"]:
                for repetition in range(1, 11):
                    if (instruction_id,temperature,repetition) in completed:continue
                    response=None
                    for attempt in range(1,transport_attempts+1):
                        try:
                            response = chat_completion(_messages(instruction, world_state), TOOLS, temperature)
                            break
                        except Exception as exc:
                            network=isinstance(exc,TimeoutError) or str(exc).startswith('模型 API 网络错误:')
                            error={'timestamp_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
                                   'instruction_id':instruction_id,'temperature':temperature,'repetition':repetition,
                                   'attempt':attempt,'network_failure':network,'error':str(exc)}
                            with output.with_suffix(output.suffix+'.transport.jsonl').open('a') as f:
                                f.write(json.dumps(error,ensure_ascii=False)+'\n')
                            if not network or attempt==transport_attempts:raise
                            time.sleep(1)
                    row = {
                        "schema_version": 1,
                        "protocol_sha256": fingerprint,
                        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                        "instruction_id": instruction_id,
                        "instruction": instruction,
                        "temperature": temperature,
                        "repetition": repetition,
                        "raw_response": response,
                    }
                    stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
                    stream.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-real", action="store_true", help="explicitly make the 40 planned API calls")
    parser.add_argument("--custom-instruction", help="the group's frozen second instruction")
    parser.add_argument("--world-state", help="frozen, non-secret world-state summary", default="语义地图摘要由操作者在正式实验前冻结。")
    parser.add_argument("--world-file",type=Path,help="read exact frozen world JSON for all40 requests")
    parser.add_argument('--transport-attempts',type=int,choices=[1,2],default=1,
                        help='freeze before sampling; only transport failures may be retried, all logged')
    parser.add_argument('--resume-after-network',action='store_true',
                        help='append a visible transport-policy amendment; verify original protocol and preserve every received response')
    parser.add_argument("--output", type=Path, default=Path("evidence/raw/lesson7_randomness.jsonl"))
    args = parser.parse_args()
    if not args.run_real:
        parser.error("离线复核不会调用模型；正式采样必须显式添加 --run-real")
    if not args.custom_instruction:
        parser.error("请先冻结第二条自选指令，再使用 --custom-instruction")
    try:
        world=args.world_file.read_text(encoding='utf-8') if args.world_file else args.world_state
        run(args.custom_instruction, world, args.output,args.transport_attempts,args.resume_after_network)
    except Exception as exc:
        parser.exit(2, f"采样按冻结的传输策略中止；已收到的模型输出保留，不自动重采：{exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
