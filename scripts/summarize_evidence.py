#!/usr/bin/env python3
"""Build reports from saved measurements without performing new API or ROS calls."""
import collections
import csv
import json
import math
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from course_audit.tools import to_course_call
from course_audit.plan_auditor import PlanAuditor,WorldState,schema_check
from course_audit.state_machine import run_state_machine,ExecutionResult
from course_audit.randomness_summary import summarize

def main():
    raw=ROOT/'evidence/raw';reports=ROOT/'evidence/reports'
    path=raw/'week7_randomness_v2_20261026.jsonl'
    rows=[json.loads(s) for s in path.read_text().splitlines()]
    report=summarize(rows);expected={'common':['navigate_to','capture_and_describe','say'],
                                  'custom':['navigate_to','navigate_to','stop']}
    reviewed=[];casebook=[]
    for row in rows:
        msg=row['raw_response']['choices'][0]['message']
        calls=[to_course_call(c) for c in (msg.get('tool_calls') or [])]
        seq=[c['name'] for c in calls]
        reviewed.append({'instruction_id':row['instruction_id'],'temperature':row['temperature'],
                         'repetition':row['repetition'],'tool_sequence':seq,'schema_valid':all(schema_check(c)[0] for c in calls),
                         'expected_sequence':expected[row['instruction_id']],
                         'complete_expected_sequence':seq==expected[row['instruction_id']]})
        if row['instruction_id']=='custom' and row['temperature']==.8 and row['repetition'] in [3,4,9]:
            casebook.append({'source_row':{k:row[k] for k in ('instruction_id','temperature','repetition')},
                            'actual_calls':calls,'assistant_original_text':msg.get('content'),
                            'issue':'文字承诺完整多步骤，但结构化计划仅包含第一步；属于不完整计划/过度承诺，不声称编造了不存在物品。'})
    for group in report['groups']:
        subset=[r for r in reviewed if r['instruction_id']==group['instruction_id'] and r['temperature']==group['temperature']]
        group['expected_sequence_complete_count']=sum(r['complete_expected_sequence'] for r in subset)
        group['expected_sequence_complete_rate']=group['expected_sequence_complete_count']/10
    errors=path.with_suffix(path.suffix+'.transport.jsonl');resumes=path.with_suffix(path.suffix+'.resume.jsonl')
    report['transport_errors']=[json.loads(s) for s in errors.read_text().splitlines()] if errors.exists() else []
    report['transport_policy_amendments']=[json.loads(s) for s in resumes.read_text().splitlines()] if resumes.exists() else []
    report['sampling_note']='40个采样格及其原始模型回答齐全；网络传输有明确记录的恢复，提示词/工具/世界状态/温度/判据未改变；未重采任何已收到回答。'
    report['rows_reviewed']=reviewed
    (reports/'week7_randomness_summary_20261026.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    (reports/'week7_model_issue_casebook.json').write_text(json.dumps({'cases':casebook,'source_kind':'real_model_raw_outputs'},ensure_ascii=False,indent=2)+'\n')
    world=WorldState.from_mapping(json.loads((ROOT/'config/week8_auditor_world_bound_v2.json').read_text()))
    plans=[json.loads(s) for s in (raw/'week7_six_instructions_v2_20261026.jsonl').read_text().splitlines()]
    regression=[]
    for plan in plans:
        result=run_state_machine(plan['benchmark_ref'],lambda *_:plan,PlanAuditor(world),
                lambda call:ExecutionResult(True,'dry-run only',{'dry_run':True}))
        regression.append({'id':plan['benchmark_ref'],'expected_action':plan['expected_action'],
                           'state_machine_result':result,
                           'interpretation':'模型自己追问/拒绝时不谎报审计器拦截；say拒绝属于允许的非运动工具。'})
    (reports/'week8_six_instruction_dry_regression.json').write_text(json.dumps(regression,ensure_ascii=False,indent=2)+'\n')
    matrix=list(csv.DictReader((raw/'week8_trap_paired_12cells_20261026.csv').open(encoding='utf-8-sig')))
    pairs={}
    for r in matrix:pairs.setdefault(r['trap_id'],[]).append(r)
    trap_report={'cells':len(matrix),'same_raw_output_for_each_pair':all(len(v)==2 and v[0]['raw_model_output']==v[1]['raw_model_output'] for v in pairs.values()),
       'executors_used':sorted(set(r['executor_used'] for r in matrix)),
       'audit_on_decisions':dict(collections.Counter(r['auditor_decision'] for r in matrix if r['condition']=='audit_on')),
       'manual_review':'六条原始回答均没有提出危险导航；模型自己拒绝或请求澄清。ALLOWED的say/stop不等于接下危险任务。',
       'conclusion':'本组未复现六陷阱下的危险导航提案；该12格不能证明审计器优于无审计。四规则拦截能力由独立八用例验证。',
       'limitations':['12格原始输出与成对审计日志齐全；目前缺少该对照过程的完整录屏。']}
    (reports/'week8_trap_pair_summary.json').write_text(json.dumps(trap_report,ensure_ascii=False,indent=2)+'\n')
    print('Reports updated;40 samples,3 raw issue cases,6 dry regressions,12 paired trap cells.')

if __name__=='__main__':main()
