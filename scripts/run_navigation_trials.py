#!/usr/bin/env python3
"""Actual simulator service trials, with raw odom/AMCL and asynchronous truth trace."""
import argparse
import json
import math
import os
import time
import urllib.request
from pathlib import Path
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data, QoSProfile, DurabilityPolicy
from nav_msgs.msg import Odometry
from geometry_msgs.msg import PoseWithCovarianceStamped
from nav_g03.srv import NavigateTo


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--goals',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--domain',choices=['47','49'],default='47')
    p.add_argument('--health-port',type=int,choices=[8000,8002],default=8000)
    a=p.parse_args()
    if os.environ.get('ROS_DOMAIN_ID')!=a.domain:p.error('Requires matching isolated simulation domain')
    protocol=json.loads(a.goals.read_text())
    rclpy.init();n=Node('course_navigation_trial_recorder')
    events=[];start=time.monotonic()
    def emit(event,**data):
        events.append({'event':event,'wall_ns':time.time_ns(),'elapsed_s':time.monotonic()-start,**data})
    def pose(topic,msg):
        pos=msg.pose.pose
        q=pos.orientation
        emit(topic,stamp_ns=msg.header.stamp.sec*10**9+msg.header.stamp.nanosec,
             frame=msg.header.frame_id,x=pos.position.x,y=pos.position.y,
             yaw=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z)))
    subscriptions=[n.create_subscription(Odometry,'/odom',lambda m:pose('odom',m),qos_profile_sensor_data),
                   n.create_subscription(PoseWithCovarianceStamped,'/amcl_pose',lambda m:pose('amcl',m),
                     QoSProfile(depth=10,durability=DurabilityPolicy.TRANSIENT_LOCAL))]
    def truth():
        before=time.time_ns()
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{a.health_port}/health',timeout=1) as f:d=json.load(f)
            emit('truth',truth=d,request_start_ns=before)
            return d['robot_truth']
        except Exception as exc:emit('truth_error',error=str(exc));return None
    timer=n.create_timer(.2,truth)
    client=n.create_client(NavigateTo,'/navigate_to')
    if not client.wait_for_service(timeout_sec=10):raise RuntimeError('navigate_to unavailable')
    deadline=time.monotonic()+2
    while time.monotonic()<deadline:rclpy.spin_once(n,timeout_sec=.1)
    trials=[]
    a.output.parent.mkdir(parents=True,exist_ok=True)
    def save():
        a.output.write_text(json.dumps({'source_kind':'actual_simulation_service_execution',
          'protocol':protocol,'trials':trials,'events':events,
          'limitations':['AMCL on generated truth map; not SLAM-built map.','No real vehicle motion.']},ensure_ascii=False,indent=2)+'\n')
    try:
        for goal in protocol['goals']:
            before=truth()
            emit('request',goal=goal,start_truth=before)
            req=NavigateTo.Request();req.x,req.y,req.theta=map(float,goal['pose'])
            future=client.call_async(req)
            deadline=time.monotonic()+80
            while not future.done() and time.monotonic()<deadline:
                rclpy.spin_once(n,timeout_sec=.1)
            if not future.done():raise RuntimeError('client watchdog 80s; stop experiment')
            result=future.result();after=truth()
            record={'id':goal['id'],'pose':goal['pose'],'expected':goal['expected'],
                    'result':result.result,'reason':result.reason,'elapsed_s':result.elapsed,
                    'start_truth':before,'end_truth':after}
            if after:record['truth_goal_error_m']=math.hypot(after['x']-req.x,after['y']-req.y)
            trials.append(record);emit('response',**record);save();print(json.dumps(record,ensure_ascii=False),flush=True)
            deadline=time.monotonic()+1
            while time.monotonic()<deadline:rclpy.spin_once(n,timeout_sec=.1)
    finally:
        save();n.destroy_node();rclpy.shutdown()


if __name__=='__main__':main()
