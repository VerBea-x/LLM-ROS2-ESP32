"""Explicit six-request W7 dry run from frozen CSV references. No motor executor."""
import argparse
import datetime as dt
import hashlib
import json
import csv
from pathlib import Path
from .llm_planner import plan_once
from .plan_auditor import schema_check


def run(manifest_path,world_path,output):
    manifest=json.loads(manifest_path.read_text());world=json.loads(world_path.read_text())
    source=Path(manifest['source_csv'])
    if hashlib.sha256(source.read_bytes()).hexdigest()!=manifest['source_sha256']:
        raise ValueError('benchmark CSV changed since freeze')
    rows={r['id']:r for r in csv.DictReader(source.open(encoding='utf-8-sig',newline=''))}
    if output.exists():raise FileExistsError('use a new output file; never silently mix runs')
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as stream:
        for spec in manifest['selected']:
            instruction=rows[spec['id']]['instruction'] if spec['stratum']!='custom' else spec['instruction']
            plan=plan_once(instruction,world,.2)
            checks=[schema_check(c) for c in plan['tool_calls']]
            expected=spec['expected_action']
            targets=[c['arguments'].get('label') for c in plan['tool_calls']
                     if c.get('name')=='navigate_to' and isinstance(c.get('arguments'),dict)]
            target_match=targets==spec['expected_targets'].split('|') if expected.startswith('navigate') else None
            row={'timestamp_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
                 'benchmark_ref':('S5-' if spec['stratum']=='S5' else '')+spec['id'],
                 'stratum':spec['stratum'],'expected_action':expected,'expected_targets':spec['expected_targets'],
                 'schema_checks':checks,'target_sequence_match':target_match,
                 'manual_action_review_required':expected in {'reject','clarify'},
                 'world_sha256':hashlib.sha256(world_path.read_bytes()).hexdigest(),**plan}
            # Original CSV is the authoritative instruction record; S5 text is not duplicated here.
            if spec['stratum']!='S5':row['instruction']=instruction
            stream.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n');stream.flush()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--world',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--run-real',action='store_true')
    a=p.parse_args()
    if not a.run_real:p.error('requires --run-real; makes exactly six API calls; no automatic retry')
    run(a.manifest,a.world,a.output)

if __name__=='__main__':main()
