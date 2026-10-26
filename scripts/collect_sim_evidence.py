#!/usr/bin/env python3
"""Read-only ROS snapshot with fresh AMCL/truth pairs in isolated simulator domain."""
import argparse
import json
import math
import os
import time
import urllib.request
from pathlib import Path

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from nav_msgs.msg import OccupancyGrid, Odometry
from sensor_msgs.msg import LaserScan
from tf2_msgs.msg import TFMessage
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data, QoSProfile, DurabilityPolicy


def yaw(q):
    return math.atan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--seconds', type=float, default=15)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--domain', choices=['47','48','49'],default='47')
    p.add_argument('--health-port',type=int,choices=[8000,8001,8002],default=8000)
    a = p.parse_args()
    if a.output.exists():p.error('output already exists; choose a new snapshot filename')
    if os.environ.get('ROS_DOMAIN_ID') != a.domain:
        p.error('simulation collector requires matching isolated ROS domain')
    rclpy.init()
    n = Node('course_evidence_collector')
    start = time.monotonic()
    counts, stamps, pairs, transforms, grids, trajectory = {}, {}, [], {}, {}, []
    scan_contract={}
    def record(topic, msg):
        elapsed = time.monotonic()-start
        counts.setdefault(topic, []).append(elapsed)
        if hasattr(msg, 'header'):
            stamp = msg.header.stamp.sec*10**9+msg.header.stamp.nanosec
            stamps.setdefault(topic, []).append(stamp)
        return elapsed
    def odom(msg):
        t = record('/odom', msg)
        pose = msg.pose.pose
        trajectory.append({'elapsed_s':t, 'x':pose.position.x,'y':pose.position.y,
                           'yaw':yaw(pose.orientation), 'frame':msg.header.frame_id})
    def scan(msg):
        record('/scan',msg)
        scan_contract.update(ray_count=len(msg.ranges),angle_increment_rad=msg.angle_increment,
                             range_min_m=msg.range_min,range_max_m=msg.range_max,frame_id=msg.header.frame_id)
    def amcl(msg):
        record('/amcl_pose',msg)
        try:
            before = time.time_ns()
            with urllib.request.urlopen(f'http://127.0.0.1:{a.health_port}/health',timeout=1) as f:
                truth=json.load(f)
            after = time.time_ns()
            pose=msg.pose.pose
            pairs.append({'amcl_stamp_ns':stamps['/amcl_pose'][-1],
                          'estimate_frame':msg.header.frame_id,
                          'est_x':pose.position.x,'est_y':pose.position.y,'est_yaw':yaw(pose.orientation),
                          'truth':truth,'truth_request_start_ns':before,'truth_request_end_ns':after,
                          'estimate_to_truth_age_s':(before-stamps['/amcl_pose'][-1])/1e9})
        except Exception as exc:
            pairs.append({'error':str(exc)})
    def tf(msg):
        for x in msg.transforms:
            transforms[x.header.frame_id+'->'+x.child_frame_id]={
                'parent':x.header.frame_id,'child':x.child_frame_id,
                'translation':[x.transform.translation.x,x.transform.translation.y,x.transform.translation.z],
                'rotation':[x.transform.rotation.x,x.transform.rotation.y,x.transform.rotation.z,x.transform.rotation.w]}
    def grid(topic,msg):
        record(topic,msg)
        grids[topic]={'resolution':msg.info.resolution,'width':msg.info.width,'height':msg.info.height,
                      'frame':msg.header.frame_id,'origin':[msg.info.origin.position.x,msg.info.origin.position.y],
                      'origin_yaw':yaw(msg.info.origin.orientation),'data':list(msg.data)}
    subs=[n.create_subscription(Odometry,'/odom',odom,qos_profile_sensor_data),
          n.create_subscription(LaserScan,'/scan',scan,qos_profile_sensor_data),
          n.create_subscription(PoseWithCovarianceStamped,'/amcl_pose',amcl,10),
          n.create_subscription(TFMessage,'/tf',tf,50),
          n.create_subscription(TFMessage,'/tf_static',tf,QoSProfile(depth=10,durability=DurabilityPolicy.TRANSIENT_LOCAL))]
    for topic in ['/map','/global_costmap/costmap']:
        subs.append(n.create_subscription(OccupancyGrid,topic,lambda m,t=topic:grid(t,m),
                    QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL)))
    while time.monotonic()-start<a.seconds:
        rclpy.spin_once(n,timeout_sec=.1)
    rates={}
    for topic,ts in counts.items():
        rates[topic]={'messages':len(ts),'hz':(len(ts)-1)/(ts[-1]-ts[0]) if len(ts)>1 else None,
                      'unique_stamps':len(set(stamps.get(topic,[])))}
    data={'source_kind':'simulation_live_ros','ros_domain_id':int(a.domain),'duration_s':time.monotonic()-start,
          'topics':n.get_topic_names_and_types(),'rates':rates,'transforms':transforms,
          'amcl_truth_pairs':pairs,'grids':grids,'odom_trajectory':trajectory,'scan_contract':scan_contract,
          'limitations':['AMCL initialized using explicit simulator truth seed; not kidnapping recovery.',
                          'HTTP truth is asynchronous; request latency and message age recorded.',
                          'Distinct message stamps do not by themselves prove statistical independence.']}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'rates':rates,'tf_edges':list(transforms),'pairs':len(pairs),'grids':list(grids)},ensure_ascii=False))
    n.destroy_node()
    rclpy.shutdown()


if __name__=='__main__':main()
