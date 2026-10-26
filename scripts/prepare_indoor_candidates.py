#!/usr/bin/env python3
"""Scene-first candidate pool, using annotations only; no detector feedback."""
import collections,json,time,urllib.request
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

root=Path(__file__).resolve().parents[1];source=root/'data/annotations/instances_val2017.json'
doc=json.loads(source.read_text());cats={c['id']:c['name'] for c in doc['categories']}
anns=collections.defaultdict(list)
for a in doc['annotations']:anns[a['image_id']].append(a)
context={'dining table','couch','bed','refrigerator','oven','sink','tv','microwave','laptop'}
excluded={'bear','bird','horse','zebra','giraffe','cow','elephant','sheep','car','bus','train','truck','airplane','boat','motorcycle','bicycle',
          'sports ball','baseball bat','surfboard','skis','snowboard','skateboard','tennis racket'}
targets={'cup','bottle','chair'};images={i['id']:i for i in doc['images']};used=set();selection=[]
for label,n in [('cup',10),('bottle',10),('chair',8),('negative',8)]:
    eligible=[]
    for i in sorted(images):
        names={cats[a['category_id']] for a in anns[i]}
        if i in used or names&excluded or not names&context or len(names)<3:continue
        if label=='negative':
            if names&targets or len(names&context)<2:continue
        elif label not in names:continue
        if any(a.get('iscrowd') for a in anns[i] if cats[a['category_id']] in targets):continue
        eligible.append(i)
    for i in eligible[:n]:
        used.add(i);selection.append({'image_id':i,'group':label,'context':sorted({cats[a['category_id']] for a in anns[i]}&context)})
out=root/'data/coco_indoor20_v2';(out/'candidates').mkdir(parents=True,exist_ok=True)
(out/'candidate_protocol.json').write_text(json.dumps({'reason':'User rejected generic animal/outdoor negative examples; require complete indoor scenes.',
 'filter':'indoor context labels, >=3 categories, no outdoor/animal/sport cues; negatives >=2 indoor context types; no prediction-based selection',
 'candidates':selection},ensure_ascii=False,indent=2)+'\n')
for s in selection:
    im=images[s['image_id']];p=out/'candidates'/im['file_name']
    old=root/'data/coco_indoor20_v2/images'/im['file_name']
    if not p.exists() and old.exists():p.write_bytes(old.read_bytes())
    if not p.exists():
        url='https://s3.amazonaws.com/images.cocodataset.org/val2017/'+im['file_name']
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url,timeout=30) as f:p.write_bytes(f.read())
                break
            except Exception:
                if attempt==2:raise
                time.sleep(1)
    print(s['image_id'],s['group'],s['context'],flush=True)
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',14)
for page in range((len(selection)+19)//20):
    sheet=Image.new('RGB',(1440,1050),'#f0f3f7');d=ImageDraw.Draw(sheet)
    for j,s in enumerate(selection[page*20:(page+1)*20]):
        p=out/'candidates'/images[s['image_id']]['file_name'];im=Image.open(p).convert('RGB');im.thumbnail((350,175))
        x=(j%4)*360;y=(j//4)*210;sheet.paste(im,(x,y+28));d.text((x+5,y+5),str(s['image_id'])+' '+s['group'],font=font,fill='black')
    sheet.save(out/f'candidate_sheet_{page+1}.jpg')
print('Candidate pool ready for visual scene review',flush=True)
