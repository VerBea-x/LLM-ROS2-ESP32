#!/usr/bin/env bash
set -eo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ROS_HOME="${ROS_HOME:-/tmp/course_rebuild_ros_home}"
export ROS_LOG_DIR="${ROS_LOG_DIR:-/tmp/course_rebuild_ros_logs}"
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=47
source /tmp/course_rebuild_ros_ws/install/setup.bash
mkdir -p /tmp/course_rebuild_runtime/map
cp "$ROOT/evidence/raw/week3_truth_map/"* /tmp/course_rebuild_runtime/map/
cp "$ROOT/ros2_ws/src/nav_g03/config/nav2_params.yaml" /tmp/course_rebuild_runtime/nav2_params.yaml
ros2 launch nav_g03 sim_navigation.launch.py \
  map:=/tmp/course_rebuild_runtime/map/map_gt.yaml \
  params_file:=/tmp/course_rebuild_runtime/nav2_params.yaml \
  navigate_timeout_s:=60
