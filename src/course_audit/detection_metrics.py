"""Course W5: class-aware, one-to-one bounding box IoU matching at frozen thresholds."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path


def box(value):
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError('bbox must be [xmin,ymin,xmax,ymax] in original image pixels')
    x1,y1,x2,y2 = map(float,value)
    if not all(math.isfinite(v) for v in (x1,y1,x2,y2)) or x2<=x1 or y2<=y1:
        raise ValueError('invalid or zero-area bbox')
    return x1,y1,x2,y2


def iou(a,b):
    ax,ay,bx,by=box(a); cx,cy,dx,dy=box(b)
    intersection=max(0,min(bx,dx)-max(ax,cx))*max(0,min(by,dy)-max(ay,cy))
    return intersection/((bx-ax)*(by-ay)+(dx-cx)*(dy-cy)-intersection)


def evaluate(dataset: dict, predictions: dict, root: Path, require_images=True):
    scenes=dataset['scenes']
    ids=[s['sample_id'] for s in scenes]
    if len(ids)!=len(set(ids)) or len(scenes)<20:
        raise ValueError('require >=20 distinct scenes')
    if dataset.get('dataset_protocol')=='public_substitution_v1':
        if not dataset.get('substitution_note') or any(s['source_group']!='public' for s in scenes):
            raise ValueError('public substitution requires an explicit note and all-public provenance')
    else:
        for group in ('public','custom'):
            if sum(s['source_group']==group for s in scenes)<10:
                raise ValueError('require >=10 public and >=10 custom scenes')
    pred=predictions['scenes']
    if set(pred)!=set(ids):raise ValueError('prediction scene IDs must exactly match dataset')
    thresholds=[0.3,0.5,0.7]
    records=[]
    for s in scenes:
        if not s.get('truth_source') or not s.get('truth_frozen_at'):
            raise ValueError('independent truth source and freeze time required')
        image=(root/s['image']).resolve()
        if require_images:
            if not image.is_file():raise ValueError(f'missing image: {image}')
            digest=hashlib.sha256(image.read_bytes()).hexdigest()
            if digest!=s['image_sha256']:raise ValueError(f'image hash mismatch: {s["sample_id"]}')
        truth=s['objects']
        for obj in truth:
            box(obj['bbox'])
            if not obj.get('label'):raise ValueError('truth class required')
        detections=pred[s['sample_id']]
        for obj in detections:
            box(obj['bbox'])
            score=float(obj['score'])
            if not math.isfinite(score) or not 0<=score<=1 or not obj.get('label'):
                raise ValueError('invalid detection score/class')
        for threshold in thresholds:
            used=set();matches=[];fp=0
            # Confidence ordered greedy matching is fixed before scoring.
            for d in sorted(detections,key=lambda x:-x['score']):
                if d['score']<threshold:continue
                candidates=[(iou(d['bbox'],t['bbox']),i) for i,t in enumerate(truth)
                            if i not in used and t['label']==d['label']]
                overlap,index=max(candidates,default=(0,None))
                if overlap>=0.5:
                    used.add(index);matches.append({'truth_index':index,'iou':overlap,'score':d['score']})
                else:fp+=1
            records.append({'sample_id':s['sample_id'],'threshold':threshold,
                            'tp':len(used),'fp':fp,'fn':len(truth)-len(used),'matches':matches})
    totals=[]
    for t in thresholds:
        r=[r for r in records if r['threshold']==t]
        tp,fp,fn=(sum(x[k] for x in r) for k in ('tp','fp','fn'))
        totals.append({'threshold':t,'tp':tp,'fp':fp,'fn':fn,
                       'precision':tp/(tp+fp) if tp+fp else None,
                       'recall':tp/(tp+fn) if tp+fn else None})
    return {'source_kind':'labeled_object_detection','matching':'same class, IoU>=0.5, one-to-one, confidence descending',
            'dataset_protocol':dataset.get('dataset_protocol','course_public10_custom10'),
            'substitution_note':dataset.get('substitution_note'),
            'thresholds':thresholds,'records':records,'totals':totals,
            'limitations':['No true-negative count for object detection; class errors count as FP and FN.',
                            'Independent review of annotations and detector output is still required.']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset',type=Path,required=True)
    p.add_argument('--predictions',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    report=evaluate(json.loads(a.dataset.read_text()),json.loads(a.predictions.read_text()),a.dataset.parent)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report['totals'],ensure_ascii=False))


if __name__=='__main__':main()
