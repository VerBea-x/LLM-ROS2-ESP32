import copy
import unittest
from src.course_audit.semantic_registration import register_frame,export_map
from src.course_audit.semantic_world import semantic_world_fields

K={'fx':320,'cx':320,'width':640}
def frame(*pixels):return [{'label':'cup','u':u,'image_width':640,'conf':.8,'evidence_id':f'fixture_{i}_{u}'} for i,u in enumerate(pixels)]
class FrameRegistrationTests(unittest.TestCase):
 def first(self):return register_frame([],frame(220,420),(2,3,0),K,.5,'2026-10-26T00:00:00Z')
 def test_close_same_class_objects_in_one_frame_stay_separate(self):
  items=self.first();self.assertEqual(len(items),2);self.assertNotEqual(items[0]['target_name'],items[1]['target_name'])
  self.assertLess(abs(items[0]['y']-items[1]['y']),1.)
 def test_repeated_observation_retains_unique_names_and_counts(self):
  first=self.first();second=register_frame(first,frame(222,418),(2,3,0),K,.5,'2026-10-26T00:00:01Z')
  self.assertEqual([r['target_name'] for r in first],[r['target_name'] for r in second]);self.assertEqual([r['n_obs'] for r in second],[2,2])
  self.assertEqual([r['n_obs'] for r in first],[1,1])
 def test_ambiguous_and_competing_assignments_reject_atomically(self):
  items=self.first();before=copy.deepcopy(items)
  for detections in [frame(320),frame(219,221)]:
   with self.assertRaises(ValueError):register_frame(items,detections,(2,3,0),K,.5,'2026-10-26T00:00:01Z')
   self.assertEqual(items,before)
 def test_unique_map_names_survive_auditor_conversion(self):
  doc=export_map(self.first(),{'cup':{'tau_s':4,'observation_evidence_id':'synthetic_rule'}},'2026-10-26T00:00:01Z')
  fields=semantic_world_fields(doc);self.assertEqual(set(fields['semantic_items']),{'cup__001','cup__002'})
 def test_reversed_detection_order_does_not_swap_map_identity(self):
  items=self.first();repeat=register_frame(items,frame(418,222),(2,3,0),K,.5,'2026-10-26T00:00:01Z')
  self.assertEqual([r['target_name'] for r in items],[r['target_name'] for r in repeat])
  self.assertGreater(repeat[0]['y'],3);self.assertLess(repeat[1]['y'],3)
 def test_old_frame_cannot_rewind_observations(self):
  items=self.first()
  with self.assertRaises(ValueError):register_frame(items,frame(220,420),(2,3,0),K,.5,'2026-10-25T23:59:59Z')
if __name__=='__main__':unittest.main()
