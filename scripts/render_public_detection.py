#!/usr/bin/env python3
"""Render raw image/annotation/prediction evidence and threshold curves."""
import json
import argparse
import os
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
os.environ.setdefault('MPLCONFIGDIR','/tmp/course_matplotlib_config')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--dataset-dir',type=Path,default=root/'data/coco_indoor20_v2')
parser.add_argument('--run-tag',default='week5_indoor20_v2');args=parser.parse_args();data=args.dataset_dir
dataset=json.loads((data/'dataset.json').read_text());pred=json.loads((root/f'evidence/raw/{args.run_tag}_predictions.json').read_text())
metrics=json.loads((root/f'evidence/reports/{args.run_tag}_metrics.json').read_text())
out=root/'outputs'/args.run_tag;out.mkdir(parents=True,exist_ok=True)
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',14)
sheet=Image.new('RGB',(1400,1000),'#f0f3f7')
for i,s in enumerate(dataset['scenes']):
    original=Image.open(data/s['image']).convert('RGB');im=original.copy();d=ImageDraw.Draw(im)
    for obj in s['objects']:d.rectangle(obj['bbox'],outline='#00c878',width=3)
    for obj in pred['scenes'][s['sample_id']]:
        d.rectangle(obj['bbox'],outline='#ef4444',width=2)
        d.text((obj['bbox'][0],max(0,obj['bbox'][1]-14)),f"{obj['label']} {obj['score']:.2f}",font=font,fill='#ef4444')
    im.save(out/(s['sample_id']+'_annotated.jpg'))
    im.thumbnail((340,210));x=(i%4)*350;y=(i//4)*200
    # Contact sheet uses consistent aspect-ratio thumbnails; originals remain separate.
    im.thumbnail((340,170));sheet.paste(im,(x,y+25))
    ImageDraw.Draw(sheet).text((x+5,y+5),s['sample_id'][-12:]+f" GT:{len(s['objects'])}",font=font,fill='#111111')
sheet.save(out/'contact_sheet.jpg')
font_path='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc';font_manager.fontManager.addfont(font_path)
plt.rcParams['font.family']=font_manager.FontProperties(fname=font_path).get_name()
fig,ax=plt.subplots(figsize=(7,4));rows=metrics['totals'];xs=[r['threshold'] for r in rows]
ax.plot(xs,[r['precision'] for r in rows],'o-',label='查准率 Precision')
ax.plot(xs,[r['recall'] for r in rows],'s-',label='查全率 Recall')
ax.set(xlabel='置信度阈值',ylabel='比例',ylim=(0,1.05),title='COCO验证集20张公开替代图像：三档同图回放')
ax.legend();fig.tight_layout();fig.savefig(out/'precision_recall_vs_threshold.png',dpi=160)
print('Saved annotated20 images, contact sheet, and threshold curves:',out)
