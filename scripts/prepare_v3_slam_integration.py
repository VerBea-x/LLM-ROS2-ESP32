#!/usr/bin/env python3
"""Freeze a previously received real-model plan against the current SLAM map."""
import argparse,hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from course_audit.plan_auditor import PlanAuditor,WorldState
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--benchmark',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--map-snapshot',type=Path);a=p.parse_args()
if a.output.exists():p.error('new output directory required')
a.output.mkdir(parents=True)
source=ROOT/'evidence/raw/week8_integration/20261026T021310Z/real_model_agent_events.jsonl'
e=next(json.loads(s) for s in source.read_text().splitlines() if json.loads(s).get('type')=='plan')
plan=e['plan'];text=e['instruction'];now=time.time();map_source=a.map_snapshot or a.benchmark/'round2/map_snapshot.json';grid=json.loads(map_source.read_text())
world={'bounds_m':[0,10,0,10],'obstacles':[],
 'semantic_items':{'W1_door':{'x_m':7.,'y_m':6.,'last_seen_s':now}},'tau_s':{'W1_door':86400.},
 'now_s':now,'battery_pct':60,'estimated_task_s':30,'remaining_budget_s':60,
 'max_linear_speed_mps':1.,'max_angular_speed_rps':1.5,'occupancy_grid':grid,'fixture_only':False,
 'provenance':{'map_source':str(map_source),
  'semantics':'Declared fixed virtual waypoint, not camera detection.',
  'resources':'Explicit simulation settings, no physical telemetry.',
  'plan_source':str(source),'plan_source_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}}
decisions=[PlanAuditor(WorldState.from_mapping(world)).audit(c).as_dict() for c in plan['tool_calls']]
(a.output/'preflight_audit.json').write_text(json.dumps(decisions,ensure_ascii=False,indent=2)+'\n')
if not all(d['allowed'] for d in decisions):raise SystemExit('frozen plan fails current map preflight; no movement')
for name,value in [('world.json',world),('semantic.json',{'W1_door':{'x':7.,'y':6.,'theta':0.}}),('plans.json',{text:plan})]:
 (a.output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
(a.output/'provenance.json').write_text(json.dumps({'source_kind':'frozen_real_model_plan_actual_AMCL_SLAM_sim_execution',
 'instruction':text,'new_model_requests':0,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
 'pass_criteria':{'result':'COMPLETED','truth_goal_error_m_max':.30,'replan_count_max':2,'stop_verified':True},
 'limits':['One local task; no real camera, lidar, battery or vehicle.',
 'Original received model reply reused; not a new online model sampling.',
 'Known virtual waypoint TTL is a declared setting, not W6 field observation.']},ensure_ascii=False,indent=2)+'\n')
print(str(a.output))
