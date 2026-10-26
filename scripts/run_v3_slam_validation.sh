#!/usr/bin/env bash
# Full live AMCL/SLAM simulation run using a previously received model plan.
set -eo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source /opt/ros/humble/setup.bash
[[ -f /tmp/course_rebuild_ros_ws/install/setup.bash ]] || bash "$ROOT/scripts/build_ros.sh"
source /tmp/course_rebuild_ros_ws/install/setup.bash
export ROS_DOMAIN_ID=47 SIM_GATEWAY_WS=ws://127.0.0.1:8000/ws COURSE_SLAM_RAYS=720
export ROS_LOG_DIR=/tmp/course_v3_slam_logs PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ROOT/src:$PYTHONPATH"
RUN_ID="${COURSE_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUT="$ROOT/evidence/raw/week8_v3_slam/$RUN_ID"
RUNTIME="/tmp/course_v3_slam/$RUN_ID"
SIM=/home/yahboom/embodied-sim-lite/embodied-sim-lite
mkdir -p run
exec 9>run/domain47.lock
flock -n 9 || { echo '域47正在运行'; exit 2; }
[[ ! -e "$OUT" ]] || { echo '实验已存在，换新编号'; exit 2; }
python3 - <<'PY'
import socket
with socket.socket() as s:
 if s.connect_ex(('127.0.0.1',8000))==0:raise SystemExit('8000已使用；没有中断现有服务')
PY
mkdir -p "$OUT/initialization" "$RUNTIME/map"
cp outputs/slam_improvement/map_slam.{pgm,yaml} "$RUNTIME/map/"
cp evidence/raw/week34_slam_map/20261026_slam_amcl_v1/params_snapshot.yaml "$OUT/params_snapshot.yaml"
cleanup() {
 for pid in "${agent:-}" "${navigation:-}" "${bridge:-}" "${gateway:-}"; do
  [[ -z "$pid" ]] || kill -TERM -- "-$pid" 2>/dev/null || true
 done
 wait || true
}
trap cleanup EXIT
setsid python3 scripts/gateway_sensor_variant.py --simdir "$SIM" --seed 42 --port 8000 --slip .05 > "$OUT/gateway.log" 2>&1 &
gateway=$!
sleep 2
setsid python3 "$SIM/ros_bridge.py" > "$OUT/bridge.log" 2>&1 &
bridge=$!
setsid ros2 launch nav_g03 sim_navigation.launch.py map:="$RUNTIME/map/map_slam.yaml" params_file:="$OUT/params_snapshot.yaml" navigate_timeout_s:=60 > "$OUT/navigation.log" 2>&1 &
navigation=$!
python3 scripts/run_slam_map_benchmark.py --output "$OUT/initialization" --round 1 --initialize-only > "$OUT/initialization/collector.log" 2>&1
python3 scripts/prepare_v3_slam_integration.py --benchmark evidence/raw/week34_slam_map/20261026_slam_amcl_v1 --map-snapshot "$OUT/initialization/costmap_snapshot.json" --output "$OUT/agent"
setsid python3 -m course_audit.agent_ros_node --world "$OUT/agent/world.json" --semantic "$OUT/agent/semantic.json" --frozen-plans "$OUT/agent/plans.json" --task-contracts config/task_contracts_v3.json --execute-sim --log "$OUT/agent/agent_events.jsonl" > "$OUT/agent/node.log" 2>&1 &
agent=$!
python3 scripts/record_v3_slam_integration.py --output "$OUT/agent"
