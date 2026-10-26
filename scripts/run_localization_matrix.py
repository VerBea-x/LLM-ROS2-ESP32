#!/usr/bin/env python3
"""W3 five-point A/B matrix with fresh scan updates and independent truth readout."""
import csv
import json
import math
import os
import time
from pathlib import Path
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile,DurabilityPolicy
from geometry_msgs.msg import Twist,PoseWithCovarianceStamped
from std_srvs.srv import Empty
from sim_truth_driver import drive,read_truth

ROOT=Path(__file__).resolve().parents[1]

def angle(a,b):return math.atan2(math.sin(a-b),math.cos(a-b))

def main():
    if os.environ.get('ROS_DOMAIN_ID')!='47':raise RuntimeError('requires isolated simulation domain47')
    protocol=json.loads((ROOT/'config/week3_4_preregister.json').read_text())
    rclpy.init();n=Node('course_localization_matrix')
    velocity=n.create_publisher(Twist,'/cmd_vel',10)
    initial=n.create_publisher(PoseWithCovarianceStamped,'/initialpose',10)
    update=n.create_client(Empty,'/request_nomotion_update')
    samples=[];events=[];summaries=[];latest=[None];start=time.monotonic()
    active={'point':None,'condition':None,'after_stamp':0}
    seen=set()
    def record(event,**kw):events.append({'event':event,'elapsed_s':time.monotonic()-start,**kw})
    def receive(msg):
        stamp=msg.header.stamp.sec*10**9+msg.header.stamp.nanosec
        if stamp in seen or stamp<=active['after_stamp']:return
        seen.add(stamp)
        if active['point'] is None:return
        # Freeze the estimate before reading the independent truth source.
        pose=msg.pose.pose;q=pose.orientation
        est=(pose.position.x,pose.position.y,math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z)))
        before=time.time_ns();state=read_truth();after=time.time_ns();truth=state['robot_truth']
        age=(before-stamp)/1e9
        row={'point_id':active['point'],'condition':active['condition'],'amcl_stamp_ns':stamp,
             'est_x':est[0],'est_y':est[1],'est_yaw':est[2],
             'truth_x':truth['x'],'truth_y':truth['y'],'truth_yaw':math.radians(truth['theta_deg']),
             'truth_source':'simulator /health robot_truth seed42','estimate_frame':msg.header.frame_id,
             'truth_frame':'map','truth_request_s':(after-before)/1e9,'truth_age_s':age,
             'cov_x':msg.pose.covariance[0],'cov_y':msg.pose.covariance[7],
             'position_error_m':math.hypot(est[0]-truth['x'],est[1]-truth['y'])}
        row['valid_timing']=0<=age<=.3 and (after-before)/1e9<=.1
        samples.append(row);latest[0]=row
    sub=n.create_subscription(PoseWithCovarianceStamped,'/amcl_pose',receive,
          QoSProfile(depth=10,durability=DurabilityPolicy.TRANSIENT_LOCAL))
    raw=ROOT/'evidence/raw/week3_localization_matrix.json'
    def save():
        raw.write_text(json.dumps({'source_kind':'actual_simulation_amcl_vs_independent_truth',
           'protocol':protocol,'cells':summaries,'samples':samples,'events':events,
           'limitations':['Known truth map used; SLAM map validation is a separate experiment.',
                           'Truth-assisted positioning is experiment apparatus, not estimated navigation.',
                           'Repeated no-motion updates at a fixed point are correlated; one final sample per cell is used in course table.',
                           'Points are reachable local subset; whole-field coverage remains pending.']},ensure_ascii=False,indent=2)+'\n')
    try:
        if not update.wait_for_service(timeout_sec=5):raise RuntimeError('AMCL no-motion update service missing')
        for point in protocol['points']:
            active['point']=None
            drive(n,velocity,point['x'],point['y'],recorder=record)
            stop=time.monotonic()+1
            while time.monotonic()<stop:rclpy.spin_once(n,timeout_sec=.1)
            for condition in ('A','B'):
                t=read_truth()['robot_truth'];msg=PoseWithCovarianceStamped()
                msg.header.frame_id='map';msg.header.stamp=n.get_clock().now().to_msg()
                msg.pose.pose.position.x=t['x']+(1 if condition=='B' else 0)
                msg.pose.pose.position.y=t['y']
                yaw=math.radians(t['theta_deg']+(20 if condition=='B' else 0))
                msg.pose.pose.orientation.z=math.sin(yaw/2);msg.pose.pose.orientation.w=math.cos(yaw/2)
                msg.pose.covariance[0]=msg.pose.covariance[7]=.25**2
                msg.pose.covariance[35]=math.radians(10)**2
                active.update(point=point['id'],condition=condition,after_stamp=time.time_ns());latest[0]=None
                initial.publish(msg);record('initialization',point=point['id'],condition=condition,
                    truth=t,offset_x_m=1 if condition=='B' else 0,offset_yaw_deg=20 if condition=='B' else 0)
                begin=time.monotonic();next_update=begin+1;converged_since=None;convergence=None
                while time.monotonic()-begin<30:
                    now=time.monotonic()
                    if now>=next_update:
                        update.call_async(Empty.Request());next_update=now+1
                    rclpy.spin_once(n,timeout_sec=.1)
                    row=latest[0]
                    if row and row['valid_timing'] and row['position_error_m']<=.15:
                        if converged_since is None:converged_since=now
                        if now-converged_since>=3:
                            convergence=now-begin;break
                    else:converged_since=None
                final=latest[0]
                cell={'point_id':point['id'],'condition':condition,'convergence_s':convergence,
                      'status':'converged' if convergence is not None else 'not_converged_within_30s',
                      'final_sample':final,'observation_s':time.monotonic()-begin}
                summaries.append(cell);save()
                print(json.dumps({'point':point['id'],'condition':condition,'status':cell['status'],
                      'error_m':final['position_error_m'] if final else None},ensure_ascii=False),flush=True)
        selected=[c['final_sample'] for c in summaries if c['final_sample'] and c['final_sample']['valid_timing']]
        if selected:
            with (ROOT/'evidence/raw/week3_localization_selected.csv').open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(selected[0]));w.writeheader();w.writerows(selected)
    finally:
        active['point']=None;velocity.publish(Twist());save();n.destroy_node();rclpy.shutdown()

if __name__=='__main__':main()
