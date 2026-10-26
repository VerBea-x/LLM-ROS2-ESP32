#!/usr/bin/env python3
"""Freeze20 visually reviewed indoor scenes before the v2 inference run."""
import collections,datetime as dt,hashlib,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

root=Path(__file__).resolve().parents[1];source=root/'data/annotations/instances_val2017.json'
out=root/'data/coco_indoor20_v2';(out/'images').mkdir(exist_ok=True)
if (out/'dataset.json').exists():raise FileExistsError('v2 dataset already frozen')
doc=json.loads(source.read_text());cats={c['id']:c['name'] for c in doc['categories']};images={i['id']:i for i in doc['images']}
groups={'cup':[3934,9400,9590,10707,13659],
        'bottle':[7574,13729,13923,14038,22705,24610,26564],
        'chair':[139,1993,4495,18380],
        'negative':[1503,9772,17379,39477]}
scene_notes={3934:'living room',9400:'indoor work/dining table',9590:'dining room',10707:'living room',13659:'office',
 7574:'kitchen',13729:'living room',13923:'living room',14038:'studio apartment',22705:'kitchen refrigerator area',
 24610:'study/dining room',26564:'office desk',139:'living/dining room',1993:'bedroom',4495:'living room',18380:'family dining room',
 1503:'office workstation',9772:'bathroom vanity',17379:'bathroom',39477:'living room'}
selected=[(i,g) for g,ids in groups.items() for i in ids];targets={'cup','bottle','chair'}
anns=collections.defaultdict(list)
for a in doc['annotations']:
 if cats[a['category_id']] in targets and not a.get('iscrowd'):anns[a['image_id']].append(a)
stamp=dt.datetime.now(dt.timezone.utc).isoformat();scenes=[]
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',14)
sheet=Image.new('RGB',(1440,1050),'#f0f3f7');draw=ImageDraw.Draw(sheet)
for j,(i,g) in enumerate(selected):
 im=images[i];path=out/'images'/im['file_name'];path.write_bytes((out/'candidates'/im['file_name']).read_bytes())
 objects=[]
 for a in anns[i]:
  x,y,w,h=a['bbox'];objects.append({'label':cats[a['category_id']],'bbox':[x,y,x+w,y+h],'annotation_id':a['id']})
 if g=='negative' and objects:raise ValueError('negative has target annotations')
 scenes.append({'sample_id':f'coco_val2017_{i:012d}','image':'images/'+im['file_name'],'source_group':'public','selection_group':g,
  'scene_review':scene_notes[i],'scene_review_before_v2_inference':True,
  'image_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'truth_source':'official COCO instances_val2017.json',
  'truth_frozen_at':stamp,'objects':objects,'width':im['width'],'height':im['height'],'license_id':im.get('license'),
  'flickr_url':im.get('flickr_url'),'download_url':'https://s3.amazonaws.com/images.cocodataset.org/val2017/'+im['file_name']})
 preview=Image.open(path).convert('RGB');preview.thumbnail((350,175));x=(j%4)*360;y=(j//4)*210
 sheet.paste(preview,(x,y+28));draw.text((x+3,y+5),str(i)+' '+scene_notes[i],font=font,fill='black')
dataset={'dataset_protocol':'public_substitution_v1','version':'indoor20_v2',
 'substitution_note':'User authorized public-only data and required relevant indoor scenes; all20 public, none claimed self-captured.',
 'selection_rule':'Annotation-based candidate filter followed by visual scene-context review; no v2 detector output used.',
 'reviewed_rejections':['bear and outdoor negative images','isolated mug/food closeups','cat/portrait closeups dominating scene'],
 'frozen_at':stamp,'categories':doc['categories'],'licenses':doc['licenses'],'scenes':scenes}
(out/'dataset.json').write_text(json.dumps(dataset,ensure_ascii=False,indent=2)+'\n');sheet.save(out/'scene_contact_sheet.jpg')
(root/'data/active_vision_dataset.json').write_text(json.dumps({'path':'data/coco_indoor20_v2','version':'indoor20_v2'},indent=2)+'\n')
print('Frozen20 reviewed indoor scenes; all-public provenance retained')
