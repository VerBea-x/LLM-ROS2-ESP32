import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from dataclasses import replace
from src.course_audit.randomness_audit import run
from src.course_audit.plan_auditor import WorldState,SemanticItem,PlanAuditor

ROOT=Path(__file__).resolve().parents[1]

class ProtocolRecoveryTests(unittest.TestCase):
    def test_resume_preserves_received_response_and_checks_frozen_world(self):
        calls=[0]
        def fake(*args):
            calls[0]+=1
            if calls[0]==2:raise RuntimeError('模型 API 网络错误: fixture transport interruption')
            return {'id':calls[0],'choices':[{'message':{'tool_calls':[{'function':{'name':'stop','arguments':'{}'}}]}}]}
        with tempfile.TemporaryDirectory() as d,patch('src.course_audit.randomness_audit.chat_completion',side_effect=fake):
            out=Path(d)/'raw.jsonl'
            with self.assertRaises(RuntimeError):run('custom','frozen world',out)
            first=out.read_text()
            with self.assertRaises(ValueError):run('custom','changed world',out,resume_after_network=True)
            self.assertEqual(out.read_text(),first)
            run('custom','frozen world',out,resume_after_network=True)
            rows=[json.loads(x) for x in out.read_text().splitlines()]
            self.assertEqual(len(rows),40);self.assertEqual(rows[0]['raw_response']['id'],1)
            self.assertEqual(calls[0],41)
            self.assertEqual(len({(r['instruction_id'],r['temperature'],r['repetition']) for r in rows}),40)
            self.assertTrue(out.with_suffix('.jsonl.resume.jsonl').exists())

    def test_fresh_label_does_not_legalize_invented_coordinates(self):
        w=WorldState.from_mapping(json.loads((ROOT/'config/lesson8_fixture.json').read_text()))
        w=replace(w,semantic_items={**w.semantic_items,'W1_door':SemanticItem(95.,2.,2.)})
        decision=PlanAuditor(w).audit({'name':'navigate_to','arguments':{'x':3.,'y':2.,'label':'W1_door'}})
        self.assertFalse(decision.allowed);self.assertEqual(decision.rule_id,'R3')

if __name__=='__main__':unittest.main()
