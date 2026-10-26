#!/usr/bin/env python3
"""Replay recorded semantic observations through R2; never calls ROS or a model."""
import datetime as dt
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from course_audit.plan_auditor import PlanAuditor,WorldState
from course_audit.semantic_world import semantic_world_fields

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'evidence/raw/week6_ros_lab_v3/lab_result.json')
    parser.add_argument('--output',type=Path,default=ROOT/'evidence/reports/week6_to_week8_auditor_bridge.json')
    args=parser.parse_args();source=args.source.resolve()
    lab=json.loads(source.read_text());base=json.loads((ROOT/'config/week8_auditor_world_bound_v2.json').read_text())
    rows=[]
    for name,expected in [('fresh_snapshot',True),('stale_snapshot',False)]:
        snap=lab[name];world={**base,**semantic_world_fields(snap),
          'provenance':{**base['provenance'],'semantics':str(source.relative_to(ROOT)),
                         'semantic_source_kind':snap['source_kind']}}
        auditor=PlanAuditor(WorldState.from_mapping(world))
        for item in snap['items']:
            call={'name':'navigate_to','arguments':{'x':item['x'],'y':item['y'],'label':item.get('target_name',item['label'])}}
            result=auditor.audit(call).as_dict()
            rows.append({'snapshot':name,'call':call,'decision':result,
                         'passed':result['allowed']==expected and (expected or result['rule_id']=='R2')})
    report={'source_kind':'recorded_synthetic_ROS_observation_to_auditor_replay',
      'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'implementation_version':'strict_semantic_world_v2','checks':rows,
      'all_checks_passed':all(r['passed'] for r in rows),
      'limitations':['Offline bridge replay; not a continuously connected perception/navigation execution.',
                     'Map is the existing known-map simulation snapshot, not the improved SLAM map.',
                     'Synthetic movement-derived tau and declared simulated resources; no field measurements.']}
    out=args.output
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'passed':sum(r['passed'] for r in rows),'total':len(rows)}))
    return 0 if report['all_checks_passed'] else 1
if __name__=='__main__':raise SystemExit(main())
