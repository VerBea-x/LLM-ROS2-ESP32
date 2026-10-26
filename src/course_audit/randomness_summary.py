"""Recompute tool-name consistency and parameter variants from 40 raw API results."""
import argparse
import collections
import json
from pathlib import Path


def summarize(rows):
    groups=collections.defaultdict(list)
    for row in rows:groups[(row['instruction_id'],row['temperature'])].append(row)
    results=[]
    for (instruction,temp),group in sorted(groups.items()):
        sequences=[];variants=[];malformed=[]
        for row in group:
            try:
                msg=row['raw_response']['choices'][0]['message']
                calls=msg.get('tool_calls') or []
                seq=tuple(c['function']['name'] for c in calls) if calls else ('TEXT_RESPONSE',)
                sequences.append(seq)
                # API IDs vary independently of the generated plan: exclude them.
                plan=[{'name':c['function']['name'],'arguments':json.loads(c['function']['arguments'])} for c in calls]
                variants.append(json.dumps(plan if calls else msg.get('content'),ensure_ascii=False,sort_keys=True))
            except (KeyError,TypeError,ValueError) as exc:
                malformed.append({'repetition':row['repetition'],'error':str(exc)})
                sequences.append(('MALFORMED',));variants.append('MALFORMED')
        counter=collections.Counter(sequences)
        common,count=counter.most_common(1)[0]
        reps=[r['repetition'] for r in group]
        complete=len(group)==10 and sorted(reps)==list(range(1,11))
        first3=[seq for _,seq in sorted(zip(reps,sequences))[:3]]
        firstvars=[v for _,v in sorted(zip(reps,variants))[:3]]
        classification=None
        if len(first3)==3:
            classification='A' if len(set(firstvars))==1 else ('B' if len(set(first3))==1 else 'C')
        results.append({'instruction_id':instruction,'temperature':temp,'n':len(group),'complete':complete,
                        'most_common_tool_sequence':common,'consistency':count/10,
                        'sequence_variants':len(counter),'parameter_or_text_variants':len(set(variants)),
                        'first_three_classification':classification,'malformed':malformed,
                        'correctness':'requires expected-action and semantic-source review; consistency is not correctness'})
    complete=(len(rows)==40 and len(groups)==4 and all(r['complete'] for r in results)
              and len({r['protocol_sha256'] for r in rows})==1
              and set(groups)=={(i,t) for i in ('common','custom') for t in (.2,.8)})
    return {'complete_40_call_protocol':complete,'row_count':len(rows),'groups':results}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();report=summarize([json.loads(s) for s in a.input.read_text().splitlines() if s.strip()])
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report['complete_40_call_protocol'] else 1


if __name__=='__main__':raise SystemExit(main())
