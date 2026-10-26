#!/usr/bin/env bash
set -eo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source /opt/ros/humble/setup.bash
[[ -f /tmp/course_rebuild_ros_ws/install/setup.bash ]] || bash "$ROOT/scripts/build_ros.sh"
source /tmp/course_rebuild_ros_ws/install/setup.bash
export ROS_DOMAIN_ID=47 SIM_GATEWAY_WS=ws://127.0.0.1:8000/ws COURSE_SLAM_RAYS=720
export ROS_LOG_DIR=/tmp/course_slam_validation_logs PYTHONDONTWRITEBYTECODE=1
SIM=/home/yahboom/embodied-sim-lite/embodied-sim-lite
RUN_ID="${COURSE_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
PROTOCOL="${COURSE_PROTOCOL:-$ROOT/config/week34_safe_return_precise_v4.json}"
OUT="$ROOT/evidence/raw/week34_slam_map/$RUN_ID"
RUNTIME="/tmp/course_slam_validation/$RUN_ID"
mkdir -p "$ROOT/run"
exec 9>"$ROOT/run/domain47.lock"
flock -n 9 || { echo '域47已有实验'; exit 2; }
[[ ! -e "$OUT" ]] || { echo '输出已存在，请换运行编号'; exit 2; }
mkdir -p "$OUT" "$RUNTIME/map"
cp outputs/slam_improvement/map_slam.{pgm,yaml} "$RUNTIME/map/"
cp "$PROTOCOL" "$OUT/protocol.json"
python3 - "$RUNTIME/params.yaml" "$OUT/protocol.json" <<'PY'
from pathlib import Path
import sys,yaml,json
p=yaml.safe_load(Path('ros2_ws/src/nav_g03/config/nav2_params.yaml').read_text())
p['amcl']['ros__parameters']['max_beams']=60
overrides=json.loads(Path(sys.argv[2]).read_text()).get('parameter_overrides',{})
p['amcl']['ros__parameters'].update(overrides.get('amcl',{}))
p['controller_server']['ros__parameters']['general_goal_checker'].update(overrides.get('goal_checker',{}))
p['controller_server']['ros__parameters']['FollowPath'].update(overrides.get('FollowPath',{}))
p['velocity_smoother']['ros__parameters'].update(overrides.get('velocity_smoother',{}))
Path(sys.argv[1]).write_text(yaml.safe_dump(p,sort_keys=False))
PY
cp "$RUNTIME/params.yaml" "$OUT/params_snapshot.yaml"
cleanup_round() {
 for pid in "${navigation:-}" "${bridge:-}" "${gateway:-}"; do
  [[ -z "$pid" ]] || kill -TERM -- "-$pid" 2>/dev/null || true
 done
 wait || true
 navigation=; bridge=; gateway=
}
trap cleanup_round EXIT
for round in 1 2; do
 python3 - <<'PY'
import socket
with socket.socket() as s:
 if s.connect_ex(('127.0.0.1',8000))==0:raise SystemExit('8000已使用，未中断现有服务')
PY
 mkdir -p "$OUT/round$round"
 setsid python3 -B scripts/gateway_sensor_variant.py --simdir "$SIM" --seed 42 --port 8000 --slip 0.05 > "$OUT/round$round/gateway.log" 2>&1 &
 gateway=$!
 sleep 2
 setsid python3 -B "$SIM/ros_bridge.py" > "$OUT/round$round/bridge.log" 2>&1 &
 bridge=$!
 setsid ros2 launch nav_g03 sim_navigation.launch.py map:="$RUNTIME/map/map_slam.yaml" params_file:="$RUNTIME/params.yaml" navigate_timeout_s:=60 > "$OUT/round$round/navigation.log" 2>&1 &
 navigation=$!
 python3 scripts/run_slam_map_benchmark.py --output "$OUT/round$round" --round "$round" --protocol "$OUT/protocol.json" > "$OUT/round$round/collector.log" 2>&1 || echo "第${round}轮未通过，保留记录"
 cat "$OUT/round$round/collector.log"
 if [[ "$round" == 2 && "${COURSE_KEEP_STACK:-0}" == 1 ]]; then
  echo "$OUT" > run/slam_validation_output_dir.txt
  echo "两轮记录完成，保留本次仿真用于后续V3验证：$OUT"
  wait
 else
  cleanup_round
  sleep 2
 fi
done
