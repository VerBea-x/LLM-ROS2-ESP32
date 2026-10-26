#!/usr/bin/env python3
"""Simulation experiment positioning helper. Truth drives placement, never SLAM/AMCL TF."""
import json
import math
import time
import urllib.request
from geometry_msgs.msg import Twist


def read_truth(port=8000):
    with urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=1) as f:
        state=json.load(f)
    if state.get('mode')!='nav-static':raise RuntimeError('requires static simulator')
    return state


def drive(node,publisher,x,y,port=8000,timeout=80,recorder=None,obstacles=None,min_clearance_m=0.0):
    import rclpy
    start=time.monotonic();last=None;stalled=0
    try:
        while time.monotonic()-start<timeout:
            state=read_truth(port);t=state['robot_truth'];dx=x-t['x'];dy=y-t['y']
            if obstacles is not None:
                clearance=min([t['x']-.2,10-t['x']-.2,t['y']-.2,10-t['y']-.2]+
                    [math.hypot(t['x']-o['x'],t['y']-o['y'])-o['r']-.2 for o in obstacles])
                if clearance<min_clearance_m:
                    raise RuntimeError(f'experiment footprint guard: clearance={clearance:.3f}m')
            dist=math.hypot(dx,dy)
            if recorder:recorder('placement',truth=state,target=[x,y])
            if dist<0.08:return state
            error=math.atan2(math.sin(math.atan2(dy,dx)-math.radians(t['theta_deg'])),
                             math.cos(math.atan2(dy,dx)-math.radians(t['theta_deg'])))
            cmd=Twist();cmd.angular.z=max(-.6,min(.6,error*1.8))
            cmd.linear.x=min(.3,dist*.7) if abs(error)<.35 else 0.0
            publisher.publish(cmd)
            if last and math.hypot(t['x']-last['x'],t['y']-last['y'])<.001 and cmd.linear.x>.05:
                stalled+=1
                if stalled>40:raise RuntimeError('truth driver collision/stall; no automatic bypass')
            else:stalled=0
            last=t;rclpy.spin_once(node,timeout_sec=.1)
        raise TimeoutError('simulation positioning timeout')
    finally:
        for _ in range(5):publisher.publish(Twist());rclpy.spin_once(node,timeout_sec=.1)
