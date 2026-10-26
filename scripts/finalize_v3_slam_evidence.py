#!/usr/bin/env python3
"""Verify actual map/costmap evidence, video, and export read-only viewing entries."""
import copy,hashlib,json,os,subprocess,sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from course_audit.plan_auditor import PlanAuditor,WorldState
base=ROOT/'evidence/raw/week8_v3_slam/20261026_frozen_plan_v2';agent=base/'agent'
world=json.loads((agent/'world.json').read_text());rows=[];grids={}
for kind,filename in [('raw_SLAM_map','map_snapshot.json'),('inflated_Nav2_costmap','costmap_snapshot.json')]:
 grid=json.loads((base/'initialization'/filename).read_text());grids[kind]=grid
 for label,x,y in [('door',7.,6.),('middle',6.,6.),('blocked_return',8.,5.5)]:
  d=copy.deepcopy(world);d['occupancy_grid']=grid;d['semantic_items']={label:{'x_m':x,'y_m':y,'last_seen_s':world['now_s']}};d['tau_s']={label:86400.}
  d['provenance']['map_source']=str((base/'initialization'/filename).relative_to(ROOT))
  decision=PlanAuditor(WorldState.from_mapping(d)).audit({'name':'navigate_to','arguments':{'x':x,'y':y,'label':label}}).as_dict()
  rows.append({'map_kind':kind,'label':label,'position':[x,y],'decision':decision,
   'expected_allow':not(kind=='inflated_Nav2_costmap' and label=='blocked_return')})
report={'source_kind':'offline_same_target_check_on_actual_ROS_map_and_costmap_snapshots','rows':rows,
 'all_checks_passed':all(r['decision']['allowed']==r['expected_allow'] for r in rows),
 'limits':['Snapshot checks, no new navigation calls. Raw SLAM free cell does not imply robot-footprint reachability.',
 'Future execution must refresh current costmap and preserve the service-side live costmap check.']}
(ROOT/'evidence/reports/week34_costmap_boundary_check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
fig,axes=plt.subplots(1,2,figsize=(10,5),constrained_layout=True)
for ax,(kind,g) in zip(axes,grids.items()):
 arr=np.array(g['data']).reshape(g['height'],g['width']);res=g['resolution_m'];x=g['origin_x_m'];y=g['origin_y_m']
 im=ax.imshow(arr,origin='lower',extent=[x,x+g['width']*res,y,y+g['height']*res],vmin=-1,vmax=100,cmap='gray_r')
 for label,px,py in [('door',7,6),('middle',6,6),('return',8,5.5)]:
  ax.scatter([px],[py],c='red' if label=='return' else '#0077cc',marker='x',s=70);ax.text(px+.12,py+.12,label,fontsize=9,color='red' if label=='return' else '#0077cc')
 ax.set_title(kind.replace('_',' '));ax.set_xlabel('map x (m)');ax.set_ylabel('map y (m)');ax.set_xlim(0,10);ax.set_ylim(0,10)
fig.suptitle('Same target (8,5.5): raw map=0; Nav2 inflated costmap=99')
fig.savefig(ROOT/'evidence/reports/figures/week34_map_vs_costmap.png',dpi=150);plt.close(fig)
video=agent/'v3_slam_live_sim.mp4'
probe=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=codec_name,width,height,pix_fmt,nb_frames,duration','-of','json',str(video)],capture_output=True,text=True,check=True)
decode=subprocess.run(['ffmpeg','-v','error','-i',str(video),'-f','null','-'],capture_output=True,text=True)
media={'ffprobe':json.loads(probe.stdout),'full_decode_exit_code':decode.returncode,'decode_stderr':decode.stderr,
 'sha256':hashlib.sha256(video.read_bytes()).hexdigest()}
(agent/'media_validation.json').write_text(json.dumps(media,ensure_ascii=False,indent=2)+'\n')
if decode.returncode:raise SystemExit('video decoding failed')
canonical=ROOT/'outputs/week8/v3_slam_live_sim.mp4'
if not canonical.exists():os.link(video,canonical)
assert hashlib.sha256(canonical.read_bytes()).hexdigest()==media['sha256']
subprocess.run(['ffmpeg','-y','-v','error','-sseof','-1','-i',str(video),'-frames:v','1',str(ROOT/'outputs/week8/v3_slam_final_frame.png')],check=True)
print(json.dumps({'costmap_checks':report['all_checks_passed'],'video_full_decode':decode.returncode==0,'video_sha256':media['sha256']}))
