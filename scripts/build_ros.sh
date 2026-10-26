#!/usr/bin/env bash
set -eo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Humble rosidl splits non-ASCII source paths incorrectly. Keep canonical sources
# here and use an ASCII scratch workspace, regenerated on every build.
WS=/tmp/course_rebuild_ros_ws
mkdir -p "$WS/src" "$ROOT/evidence/raw"
cp -a "$ROOT/ros2_ws/src/nav_g03" "$WS/src/"
source /opt/ros/humble/setup.bash
cd "$WS"
colcon build --packages-select nav_g03 2>&1 | tee "$ROOT/evidence/raw/ros_build.log"
