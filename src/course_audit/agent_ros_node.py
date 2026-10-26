"""ROS course interface. Frozen proposals by default; model and execution are explicit."""
import argparse
import json
import os
import queue
import threading
import time
from pathlib import Path
from .plan_auditor import PlanAuditor,WorldState
from .state_machine import ExecutionResult,run_state_machine
from .llm_planner import plan_once
from .ros_executor import make_sim_navigate_executor
from .task_contract import TaskContract


def main():
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world',type=Path,required=True)
    p.add_argument('--semantic',type=Path,required=True)
    p.add_argument('--planner-world',type=Path,help='frozen semantic summary used in the model requests')
    p.add_argument('--task-contracts',type=Path,help='explicit contracts keyed by exact instruction; no inferred intent')
    p.add_argument('--frozen-plans',type=Path)
    p.add_argument('--run-real-model',action='store_true')
    p.add_argument('--execute-sim',action='store_true')
    p.add_argument('--log',type=Path,required=True)
    a=p.parse_args()
    if os.environ.get('ROS_DOMAIN_ID') not in {'47','49'}:p.error('requires isolated simulation domain 47 or49')
    if a.run_real_model==bool(a.frozen_plans):p.error('choose exactly one: --frozen-plans or --run-real-model')
    if a.execute_sim and not a.task_contracts:p.error('仿真执行需--task-contracts明确完整步骤，不能仅以单条工具合法判任务完整。')
    plans=json.loads(a.frozen_plans.read_text()) if a.frozen_plans else {}
    contracts=json.loads(a.task_contracts.read_text()) if a.task_contracts else {}
    rclpy.init();node=Node('course_agent');pub=node.create_publisher(String,'/agent/plan_events',100)
    jobs=queue.Queue(maxsize=1);done=threading.Event()
    a.log.parent.mkdir(parents=True,exist_ok=True)
    def emit(event):
        record={'wall_ns':time.time_ns(),**event}
        with a.log.open('a') as f:f.write(json.dumps(record,ensure_ascii=False,allow_nan=False)+'\n')
        msg=String();msg.data=json.dumps(record,ensure_ascii=False,allow_nan=False);pub.publish(msg)
    def receive(msg):
        try:jobs.put_nowait(msg.data)
        except queue.Full:emit({'type':'report','result':'BUSY','evidence':['bounded queue occupied'],'limitations':['not executed']})
    sub=node.create_subscription(String,'/agent/instruction',receive,10)
    def worker():
        while not done.is_set():
            try:instruction=jobs.get(timeout=.2)
            except queue.Empty:continue
            executor=None
            try:
                world_data=json.loads(a.world.read_text())
                # Epoch seconds are the production clock; fixture snapshots deliberately freeze their clock.
                if not world_data.get('fixture_only'):world_data['now_s']=time.time()
                world=WorldState.from_mapping(world_data)
                semantic=json.loads(a.semantic.read_text())
                if a.task_contracts and instruction not in contracts:
                    emit({'type':'report','result':'REJECTED','final_report':{'result':'REJECTED',
                          'evidence':['指令没有显式任务契约；不猜测步骤。'],'limitations':['没有执行工具。']}})
                    continue
                contract=TaskContract.from_mapping(contracts[instruction]) if a.task_contracts else None
                if a.run_real_model:
                    def planner(text,feedback):
                        planning_world=json.loads(a.planner_world.read_text()) if a.planner_world else world_data
                        return plan_once(text+('\n执行反馈：'+feedback if feedback else ''),planning_world)
                else:
                    def planner(text,feedback):
                        if feedback:return {'tool_calls':[],'refusal':'固定规划器不猜测修复；执行失败后报告。'}
                        return plans.get(text,{'tool_calls':[],'refusal':'该指令无冻结计划；需要真实模型或补充计划。'})
                if a.execute_sim:executor=make_sim_navigate_executor(semantic)
                else:executor=lambda call:ExecutionResult(True,'仅干跑；没有调用执行接口。',{'dry_run':True,'call':call})
                result=run_state_machine(instruction,planner,PlanAuditor(world),executor,
                    limitations=['仿真集成验证；固定规划器不证明LLM理解能力。' if not a.run_real_model else '模型调用原始输出保存在plan事件。',
                                 '语义与资源状态依赖传入证据；仿真占位电量不证明实车电量。'],event_sink=emit,task_contract=contract)
                emit({'type':'report','final_report':result['report'],'result':result['result']})
            except Exception as exc:
                emit({'type':'report','result':'FAILED','evidence':[str(exc)],'limitations':['未将异常报告为成功。']})
            finally:
                if executor and hasattr(executor,'close'):executor.close()
                jobs.task_done()
    thread=threading.Thread(target=worker,daemon=True);thread.start()
    node.get_logger().info('/agent/instruction -> plan/audit/exec/report; domain='+os.environ['ROS_DOMAIN_ID'])
    try:rclpy.spin(node)
    except KeyboardInterrupt:pass
    finally:
        done.set();thread.join(timeout=75);node.destroy_node();rclpy.try_shutdown()


if __name__=='__main__':main()
