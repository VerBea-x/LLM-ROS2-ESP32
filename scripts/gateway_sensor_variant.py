#!/usr/bin/env python3
"""Explicit simulated lidar variant; leaves the upstream simulator unchanged."""
import os
import runpy
import sys
from pathlib import Path

sim=Path('/home/yahboom/embodied-sim-lite/embodied-sim-lite')
sys.path.insert(0,str(sim))
from embodied_env import EmbodiedNavEnv
rays=int(os.environ.get('COURSE_SLAM_RAYS','24'))
if rays not in (24,360,720):raise ValueError('only preregistered24/360/720 rays allowed')
EmbodiedNavEnv.N_RAYS=rays
print(f'EXPLICIT SIMULATED SENSOR VARIANT: rays={rays}; not physical lidar',flush=True)
runpy.run_path(str(sim/'nav_gateway.py'),run_name='__main__')
