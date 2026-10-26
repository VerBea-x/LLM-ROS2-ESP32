#!/usr/bin/env python3
"""Create explicit synthetic mobility observations and derive rules before ROS lab."""
import json,random,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from course_audit.semantic_registration import project,error_components
p=json.loads((ROOT/'config/week6_controlled_lab_protocol.json').read_text());m=p['mobility'];rng=random.Random(m['seed']);events=[];rules={}
for cls,(lo,hi) in m['interval_ranges_s'].items():
    t=0;index=0;training=[];last=0
    while True:
        t+=rng.randint(lo,hi)
        if t>m['logical_duration_s']:break
        index+=1;e={'event_id':f'SIM_MOBILITY_{cls}_{index:03d}','class':cls,'logical_time_s':t,
          'position_m':[float(index%3),float((index+1)%2)],'source_kind':'synthetic_motion_schedule'}
        events.append(e)
        if t<=m['training_end_s']:training.append(t-last)
        last=t
    rules[cls]={'tau_s':min(training)/2,'observed_training_min_interval_s':min(training),
                'observation_evidence_id':f'SIM_MOBILITY_TRAIN_{cls}','training_event_count':len(training)}
by_label={'cup':rules['handheld'],'bottle':rules['handheld'],'backpack':rules['handheld'],'person':rules['person'],'chair':rules['furniture']}
record={'protocol':p,'source_kind':'controlled_simulation_logical_time','events':events,
        'derived_class_rules':rules,'limitations':['Declared stochastic synthetic schedule; not real object movement measurements.']}
(ROOT/'evidence/raw/week6_controlled_mobility.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
(ROOT/'config/week6_controlled_tau_rules.json').write_text(json.dumps(by_label,ensure_ascii=False,indent=2)+'\n')
checks=[]
for name,u,distance,du in [('near',320,.8,0),('far',320,2.5,0),('left',220,1,0),('pixel_bias',320,1,5)]:
    b=math.atan2(320-u,320);truth=[2+distance*math.cos(b),3+distance*math.sin(b)]
    estimate=project(u+du,320,320,640,640,(2,3,0))
    checks.append({'case':name,'source_kind':'known_virtual_geometry','station':[2,3],
      'truth':truth,'estimate':[estimate['x'],estimate['y']],**error_components((estimate['x'],estimate['y']),truth,(2,3))})
(ROOT/'evidence/reports/week6_controlled_error_components.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
print('Derived controlled-simulation tau:',{k:v['tau_s'] for k,v in rules.items()})
