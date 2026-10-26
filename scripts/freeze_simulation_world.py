#!/usr/bin/env python3
"""Register declared virtual landmarks against an actual simulator costmap snapshot."""
import hashlib
import argparse
import json
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--tag',default='')
args=parser.parse_args()
suffix='_'+args.tag if args.tag else ''
source=ROOT/'evidence/raw/week8_integration/map_snapshot.json'
grid=json.loads(source.read_text())['grids']['/global_costmap/costmap']
points=[('W1_door','门口',7.,6.),('W2_charge','充电站',6.,6.),('W3_podium','讲台/桌子',6.,5.5),
        ('W4_shelf','充电站旁边的书架/架子',6.,6.6),('W5_window','窗边',1.,5.),('W6_bench','长椅',4.,3.),
        ('W7_trash','垃圾桶',8.8,3.3),('W8_home','起点',8.08,6.238)]
now=time.time();items=[]
for label,name,x,y in points:
    mx=int((x-grid['origin'][0])/grid['resolution']);my=int((y-grid['origin'][1])/grid['resolution'])
    if not (0<=mx<grid['width'] and 0<=my<grid['height']):raise ValueError('out of bounds: '+label)
    cost=grid['data'][my*grid['width']+mx]
    if not 0<=cost<50:raise ValueError(f'{label} not free: {cost}')
    items.append({'label':label,'name':name,'x':x,'y':y,'theta':0.,'last_seen_s':now,
                  'tau_s':86400.,'state':'fresh','cost_at_registration':cost,
                  'source':'explicitly designated stationary virtual landmark; not detected physical object'})
items.append({'label':'cup_old','name':'过期测试杯子','x':1.,'y':1.,'theta':0.,'last_seen_s':now-600,
              'tau_s':30.,'state':'stale','source':'explicit stale-input injection, not scene observation'})
world={'schema_version':1,'source_kind':'declared_simulation_landmarks_with_verified_geometry',
       'fixture_only':True,'scene_clock_frozen_s':now,'frame_id':'map','current_label':'W8_home',
       'current_pose':{'x':8.08,'y':6.238,'theta':1.538},'semantic_map':items,
       'battery_pct':60,'battery_source':'simulated placeholder','map_bounds_m':[0,10,0,10],
       'tools_capabilities':['navigation','query semantic map','capture placeholder','say','stop'],
       'unavailable_capabilities':['manipulation','physical camera observations','real lidar'],
       'capture_contract':'capture_and_describe is a placeholder until camera data exists; never invent an observation.',
       'limitations':['Names denote deliberately assigned virtual landmarks, not visual detections.',
                      'Static-landmark TTL86400s is an experiment validity window, not W6 measured tau.',
                      'cup_old is explicitly stale input injection.']}
world['semantic_relations']=[{'subject':'W4_shelf','relation':'near','object':'W2_charge','distance_m':.6}]
world_path=ROOT/f'config/week7_world_frozen{suffix}.json'
if world_path.exists():raise FileExistsError('frozen world already exists; do not overwrite')
world_path.write_text(json.dumps(world,ensure_ascii=False,indent=2)+'\n')
auditor={'bounds_m':[0,10,0,10],'obstacles':[],'semantic_items':{p['label']:{'last_seen_s':p['last_seen_s']} for p in items},
         'tau_s':{p['label']:p['tau_s'] for p in items},'now_s':now,'battery_pct':60,
         'estimated_task_s':30,'remaining_budget_s':60,'max_linear_speed_mps':1.,'max_angular_speed_rps':1.5,
         'fixture_only':True,'occupancy_grid':{'width':grid['width'],'height':grid['height'],
         'resolution_m':grid['resolution'],'origin_x_m':grid['origin'][0],'origin_y_m':grid['origin'][1],
         'origin_yaw_rad':grid['origin_yaw'],'data':grid['data'],'occupied_threshold':50},
         'provenance':{'map_source':str(source),'world_source':str(world_path),
                       'map_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                       'semantics':'declared virtual landmarks','resource_source':'explicit simulation settings'}}
(ROOT/f'config/week8_auditor_world_frozen{suffix}.json').write_text(json.dumps(auditor,ensure_ascii=False,indent=2)+'\n')
(ROOT/f'evidence/raw/week6_sim_waypoint_registration{suffix}.json').write_text(json.dumps({
    'source_kind':world['source_kind'],'items':items,'all_eight_landmarks_free':True,
    'limitations':world['limitations'],'course_week6_passed':False},ensure_ascii=False,indent=2)+'\n')
print('Frozen8 virtual landmarks and1 stale test item; geometric check passed; W6 visual registration not claimed.')
