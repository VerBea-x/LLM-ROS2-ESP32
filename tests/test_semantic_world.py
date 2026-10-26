import copy
import unittest
from src.course_audit.semantic_registration import register,export_map
from src.course_audit.semantic_world import semantic_world_fields


class SemanticWorldTests(unittest.TestCase):
    def document(self):
        return {'frame_id':'map','generated_at':'2026-10-26T00:00:05Z','items':[
            {'label':'cup','x':1.,'y':2.,'last_seen':'2026-10-26T00:00:00Z',
             'tau_s':4.,'tau_evidence_id':'synthetic_rule','evidence_ids':['synthetic_detection']}]}

    def test_duplicate_class_targets_do_not_overwrite_each_other(self):
        doc=self.document();other=copy.deepcopy(doc['items'][0]);other['x']=4.;doc['items'].append(other)
        with self.assertRaisesRegex(ValueError,'ambiguous'):semantic_world_fields(doc)

    def test_wrong_frame_and_untraceable_tau_are_rejected(self):
        doc=self.document();doc['frame_id']='camera'
        with self.assertRaises(ValueError):semantic_world_fields(doc)
        doc=self.document();doc['items'][0].pop('tau_evidence_id')
        with self.assertRaises(ValueError):semantic_world_fields(doc)

    def test_query_clock_and_observation_clock_stay_distinct(self):
        fields=semantic_world_fields(self.document())
        self.assertEqual(fields['now_s']-fields['semantic_items']['cup']['last_seen_s'],5.)
        self.assertEqual(fields['tau_s']['cup'],4.)

    def test_out_of_order_observation_cannot_mutate_registered_target(self):
        d={'label':'cup','u':320,'image_width':640,'conf':.8,'evidence_id':'later'}
        k={'fx':320,'cx':320,'width':640}
        items=register([],d,(0,0,0),k,.5,'2026-10-26T00:00:05Z');before=copy.deepcopy(items)
        with self.assertRaisesRegex(ValueError,'out-of-order'):
            register(items,{**d,'evidence_id':'earlier'},(.4,0,0),k,.5,'2026-10-26T00:00:04Z')
        self.assertEqual(items,before)

if __name__=='__main__':unittest.main()
