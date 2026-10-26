import unittest
from pathlib import Path
from src.course_audit.detection_metrics import evaluate

class PublicSubstitutionTests(unittest.TestCase):
    def test_public_only_requires_explicit_substitution_without_faking_custom_sources(self):
        scenes=[{'sample_id':str(i),'source_group':'public','truth_source':'unit_test',
                 'truth_frozen_at':'before_prediction','image':'unused','objects':[]} for i in range(20)]
        dataset={'scenes':scenes};pred={'scenes':{str(i):[] for i in range(20)}}
        with self.assertRaises(ValueError):evaluate(dataset,pred,Path('.'),require_images=False)
        dataset['dataset_protocol']='public_substitution_v1'
        with self.assertRaises(ValueError):evaluate(dataset,pred,Path('.'),require_images=False)
        dataset['substitution_note']='explicitly authorized all-public alternative'
        report=evaluate(dataset,pred,Path('.'),require_images=False)
        self.assertEqual(report['dataset_protocol'],'public_substitution_v1')
        self.assertTrue(all(s['source_group']=='public' for s in scenes))

if __name__=='__main__':unittest.main()
