#!/usr/bin/env bash
set -eo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SIM=/home/yahboom/embodied-sim-lite/embodied-sim-lite
export ROS_DOMAIN_ID=49 SIM_GATEWAY_WS=ws://127.0.0.1:8002/ws
export ROS_LOG_DIR=/tmp/course_truth_integration_logs PYTHONDONTWRITEBYTECODE=1
RUN_ID="${COURSE_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUT="$ROOT/evidence/raw/week8_integration/$RUN_ID"
BRIDGE_ARGS=()
if [[ "${1:-}" == "--timeout-injection" ]]; then
  OUT="$ROOT/evidence/raw/week4_timeout/$RUN_ID"
  BRIDGE_ARGS=(--ros-args -r /cmd_vel:=/sim_dropped_cmd_vel -r /cmd_vel_nav:=/sim_dropped_cmd_vel_nav)
fi
source /opt/ros/humble/setup.bash
source /tmp/course_rebuild_ros_ws/install/setup.bash
mkdir -p "$ROOT/run"
exec 9>"$ROOT/run/domain49.lock"
flock -n 9 || { echo '本项目域49已有运行实例'; exit 2; }
python3 - <<'PY'
import socket
s=socket.socket()
if s.connect_ex(('127.0.0.1',8002))==0:
    raise SystemExit('8002端口已使用；请先停止原实例，不自动覆盖')
PY
RUNTIME="/tmp/course_truth_integration/$RUN_ID"
mkdir -p "$RUNTIME/map" "$OUT"
cp "$ROOT/evidence/raw/week3_truth_map/"* "$RUNTIME/map/"
cp "$ROOT/ros2_ws/src/nav_g03/config/nav2_params.yaml" "$RUNTIME/params.yaml"
if [[ "${1:-}" == "--timeout-injection" ]]; then
  python3 - "$RUNTIME/params.yaml" <<'PY'
import yaml
import sys
from pathlib import Path
p=Path(sys.argv[1])
d=yaml.safe_load(p.read_text())
d['controller_server']['ros__parameters']['progress_checker']['movement_time_allowance']=90.0
p.write_text(yaml.safe_dump(d,sort_keys=False))
PY
fi
cp "$RUNTIME/params.yaml" "$OUT/params_snapshot.yaml"
python3 -B "$SIM/nav_gateway.py" --simdir "$SIM" --seed 42 --port 8002 --slip 0 > "$OUT/gateway.log" 2>&1 &
gateway=$!
trap 'kill -INT "${navigation:-}" 2>/dev/null || true; kill "$gateway" "${bridge:-}" 2>/dev/null || true; wait || true' EXIT
sleep 2
python3 -B "$SIM/ros_bridge.py" "${BRIDGE_ARGS[@]}" > "$OUT/bridge.log" 2>&1 &
bridge=$!
ros2 launch nav_g03 sim_truth_navigation.launch.py map:="$RUNTIME/map/map_gt.yaml" params_file:="$RUNTIME/params.yaml" > "$OUT/nav.log" 2>&1 &
navigation=$!
echo "$OUT" > "$ROOT/run/domain49_output_dir.txt"
python3 "$ROOT/scripts/wait_navigation_ready.py" --output "$OUT/readiness.json"
echo "导航就绪，证据目录：$OUT"
wait
