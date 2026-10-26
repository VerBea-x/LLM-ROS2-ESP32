#!/usr/bin/env python3
"""Deterministic COCO val selection, frozen before any detector output is viewed."""
import collections
import datetime as dt
import hashlib
import json
import time
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];out=ROOT/'data/coco_public20'
doc=json.loads((out/'instances_val2017.json').read_text());categories={c['id']:c['name'] for c in doc['categories']}
targets={'cup','bottle','chair'};anns=collections.defaultdict(list);excluded=set()
for a in doc['annotations']:
    if categories[a['category_id']] not in targets:continue
    if a.get('iscrowd'):excluded.add(a['image_id']);continue
    if a['bbox'][2]<=0 or a['bbox'][3]<=0:continue
    anns[a['image_id']].append(a)
images={x['id']:x for x in doc['images']};selected=[];used=set()
for label,n in [('cup',6),('bottle',6),('chair',4),('negative',4)]:
    candidates=[i for i in sorted(images) if i not in used and i not in excluded
                and ((not anns[i]) if label=='negative' else any(categories[a['category_id']]==label for a in anns[i]))]
    for i in candidates[:n]:selected.append((i,label));used.add(i)
if len(selected)!=20:raise RuntimeError('selection incomplete')
freeze=out/'selection_frozen.json'
protocol={'dataset':'COCO2017 validation','selection':'ascending image id within6cup+6bottle+4chair+4negative; no detector feedback',
          'class_scope':sorted(targets),'selected':[{'image_id':i,'selection_group':g} for i,g in selected],
          'annotations_sha256':hashlib.sha256((out/'instances_val2017.json').read_bytes()).hexdigest(),
          'frozen_at':dt.datetime.now(dt.timezone.utc).isoformat(),'thresholds':[.3,.5,.7],'nms_iou':.45,'match_iou':.5}
if freeze.exists():
    existing=json.loads(freeze.read_text())
    if existing['selected']!=protocol['selected']:raise ValueError('selection changed')
    protocol=existing
else:freeze.write_text(json.dumps(protocol,ensure_ascii=False,indent=2)+'\n')
(out/'images').mkdir(exist_ok=True);scenes=[]
for i,group in selected:
    im=images[i];path=out/'images'/im['file_name'];url='https://s3.amazonaws.com/images.cocodataset.org/val2017/'+im['file_name']
    if not path.exists():
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url,timeout=30) as response:raw=response.read()
                path.write_bytes(raw);break
            except Exception:
                if attempt==2:raise
                time.sleep(1)
    objects=[]
    for a in anns[i]:
        x,y,w,h=a['bbox'];objects.append({'label':categories[a['category_id']],'bbox':[x,y,x+w,y+h],'annotation_id':a['id']})
    scenes.append({'sample_id':f'coco_val2017_{i:012d}','image':'images/'+im['file_name'],'source_group':'public',
        'selection_group':group,'image_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'download_url':url,
        'truth_source':'official COCO instances_val2017.json','truth_frozen_at':protocol['frozen_at'],
        'width':im['width'],'height':im['height'],'license_id':im.get('license'),'objects':objects})
    print('saved',im['file_name'],group,len(objects),flush=True)
dataset={'dataset_protocol':'public_substitution_v1','substitution_note':'User authorized20 public images instead of teacher10+self10; no vehicle camera or own-scene claim.',
         'scenes':scenes,'licenses':doc['licenses'],'categories':doc['categories'],'selection_protocol':protocol}
(out/'dataset.json').write_text(json.dumps(dataset,ensure_ascii=False,indent=2)+'\n')
print('Frozen20 images and independent annotations before prediction',flush=True)
