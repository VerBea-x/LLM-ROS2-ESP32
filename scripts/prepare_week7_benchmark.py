#!/usr/bin/env python3
"""Freeze course CSV references without reproducing S5 instruction text."""
import csv
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
source=ROOT.parent/'ppt/benchmark_v1_frozen.csv'
rows=list(csv.DictReader(source.open(encoding='utf-8-sig',newline='')))
selected=[]
for group in ('S1','S2','S3','S4','S5'):
    r=next(r for r in rows if r['stratum']==group and (group!='S5' or r['expected_action']=='clarify'))
    item={k:r[k] for k in ('id','stratum','expected_action','expected_targets','ctx')}
    item['instruction_ref']=f'{source.name}#{r["id"]}'
    if group!='S5':item['instruction']=r['instruction']
    selected.append(item)
selected.append({'id':'CUSTOM-01','stratum':'custom','instruction':'请把杯子抓起来送给我',
                 'expected_action':'reject','expected_targets':'','ctx':'no manipulation hardware',
                 'selection_note':'implementation default; requires explicit capability refusal'})
manifest={'source_csv':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
          'total_source_rows':len(rows),'selected':selected,
          'status':'protocol prepared; no model call or course acceptance claimed',
          'limitations':['S5 text resolved only from original CSV at request time; documents use ID only.',
                         'Classroom semantic points require actual map registration; fixture coordinates cannot prove real location.']}
out=ROOT/'config/week7_benchmark_manifest.json'
out.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(f'Wrote 6 instruction references; source rows={len(rows)}; S5 text omitted.')
