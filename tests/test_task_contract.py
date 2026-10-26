import unittest
from src.course_audit.task_contract import TaskContract
from src.course_audit.state_machine import ExecutionResult, run_state_machine
from tests.test_state_machine import load_world
from src.course_audit.plan_auditor import PlanAuditor


class TaskContractTests(unittest.TestCase):
    def contract(self, **changes):
        value={'required_sequence':['navigate_to','stop'], 'navigation_labels':['W1_door'],
               'evidence_id':'explicit_unit_test_task'}
        value.update(changes)
        return TaskContract.from_mapping(value)

    def run_plan(self,calls,contract):
        executed=[]
        result=run_state_machine('test',lambda *_:{'tool_calls':calls},PlanAuditor(load_world()),
            lambda c:executed.append(c) or ExecutionResult(True,'dry run',{}),task_contract=contract)
        return result,executed

    def test_incomplete_plan_never_executes_valid_prefix(self):
        result,executed=self.run_plan([{'name':'navigate_to','arguments':{'x':2.,'y':2.,'label':'W1_door'}}],self.contract())
        self.assertEqual(result['result'],'REJECTED');self.assertEqual(executed,[])
        self.assertEqual(result['evidence'][0]['rule_id'],'TASK_SEQUENCE')

    def test_target_order_is_part_of_contract(self):
        c=self.contract(required_sequence=['navigate_to','navigate_to'],navigation_labels=['A','B'])
        self.assertFalse(c.check([{'name':'navigate_to','arguments':{'label':'B'}},
                                  {'name':'navigate_to','arguments':{'label':'A'}}])['allowed'])

    def test_unavailable_camera_rejects_whole_task(self):
        c=self.contract(required_sequence=['navigate_to','capture_and_describe'],unavailable_tools=['capture_and_describe'])
        result,executed=self.run_plan([{'name':'navigate_to','arguments':{'x':2.,'y':2.,'label':'W1_door'}},
                                      {'name':'capture_and_describe','arguments':{}}],c)
        self.assertEqual(executed,[]);self.assertEqual(result['evidence'][0]['rule_id'],'TASK_CAPABILITY')

    def test_stop_does_not_claim_original_task_completed(self):
        result,executed=self.run_plan([{'name':'stop','arguments':{}}],self.contract())
        self.assertEqual(result['result'],'STOPPED');self.assertEqual(len(executed),1)

    def test_invalid_contract_and_planner_are_reported(self):
        with self.assertRaises(ValueError):self.contract(required_sequence='navigate_to')
        for planner,expected in [(lambda *_:[], 'REJECTED'),
                                  (lambda *_:(_ for _ in ()).throw(RuntimeError('transport unavailable')),'PLANNING_FAILED')]:
            result=run_state_machine('test',planner,PlanAuditor(load_world()),lambda _:self.fail('must not execute'))
            self.assertEqual(result['result'],expected)

if __name__=='__main__':unittest.main()
