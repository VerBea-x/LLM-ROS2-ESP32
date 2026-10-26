#!/usr/bin/env python3
"""Compare legacy offline replay with actual new ROS dense-frame output."""
import hashlib,json,os,sys
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR','/tmp/course_matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from course_audit.semantic_registration import register
source=ROOT/'evidence/raw/week6_dense_frame_v2/lab_result.json';d=json.loads(source.read_text());old=[]
for i,u in enumerate(d['injections'][0]['pixels']):
 register(old,{'label':'cup','u':u,'image_width':640,'conf':.8,'evidence_id':f'legacy_replay_{i}'},(2,3,0),{'fx':320,'cx':320,'width':640},.5,'2026-10-26T00:00:00Z')
new=d['snapshots'][0]['items'];report={'source_kind':'legacy_offline_replay_compared_with_actual_synthetic_ROS_frame','source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
 'legacy_entries':old,'new_actual_entries':new,'comparison':{'legacy_count':len(old),'new_count':len(new)},'limits':['Legacy side recomputed offline, not a new ROS baseline run. Both sides use synthetic detections and virtual depth.']}
(ROOT/'evidence/reports/week6_dense_legacy_vs_frame.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
fig,axes=plt.subplots(1,2,figsize=(9,4),constrained_layout=True)
for ax,items,title in zip(axes,[old,new],['Legacy: one merged cup (offline replay)','New: two cups (actual synthetic ROS)']):
 for n,item in enumerate(new):ax.scatter(item['x'],item['y'],s=200,facecolors='none',edgecolors='gray',label='Declared synthetic objects' if n==0 else None)
 for n,item in enumerate(items):
  ax.scatter(item['x'],item['y'],c='#c62828' if len(items)==1 else '#1769aa',s=50)
  ax.annotate(item.get('target_name','merged cup'),(item['x'],item['y']),xytext=(8,5),textcoords='offset points',fontsize=9)
 ax.set_xlim(2.65,3.3);ax.set_ylim(2.5,3.5);ax.set_aspect('equal');ax.set_title(title,fontsize=11);ax.set_xlabel('map x (m)');ax.set_ylabel('map y (m)');ax.grid(alpha=.2)
fig.savefig(ROOT/'evidence/reports/figures/week6_dense_frame_fix.png',dpi=150);plt.close(fig)
print(report['comparison'])
