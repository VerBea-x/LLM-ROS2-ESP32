#!/usr/bin/env python3
"""Static scientific figures from saved raw measurements; no simulated new results."""
import json
import os
from pathlib import Path
import numpy as np
os.environ.setdefault('MPLCONFIGDIR','/tmp/course_matplotlib_config')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'evidence/reports/figures';OUT.mkdir(exist_ok=True)
font_path='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
font_manager.fontManager.addfont(font_path)
plt.rcParams['font.family']=font_manager.FontProperties(fname=font_path).get_name()
plt.rcParams['axes.unicode_minus']=False

cells=json.loads((ROOT/'evidence/raw/week3_localization_matrix.json').read_text())['cells']
fig,ax=plt.subplots(figsize=(9,4.5));x=np.arange(5)
for i,(condition,label,color) in enumerate([('A','A：正确初值','#2563eb'),('B','B：偏置1m/20°','#dc2626')]):
    values=[c['final_sample']['position_error_m']*100 for c in cells if c['condition']==condition]
    ax.bar(x+(i-.5)*.34,values,.34,label=label,color=color)
ax.axhline(15,color='#444444',linestyle='--',label='预注册不可信阈值15cm')
ax.set_xticks(x,['P1','P2','P3','P4','P5']);ax.set_ylabel('真值位置误差（cm）')
ax.set_title('局部五点定位对照：每格一个新鲜估计，非实车数据');ax.legend(fontsize=9)
fig.tight_layout();fig.savefig(OUT/'week3_localization.png',dpi=160);plt.close(fig)

paths=[('真值地图',ROOT/'evidence/raw/week1_live_sim.json'),
       ('24束 / slip=0.05',ROOT/'evidence/raw/week3_slam/live_snapshot.json'),
       ('360束 / slip=0.05',ROOT/'evidence/raw/week3_slam/20261026T015523Z/final_snapshot.json'),
       ('360束 / slip=0',ROOT/'evidence/raw/week3_slam/20261026T020326Z/final_snapshot.json')]
fig,axes=plt.subplots(1,4,figsize=(15,4))
for ax,(label,path) in zip(axes,paths):
    g=json.loads(path.read_text())['grids']['/map'];data=np.array(g['data']).reshape(g['height'],g['width'])
    rgb=np.ones((*data.shape,3));rgb[data<0]=[.7,.76,.82];rgb[data>=50]=[.08,.1,.13]
    ox,oy=g['origin'];res=g['resolution']
    ax.imshow(rgb,origin='lower',extent=[ox,ox+g['width']*res,oy,oy+g['height']*res])
    ax.set_title(label);ax.set_xlabel('地图x（m）');ax.set_ylabel('地图y（m）')
fig.suptitle('实际SLAM输出：各自地图范围；未优化配准，灰蓝为未知');fig.tight_layout()
fig.savefig(OUT/'week3_map_conditions.png',dpi=160);plt.close(fig)

summary=json.loads((ROOT/'evidence/reports/week7_randomness_summary_20261026.json').read_text())
g=summary['groups'];fig,ax=plt.subplots(figsize=(9,4.5));x=np.arange(4)
ax.bar(x-.18,[r['consistency']*100 for r in g],.36,label='最常见工具序列一致率',color='#2563eb')
ax.bar(x+.18,[r['expected_sequence_complete_rate']*100 for r in g],.36,label='完整预期工具序列比例',color='#f59e0b')
ax.set_xticks(x,[('公共' if r['instruction_id']=='common' else '自选')+f" T={r['temperature']}" for r in g])
ax.set_ylim(0,110);ax.set_ylabel('比例（%）');ax.legend(fontsize=9)
ax.set_title('40次真实模型采样：重复稳定不代表计划完整')
fig.tight_layout();fig.savefig(OUT/'week7_consistency_vs_completeness.png',dpi=160);plt.close(fig)
print('Saved3 result figures:',OUT)
