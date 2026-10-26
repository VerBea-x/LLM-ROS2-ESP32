#!/usr/bin/env python3
"""Offline synthetic stress: rotated stations, time reversal and class ambiguity."""
import argparse,copy,hashlib,json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from course_audit.semantic_registration import project,register,export_map,error_components
from course_audit.semantic_world import semantic_world_fields

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():p.error('new evidence path required')
 protocol=ROOT/'config/week6_stress_protocol_v1.json';config=json.loads(protocol.read_text());rows=[];biases=[];checks={}
 for index,(x,y,deg) in enumerate(config['stations']):
  theta=math.radians(deg)
  for u in config['pixel_columns']:
   slope=(320-u)/320.;bx=1/math.sqrt(1+slope*slope);by=slope*bx
   truth=[x+math.cos(theta)*bx-math.sin(theta)*by,y+math.sin(theta)*bx+math.cos(theta)*by]
   estimate=project(u,320,320,640,640,(x,y,theta));error=math.hypot(estimate['x']-truth[0],estimate['y']-truth[1])
   rows.append({'id':f'S{index+1}_u{u}','station':[x,y,deg],'pixel_u':u,'truth':truth,'estimate':estimate,'error_m':error,'passed':error<=config['exact_geometry_error_max_m']})
  for bias in config['orientation_bias_degrees']:
   truth=[x+math.cos(theta),y+math.sin(theta)];estimate=project(320,320,320,640,640,(x,y,theta+math.radians(bias)))
   biases.append({'station_id':index+1,'yaw_bias_deg':bias,**error_components([estimate['x'],estimate['y']],truth,(x,y))})
 checks['all12_known_pose_geometry_cases']=len(rows)==12 and all(r['passed'] for r in rows)
 k={'fx':320,'cx':320,'width':640};det={'label':'cup','u':320,'image_width':640,'conf':.8,'evidence_id':'SYNTHETIC_initial'}
 items=register([],det,(0,0,0),k,.5,'2026-10-26T00:00:05Z');frozen=copy.deepcopy(items);rejected=False
 try:register(items,{**det,'evidence_id':'SYNTHETIC_older'},(.4,0,0),k,.5,'2026-10-26T00:00:04Z')
 except ValueError:rejected=True
 checks['out_of_order_rejected_without_mutation']=rejected and items==frozen
 sameclass=[];rules={'cup':{'tau_s':4,'observation_evidence_id':'SYNTHETIC_rule'}}
 for spacing in config['same_class_distances_m']:
  items=register([],det,(0,0,0),k,.5,'2026-10-26T00:00:00Z')
  register(items,{**det,'evidence_id':'SYNTHETIC_other_object'},(spacing,0,0),k,.5,'2026-10-26T00:00:01Z')
  doc=export_map(items,rules,'2026-10-26T00:00:02Z');error=None
  try:semantic_world_fields(doc)
  except ValueError as exc:error=str(exc)
  sameclass.append({'physical_object_count_in_fixture':2,'spacing_m':spacing,'registered_item_count':len(items),'ambiguous_map_rejected':error is not None,'conversion_error':error,'map':doc})
 checks['separate_same_class_items_not_silently_overwritten']=sameclass[1]['ambiguous_map_rejected'] and sameclass[1]['registered_item_count']==2
 # The closer pair is a documented limitation, not a successful identity test.
 limitations={'near_same_class_objects_still_merge':sameclass[0]['registered_item_count']==1,'note':'Fail-closed conversion only detects separate duplicate-label items. It cannot recover objects already merged by the1m teaching approximation.'}
 lab=json.loads((ROOT/'evidence/raw/week6_ros_lab_v3/lab_result.json').read_text());bridge=[]
 for name in ['fresh_snapshot','stale_snapshot']:
  fields=semantic_world_fields(lab[name]);bridge.append({'snapshot':name,'target_count':len(fields['semantic_items']),
    'ages_s':{label:fields['now_s']-v['last_seen_s'] for label,v in fields['semantic_items'].items()},'tau_s':fields['tau_s']})
 checks['existing_ROS_observations_convert_without_loss']=all(b['target_count']==3 for b in bridge)
 result={'source_kind':config['source_kind'],'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),
  'geometry_cases':rows,'yaw_bias_cases':biases,'same_class_cases':sameclass,'existing_ROS_record_conversion':bridge,
  'checks':checks,'all_checks_passed':all(checks.values()),'known_limitations':limitations,'limitations':config['limits']}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'checks':checks,'known_limitations':limitations},ensure_ascii=False))
 return 0 if result['all_checks_passed'] else 1
if __name__=='__main__':raise SystemExit(main())
