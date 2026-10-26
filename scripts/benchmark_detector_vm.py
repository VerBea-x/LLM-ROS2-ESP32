#!/usr/bin/env python3
"""30-second offline throughput only; no camera or vehicle FPS claim."""
import json
import statistics
import time
from pathlib import Path
import cv2

root=Path(__file__).resolve().parents[1];data=root/'data/coco_indoor20_v2'
dataset=json.loads((data/'dataset.json').read_text());files=[data/s['image'] for s in dataset['scenes']]
net=cv2.dnn.readNetFromONNX(str(root/'models/yolov5n.onnx'));cv2.setNumThreads(2)
times=[];start=time.monotonic();n=0
while time.monotonic()-start<30:
    begin=time.perf_counter();im=cv2.imread(str(files[n%len(files)]))
    net.setInput(cv2.dnn.blobFromImage(im,1/255.,(640,640),swapRB=True));net.forward()
    times.append(time.perf_counter()-begin);n+=1
elapsed=time.monotonic()-start
report={'source_kind':'vm_offline_30s_throughput','frames':n,'duration_s':elapsed,'fps':n/elapsed,
        'mean_read_preprocess_inference_s':statistics.mean(times),'input_resolution':[640,640],
        'temperature':'not measured; VM cannot establish robot thermal state','performance_mode':'VM CPU2 OpenCV threads',
        'limitations':['Timing-only replay uses direct resize, not the letterbox evaluation path; it never changes saved predictions.',
                       'Repeated images are timing frames, not independent accuracy samples.','Not a camera stream or physical Pi5 FPS.']}
(root/'evidence/reports/week5_vm_throughput.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
