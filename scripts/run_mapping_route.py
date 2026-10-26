#!/usr/bin/env python3
"""Truth-assisted simulation mapping route; SLAM consumes only scan/odom."""
import json
import argparse
import os
import time
from pathlib import Path
import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from sim_truth_driver import drive,read_truth

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--route-file',type=Path)
    args=parser.parse_args()
    if args.output.exists():parser.error('output exists; use a new run file')
    if os.environ.get('ROS_DOMAIN_ID')!='48':raise RuntimeError('requires isolated mapping domain 48')
    rclpy.init();node=Node('course_sim_mapping_positioner')
    pub=node.create_publisher(Twist,'/cmd_vel',10)
    route=[[8.5,8.8],[6.0,9.2],[5.8,6.0],[2.0,6.0],[1.0,3.0],[4.0,3.0],[4.0,1.0],[8.7,1.0],[9.0,3.3],[9.0,6.0],[8.08,6.238]]
    obstacles=None;clearance=0.0;protocol=None
    if args.route_file:
        import websocket
        protocol=json.loads(args.route_file.read_text());route=protocol['route'];clearance=protocol['minimum_clearance_m']
        ws=websocket.create_connection('ws://127.0.0.1:8001/ws',timeout=5)
        scene=json.loads(ws.recv());ws.close();obstacles=scene['obstacles']
    events=[]
    def record(event,**kw):events.append({'event':event,'wall_ns':time.time_ns(),**kw})
    out=args.output
    out.parent.mkdir(parents=True,exist_ok=True)
    try:
        for x,y in route:
            drive(node,pub,x,y,port=8001,recorder=record,obstacles=obstacles,min_clearance_m=clearance)
            out.write_text(json.dumps({'source_kind':'simulation_truth_assisted_mapping_route','route':route,'events':events},indent=2)+'\n')
            print(f'Placed at {x}, {y}',flush=True)
    except Exception as exc:
        record('route_failure',error=str(exc));raise
    finally:
        out.write_text(json.dumps({'source_kind':'simulation_truth_assisted_mapping_route','route':route,'events':events,
          'route_protocol':protocol,'obstacles':obstacles,'minimum_clearance_m':clearance,
          'limitations':['Truth positions only the experiment robot. It does not publish map->odom or replace SLAM.',
                          'Mapper noise defaults are declared, not calibrated from real hardware.']},indent=2)+'\n')
        node.destroy_node();rclpy.shutdown()

if __name__=='__main__':main()
