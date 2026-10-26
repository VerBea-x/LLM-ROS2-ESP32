#!/usr/bin/env python3
"""Submit one fixed simulation integration instruction and record actual events/truth."""
import json
import argparse
import os
import time
from pathlib import Path
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from sim_truth_driver import read_truth

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--instruction',default='去P2实验点然后停下')
    p.add_argument('--output',type=Path,default=ROOT/'evidence/raw/week8_integration/execution_trace.json')
    p.add_argument('--planner-kind',choices=['frozen','real_model'],default='frozen')
    a=p.parse_args()
    if a.output.exists():p.error('output exists; choose a new trial file')
    if os.environ.get('ROS_DOMAIN_ID')!='49':raise RuntimeError('requires truth integration domain49')
    rclpy.init();n=Node('course_agent_integration_recorder')
    publisher=n.create_publisher(String,'/agent/instruction',10)
    events=[];truth=[];completed=[False];start=time.monotonic()
    def receive(msg):
        event=json.loads(msg.data);events.append(event)
        if 'final_report' in event:completed[0]=True
    sub=n.create_subscription(String,'/agent/plan_events',receive,100)
    def tick():truth.append({'wall_ns':time.time_ns(),**read_truth(8002)})
    timer=n.create_timer(.2,tick)
    deadline=time.monotonic()+2
    while time.monotonic()<deadline:rclpy.spin_once(n,timeout_sec=.1)
    m=String();m.data=a.instruction;publisher.publish(m)
    try:
        while time.monotonic()-start<80 and not completed[0]:rclpy.spin_once(n,timeout_sec=.1)
    finally:
        final=read_truth(8002)
        out=a.output
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps({'source_kind':'actual_simulation_'+a.planner_kind+'_integration','instruction':m.data,
            'completed':completed[0],'events':events,'truth_trace':truth,'final_truth':final,
            'limitations':[('Handwritten frozen proposal; no model request made.' if a.planner_kind=='frozen' else 'Real model request; declared virtual landmarks, not visually detected objects.'),
                            'slip=0 and map->odom identity: intentional truth localization, not AMCL or recovery.',
                            'battery=60 and tau=300 are explicit integration settings, not measured W6 evidence.']},ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'completed':completed[0],'event_types':[e['type'] for e in events],
                          'final_truth':final,'report':next((e for e in reversed(events) if 'final_report' in e),None)},ensure_ascii=False))
        n.destroy_node();rclpy.shutdown()

if __name__=='__main__':main()
