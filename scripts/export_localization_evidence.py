#!/usr/bin/env python3
"""Export original10-cell localization table and evidence-linked points, no new samples."""
import csv,hashlib,json,math,os,statistics
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR','/tmp/course_matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
import yaml
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'evidence/raw/week3_localization_selected.csv';rows=list(csv.DictReader(source.open()))
matrix=json.loads((ROOT/'evidence/raw/week3_localization_matrix.json').read_text());conditions={(c['point_id'],c['condition']):c for c in matrix['cells']}
records=[]
for row in rows:
 r={**row};r['evidence_id']=f"W3_{r['point_id']}_{r['condition']}"
 for key in ['est_x','est_y','est_yaw','truth_x','truth_y','truth_yaw','cov_x','cov_y','position_error_m']:r[key]=float(r[key])
 # For any valid covariance matrix with these diagonals: max(diagonal)<=lambda_max<=trace.
 r['one_sigma_major_axis_lower_m']=math.sqrt(max(r['cov_x'],r['cov_y']))
 r['one_sigma_major_axis_upper_m']=math.sqrt(r['cov_x']+r['cov_y'])
 r['yaw_error_deg']=math.degrees(math.atan2(math.sin(r['est_yaw']-r['truth_yaw']),math.cos(r['est_yaw']-r['truth_yaw'])))
 r['B_outcome']=conditions[(r['point_id'],r['condition'])]['status'] if r['condition']=='B' else 'not_applicable'
 r['untrusted_under_original_15cm_rule']=r['position_error_m']>.15
 records.append(r)
summary={c:{'n':len(rs:=[r for r in records if r['condition']==c]),'mean_error_m':statistics.mean(r['position_error_m'] for r in rs),'max_error_m':max(r['position_error_m'] for r in rs)} for c in ['A','B']}
report={'source_kind':'derived_from_original24ray_known_map_AMCL_samples','source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
 'rows':records,'summary':summary,'untrusted_point_ids':[r['evidence_id'] for r in records if r['untrusted_under_original_15cm_rule']],
 'limitations':['Only5 local truth positions; no spatial risk-radius or full-field interpolation inferred.',
 'Original24-ray known-map experiment; not new720-ray SLAM-map evidence.',
 'cov_xy not recorded; report bounds of1-sigma major standard deviation only, not exact ellipse or rviz visual grades.',
 'B nonconvergence does not itself distinguish divergence from a confident wrong lock.']}
(ROOT/'evidence/reports/week3_evidence_linked_points.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
mapfile=ROOT/'evidence/raw/week3_truth_map/map_gt.yaml';meta=yaml.safe_load(mapfile.read_text());image=Image.open(mapfile.parent/meta['image']);w,h=image.size;ox,oy,_=meta['origin'];res=meta['resolution']
fig,axes=plt.subplots(1,2,figsize=(11,5),constrained_layout=True)
for ax in axes:
 ax.imshow(image,cmap='gray',origin='upper',extent=[ox,ox+w*res,oy,oy+h*res],vmin=0,vmax=255)
 for r in records:
  c='#1769aa' if r['condition']=='A' else '#c62828'
  ax.plot([r['truth_x'],r['est_x']],[r['truth_y'],r['est_y']],color=c,alpha=.8)
  ax.scatter([r['est_x']],[r['est_y']],c=c,s=25,marker='x' if r['condition']=='B' else 'o')
  if r['condition']=='B':ax.text(r['truth_x']+.04,r['truth_y']+.08,r['point_id'],fontsize=8,color='black')
 ax.set_xlabel('map x (m)');ax.set_ylabel('map y (m)');ax.set_aspect('equal')
axes[0].set_xlim(0,10);axes[0].set_ylim(0,10);axes[0].set_title('Measured local points; unmeasured areas unverified')
axes[1].set_xlim(min(r['truth_x'] for r in records)-.4,max(r['est_x'] for r in records)+.4);axes[1].set_ylim(min(r['truth_y'] for r in records)-.4,max(r['est_y'] for r in records)+.4);axes[1].set_title('Blue=A; red=B; lines link truth to estimate')
fig.suptitle('Original W3 evidence: five B failures >15cm; no inferred risk zones')
fig.savefig(ROOT/'evidence/reports/figures/week3_evidence_linked_points.png',dpi=160);plt.close(fig)
lines=['# 第3周定位统计与不可信点证据','',
'本页复算原24束、已知地图条件下的10格AMCL采样，不是新增定位实验，也不替代720束SLAM图验证。',
'', '[原始CSV](../raw/week3_localization_selected.csv) · [证据JSON](week3_evidence_linked_points.json)',
'', '![实测点与误差连线](figures/week3_evidence_linked_points.png)',
'', '| 证据号 | 条件 | 位置误差cm | 偏角° | 主轴1σ标准差界cm | B结果 |', '|---|---|---:|---:|---|---|']
for r in records:lines.append(f"| {r['evidence_id']} | {r['condition']} | {r['position_error_m']*100:.2f} | {r['yaw_error_deg']:.2f} | {r['one_sigma_major_axis_lower_m']*100:.1f}–{r['one_sigma_major_axis_upper_m']*100:.1f} | {r['B_outcome']} |")
for c,v in summary.items():lines+=['',f"条件{c}：5格平均误差{v['mean_error_m']*100:.2f}cm，最大{v['max_error_m']*100:.2f}cm。"]
lines += ['', '按原预注册15cm不可信阈值，5个B条件均不可信；A均未超过阈值。图只标实际测量点及估计连线，不画无数据支持的连续风险区或半径。B在30秒内未收敛，不足以单独判定“发散”或“高置信锁定”。',
'', '只保存了cov_x/cov_y，没有cov_xy；因此只能给出主轴1σ标准差的上下界，不能还原精确协方差椭圆，也不能补写课程要求的rviz目视小/中/大等级。标准差不是定位真值误差，数值小不保证准确。',
'', '原试验只覆盖局部、使用24束及已知地图，不能直接作为当前720束SLAM图的空间拒绝区。若第8周需要自动拒绝不可信区域，须先补当前配置下的点位实验及明确的区域/条件策略，不能任意给5个点扩成整片禁区。教师/同学地图互评和实车签字仍待外部材料，未伪造。']
(ROOT/'evidence/reports/第3周_定位不可信点与统计.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(summary,ensure_ascii=False))
