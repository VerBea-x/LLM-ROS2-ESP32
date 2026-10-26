#!/usr/bin/env python3
"""Replay original40 replies through new pre-execution contracts; no API or ROS."""
import collections,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from course_audit.task_contract import TaskContract
from course_audit.tools import to_course_call
from course_audit.plan_auditor import PlanAuditor,WorldState
from course_audit.state_machine import run_state_machine,ExecutionResult

source=ROOT/'evidence/raw/week7_randomness_v2_20261026.jsonl';contracts=json.loads((ROOT/'config/task_contracts_v3.json').read_text())
world=WorldState.from_mapping(json.loads((ROOT/'config/week8_auditor_world_bound_v2.json').read_text()));rows=[]
for line in source.read_text().splitlines():
    raw=json.loads(line);msg=raw['raw_response']['choices'][0]['message'];calls=[to_course_call(c) for c in msg.get('tool_calls',[])]
    text='到桌子那，看看上面有什么' if raw['instruction_id']=='common' else '先去门口，再去充电站，最后停下'
    executions=[]
    output=run_state_machine(text,lambda *_:{'tool_calls':calls,'content':msg.get('content')},PlanAuditor(world),
      lambda c:executions.append(c) or ExecutionResult(True,'offline replay only',{'dry_run':True}),
      task_contract=TaskContract.from_mapping(contracts[text]),limitations=['Replay of stored real-model output, no new model call or motor execution.'])
    rows.append({'instruction_id':raw['instruction_id'],'temperature':raw['temperature'],'repetition':raw['repetition'],
                 'result':output['result'],'executed_dry_run_calls':len(executions),
                 'decisions':[e['decision'] for e in output['events'] if e['type']=='audit'],'report':output['report']})
report={'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'source_kind':'frozen_real_model_output_replay',
 'implementation_version':'task_contract_v3','counts':dict(collections.Counter(r['result'] for r in rows)),'rows':rows,
 'limitations':['Original40-response statistics unchanged.','Capability rejection addresses unavailable camera, not model accuracy.',
                'Exact supported task contracts; arbitrary language/semantic equivalence is not inferred.']}
(ROOT/'evidence/reports/week8_task_contract_replay_v3.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(report['counts'])
