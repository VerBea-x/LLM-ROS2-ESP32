#!/usr/bin/env python3
"""Export the measured map and comparison without fitting or replacing SLAM."""
import json,os,shutil,sys
from pathlib import Path
import numpy as np
os.environ.setdefault('MPLCONFIGDIR','/tmp/course_matplotlib_config')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import yaml

root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'src'))
from course_audit.registered_map_metrics import compare
out=root/'outputs/slam_improvement';out.mkdir(parents=True,exist_ok=True)
before=json.loads((root/'evidence/reports/week3_720ray_coverage_metrics.json').read_text())
after=json.loads((root/'evidence/reports/week3_safe_local_tracking_metrics.json').read_text())
before_path=Path(before['estimate_snapshot']);after_path=Path(after['estimate_snapshot'])
truth,initial=root/'evidence/raw/week1_live_sim.json',before_path.parent/'initial_snapshot.json'
_,gt,b=compare(truth,before_path,initial)
_,_,a=compare(truth,after_path,Path(after['initial_calibration_snapshot']))
font='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc';font_manager.fontManager.addfont(font)
plt.rcParams['font.family']=font_manager.FontProperties(fname=font).get_name()
fig,axes=plt.subplots(1,3,figsize=(13,4.6))
for ax,data,title in zip(axes,[gt,b,a],['独立真值地图','720束原配置：平均边界距离44.6cm','局部匹配+安全路线：18.4cm']):
    rgb=np.ones((*data.shape,3));rgb[data<0]=[.72,.78,.83];rgb[data>=50]=[.08,.1,.13]
    ax.imshow(rgb,origin='lower',extent=[0,10,0,10]);ax.set_title(title,fontsize=11)
    ax.set_xlabel('x（m）');ax.set_ylabel('y（m）')
fig.suptitle('实际SLAM结果，固定初始坐标系；未作结果配准。灰蓝为未知，改进轮另修正了采图路线。',fontsize=11)
fig.tight_layout();fig.savefig(out/'map_comparison.png',dpi=160);plt.close(fig)
run=after_path.parent;meta=yaml.safe_load((run/'map_slam.yaml').read_text())
source=run/meta['image'];shutil.copyfile(source,out/'map_slam.pgm')
meta.update(image='map_slam.pgm',free_thresh=.196)
(out/'map_slam.yaml').write_text(yaml.safe_dump(meta,sort_keys=False))
shutil.copyfile(run/'mapper.yaml',root/'config/mapper_sim_improved.yaml')
(out/'provenance.json').write_text(json.dumps({'source_run':str(run),'source_metrics':after,
    'image_change':'none; exact PGM copy','yaml_change':'relative image name; free_thresh0.196 preserves raw205-gray unknown pixels on reload',
    'not_navigation_certified':True},ensure_ascii=False,indent=2)+'\n')
print('Exported measured SLAM map and comparison:',out)
