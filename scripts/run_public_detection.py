#!/usr/bin/env python3
"""YOLOv5n ONNX inference on frozen public images; class-aware NMS and original-pixel boxes."""
import hashlib
import argparse
import json
import time
from pathlib import Path
import cv2
import numpy as np
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from course_audit.detection_metrics import evaluate

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--dataset-dir',type=Path,default=ROOT/'data/coco_indoor20_v2')
parser.add_argument('--run-tag',default='week5_indoor20_v2')
args=parser.parse_args()
data_dir=args.dataset_dir;dataset=json.loads((data_dir/'dataset.json').read_text())
model=ROOT/'models/yolov5n.onnx';net=cv2.dnn.readNetFromONNX(str(model));cv2.setNumThreads(2)
names=[c['name'] for c in sorted(dataset['categories'],key=lambda c:c['id'])]
targets={'cup','bottle','chair'};predictions={};timings=[]
output=ROOT/f'evidence/raw/{args.run_tag}_predictions.json'
if output.exists():raise FileExistsError('Prediction run already exists; preserve it')
for s in dataset['scenes']:
    image=cv2.imread(str(data_dir/s['image']));height,width=image.shape[:2]
    scale=min(640/width,640/height);w=round(width*scale);h=round(height*scale)
    left=(640-w)//2;top=(640-h)//2
    resized=cv2.resize(image,(w,h));canvas=np.full((640,640,3),114,np.uint8)
    canvas[top:top+h,left:left+w]=resized
    blob=cv2.dnn.blobFromImage(canvas,1/255.,(640,640),swapRB=True,crop=False)
    net.setInput(blob);start=time.perf_counter();raw=net.forward()[0];timings.append(time.perf_counter()-start)
    candidates=[]
    for row in raw:
        cid=int(row[5:].argmax());score=float(row[4]*row[5+cid])
        if score<.3 or names[cid] not in targets:continue
        cx,cy,bw,bh=map(float,row[:4]);x1=max(0,(cx-bw/2-left)/scale);y1=max(0,(cy-bh/2-top)/scale)
        x2=min(width,(cx+bw/2-left)/scale);y2=min(height,(cy+bh/2-top)/scale)
        if x2>x1 and y2>y1:candidates.append({'label':names[cid],'bbox':[x1,y1,x2,y2],'score':score})
    kept=[]
    for label in sorted(targets):
        group=[c for c in candidates if c['label']==label]
        if not group:continue
        boxes=[[d['bbox'][0],d['bbox'][1],d['bbox'][2]-d['bbox'][0],d['bbox'][3]-d['bbox'][1]] for d in group]
        indices=cv2.dnn.NMSBoxes(boxes,[d['score'] for d in group],.3,.45)
        kept.extend(group[int(i)] for i in np.asarray(indices).reshape(-1))
    predictions[s['sample_id']]=sorted(kept,key=lambda x:-x['score'])[:300]
    print(s['sample_id'],'detections',len(kept),flush=True)
meta={'source_kind':'actual_onnx_cpu_inference','scenes':predictions,'model_source':'https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5n.onnx',
      'model_sha256':hashlib.sha256(model.read_bytes()).hexdigest(),'opencv_version':cv2.__version__,
      'input_resolution':[640,640],'nms_iou':.45,'minimum_confidence':.3,'inference_seconds':timings,
      'limitations':['Official model has640 static input; not course320 hardware deployment.','CPU timings on VM are not vehicle camera FPS.','Only cup,bottle,chair evaluated.']}
output.write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
report=evaluate(dataset,meta,data_dir)
report['model_metadata']={k:v for k,v in meta.items() if k!='scenes'}
(ROOT/f'evidence/reports/{args.run_tag}_metrics.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report['totals'],ensure_ascii=False,indent=2),flush=True)
