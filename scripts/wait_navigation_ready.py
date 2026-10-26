#!/usr/bin/env python3
"""Require active lifecycle nodes and a real, full-size map before trials."""
import argparse
import json
import math
import time
from pathlib import Path
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile,DurabilityPolicy
from nav_msgs.msg import OccupancyGrid
from lifecycle_msgs.srv import GetState


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--timeout',type=float,default=40)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();rclpy.init();node=Node('course_navigation_readiness_gate')
    maps={};states={};pending={}
    qos=QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL)
    subs=[node.create_subscription(OccupancyGrid,t,lambda msg,t=t:maps.__setitem__(t,msg),qos)
          for t in ['/map','/global_costmap/costmap']]
    names=['map_server','controller_server','planner_server','bt_navigator']
    clients={name:node.create_client(GetState,f'/{name}/get_state') for name in names}
    start=time.monotonic();next_check=start;ready=False
    try:
        while time.monotonic()-start<a.timeout:
            rclpy.spin_once(node,timeout_sec=.1)
            for name,future in list(pending.items()):
                if future.done():
                    if future.exception() is None:states[name]=future.result().current_state.label
                    del pending[name]
            if time.monotonic()>=next_check:
                for name,c in clients.items():
                    if name not in pending and c.service_is_ready():pending[name]=c.call_async(GetState.Request())
                next_check=time.monotonic()+1
            source=maps.get('/map');cost=maps.get('/global_costmap/costmap')
            if source and cost and all(states.get(name)=='active' for name in names):
                same=(source.info.width==cost.info.width and source.info.height==cost.info.height
                      and source.info.width>=200 and source.info.height>=200
                      and abs(source.info.resolution-cost.info.resolution)<1e-6)
                if same and len(cost.data)==cost.info.width*cost.info.height:ready=True;break
        report={'ready':ready,'states':states,'elapsed_s':time.monotonic()-start,
                'maps':{t:{'width':m.info.width,'height':m.info.height,'resolution':m.info.resolution,
                           'origin':[m.info.origin.position.x,m.info.origin.position.y]} for t,m in maps.items()}}
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
        return 0 if ready else 2
    finally:node.destroy_node();rclpy.shutdown()

if __name__=='__main__':raise SystemExit(main())
