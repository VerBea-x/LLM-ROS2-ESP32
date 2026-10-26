import unittest
from src.course_audit.semantic_registration import project,register,export_map,error_components

class SemanticTests(unittest.TestCase):
    def test_course_geometry_left_positive_and_resolution_gate(self):
        self.assertAlmostEqual(project(320,320,320,640,640,(2,3,0))['x'],3)
        self.assertGreater(project(0,320,320,640,640,(2,3,0))['y'],3)
        with self.assertRaises(ValueError):project(160,320,320,640,320,(0,0,0))

    def test_merge_time_expiry_and_no_invented_tau(self):
        detection={'u':320,'image_width':640,'conf':.8,'label':'cup','evidence_id':'synthetic_unit_fixture'}
        intrinsics={'fx':320,'cx':320,'width':640}
        items=register([],detection,(0,0,0),intrinsics,.5,'2026-10-25T00:00:00Z')
        register(items,detection,(.2,0,0),intrinsics,.5,'2026-10-25T00:00:05Z')
        self.assertEqual(items[0]['n_obs'],2);self.assertAlmostEqual(items[0]['x'],1.1)
        with self.assertRaises(ValueError):export_map(items,{},'2026-10-25T00:00:10Z')
        doc=export_map(items,{'cup':{'tau_s':10,'observation_evidence_id':'unit_test_only'}},'2026-10-25T00:00:16Z')
        self.assertEqual(doc['items'][0]['state'],'stale')
        self.assertEqual(error_components((1,0),(3,0),(0,0))['radial_m'],-2)

if __name__=='__main__':unittest.main()
