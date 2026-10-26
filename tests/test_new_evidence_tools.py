import copy
import json
import math
import unittest
from pathlib import Path
from dataclasses import replace
from src.course_audit.detection_metrics import evaluate
from src.course_audit.plan_auditor import PlanAuditor, WorldState, schema_check
from src.course_audit.state_machine import run_state_machine
from src.course_audit.randomness_summary import summarize

ROOT=Path(__file__).resolve().parents[1]

class EvidenceToolTests(unittest.TestCase):
    def test_detection_counts_duplicates_and_wrong_class(self):
        scenes=[];pred={}
        for i in range(20):
            sid=str(i)
            scenes.append({'sample_id':sid,'source_group':'public' if i<10 else 'custom',
                'truth_source':'unit fixture','truth_frozen_at':'fixture','image':'unused',
                'objects':[{'label':'cup','bbox':[0,0,10,10]}, {'label':'table','bbox':[20,20,30,30]}]})
            pred[sid]=[{'label':'cup','bbox':[0,0,10,10],'score':.9},
                       {'label':'cup','bbox':[0,0,10,10],'score':.8},
                       {'label':'chair','bbox':[20,20,30,30],'score':.6}]
        r=evaluate({'scenes':scenes},{'scenes':pred},ROOT,require_images=False)
        low=r['totals'][0];high=r['totals'][2]
        self.assertEqual((low['tp'],low['fp'],low['fn']),(20,40,20))
        self.assertEqual((high['tp'],high['fp'],high['fn']),(20,20,20))

    def test_nonfinite_resource_does_not_pass(self):
        world=WorldState.from_mapping(json.loads((ROOT/'config/lesson8_fixture.json').read_text()))
        call={'name':'navigate_to','arguments':{'x':2.,'y':2.,'label':'W1_door'}}
        self.assertFalse(PlanAuditor(replace(world,battery_pct=math.nan)).audit(call).allowed)

    def test_malformed_tool_never_executes(self):
        world=WorldState.from_mapping(json.loads((ROOT/'config/lesson8_fixture.json').read_text()))
        called=[]
        for bad in [None,42,{'name':[],'arguments':{}}]:
            self.assertFalse(schema_check(bad)[0])
            self.assertFalse(PlanAuditor(world).audit(bad).allowed)
        result=run_state_machine('fixture',lambda *_:{'tool_calls':{}},PlanAuditor(world),lambda c:called.append(c))
        self.assertEqual(result['result'],'REJECTED');self.assertEqual(called,[])

    def test_randomness_excludes_api_ids_and_checks_exact_groups(self):
        rows=[]
        for instruction in ('common','custom'):
            for temp in (.2,.8):
                for rep in range(1,11):
                    rows.append({'instruction_id':instruction,'temperature':temp,'repetition':rep,'protocol_sha256':'fixed',
                        'raw_response':{'choices':[{'message':{'tool_calls':[{'id':str(rep),'function':{'name':'stop','arguments':'{}'}}]}}]}})
        result=summarize(rows)
        self.assertTrue(result['complete_40_call_protocol'])
        self.assertTrue(all(g['parameter_or_text_variants']==1 for g in result['groups']))
        self.assertFalse(summarize(rows[:-1])['complete_40_call_protocol'])

if __name__=='__main__':unittest.main()
