#!/usr/bin/env bash
set -eo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SIM=/home/yahboom/embodied-sim-lite/embodied-sim-lite
export ROS_DOMAIN_ID=48 SIM_GATEWAY_WS=ws://127.0.0.1:8001/ws
export ROS_LOG_DIR=/tmp/course_rebuild_slam_logs PYTHONDONTWRITEBYTECODE=1
source /opt/ros/humble/setup.bash
RUN_ID="${COURSE_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
export COURSE_SLAM_RAYS="${COURSE_SLAM_RAYS:-24}"
export COURSE_SLAM_SLIP="${COURSE_SLAM_SLIP:-0.05}"
export COURSE_SLAM_MATCH_RANGE="${COURSE_SLAM_MATCH_RANGE:-5.0}"
export COURSE_SLAM_PROFILE="${COURSE_SLAM_PROFILE:-baseline}"
OUT="$ROOT/evidence/raw/week3_slam/$RUN_ID"
RUNTIME="/tmp/course_rebuild_slam/$RUN_ID"
mkdir -p "$RUNTIME" "$OUT" "$ROOT/run"
exec 9>"$ROOT/run/domain48.lock"
flock -n 9 || { echo '已有域48实验'; exit 2; }
python3 - "$RUNTIME" "$OUT" <<'PY'
import sys,yaml,os
from pathlib import Path
runtime=Path(sys.argv[1]);out=Path(sys.argv[2])
d=yaml.safe_load(Path('/opt/ros/humble/share/slam_toolbox/config/mapper_params_online_async.yaml').read_text())
p=d['slam_toolbox']['ros__parameters']
p.update(use_sim_time=False,max_laser_range=float(os.environ['COURSE_SLAM_MATCH_RANGE']),minimum_travel_distance=.1,minimum_travel_heading=.1,minimum_time_interval=.1)
if os.environ['COURSE_SLAM_PROFILE']=='conservative_matching':
    p.update(use_scan_barycenter=False,do_loop_closing=False)
if os.environ['COURSE_SLAM_PROFILE']=='local_tracking':
    p.update(use_scan_barycenter=False,do_loop_closing=False,
             correlation_search_space_dimension=.2,correlation_search_space_resolution=.01,
             coarse_search_angle_offset=.1,coarse_angle_resolution=.008726646,
             fine_search_angle_offset=.001745329,distance_variance_penalty=.05,
             angle_variance_penalty=.02,minimum_angle_penalty=.5)
text=yaml.safe_dump(d,sort_keys=False)
(runtime/'mapper.yaml').write_text(text)
(out/'mapper.yaml').write_text(text)
PY
python3 -B "$ROOT/scripts/gateway_sensor_variant.py" --simdir "$SIM" --seed 42 --port 8001 --slip "$COURSE_SLAM_SLIP" > "$OUT/gateway.log" 2>&1 &
gateway=$!
trap 'kill -INT "${bag:-}" "${slam:-}" 2>/dev/null || true; kill "$gateway" "${bridge:-}" 2>/dev/null || true; wait || true; if [[ -d "$RUNTIME/rosbag" ]]; then cp -a "$RUNTIME/rosbag" "$OUT/rosbag"; fi' EXIT
sleep 2
python3 -B "$SIM/ros_bridge.py" > "$OUT/bridge.log" 2>&1 &
bridge=$!
ros2 launch slam_toolbox online_async_launch.py slam_params_file:="$RUNTIME/mapper.yaml" use_sim_time:=false > "$OUT/slam.log" 2>&1 &
slam=$!
if [[ "${COURSE_RECORD_BAG:-0}" == "1" ]]; then
  ros2 bag record -o "$RUNTIME/rosbag" /scan /odom /tf /tf_static /map > "$OUT/rosbag.log" 2>&1 &
  bag=$!
fi
echo "$OUT" > "$ROOT/run/domain48_output_dir.txt"
wait
