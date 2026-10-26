#!/usr/bin/env bash
set -eo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SIM_DIR="/home/yahboom/embodied-sim-lite/embodied-sim-lite"
RUN_DIR="$ROOT/run"
mkdir -p "$RUN_DIR" "$ROOT/evidence/raw"
export ROS_HOME="${ROS_HOME:-/tmp/course_rebuild_ros_home}"
export ROS_LOG_DIR="${ROS_LOG_DIR:-/tmp/course_rebuild_ros_logs}"
export PYTHONDONTWRITEBYTECODE=1
export ROS_DOMAIN_ID=47
source /opt/ros/humble/setup.bash
for name in gateway bridge; do
  pid_file="$RUN_DIR/$name.pid"
  if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
    echo "已有本项目 $name 进程：$(cat "$pid_file")" >&2
    exit 2
  fi
done
if python3 -c 'import socket,sys; s=socket.socket(); s.settimeout(.5); sys.exit(0 if s.connect_ex(("127.0.0.1",8000)) == 0 else 1)'; then
  echo "127.0.0.1:8000 已被占用；为避免中断现有服务，未启动仿真。" >&2
  exit 2
fi
nohup python3 -B "$SIM_DIR/nav_gateway.py" --simdir "$SIM_DIR" --seed 42 --port 8000 --slip 0.05 \
  >"$ROOT/evidence/raw/nav_gateway.log" 2>&1 &
echo $! > "$RUN_DIR/gateway.pid"
ready=0
for _ in $(seq 1 20); do
  if python3 - <<'PY'
import json, urllib.request
try:
    d=json.load(urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=1))
    raise SystemExit(0 if d.get("mode") == "nav-static" else 1)
except Exception:
    raise SystemExit(1)
PY
  then ready=1; break; fi
  sleep 0.5
done
if [[ "$ready" != 1 ]]; then
  kill "$(cat "$RUN_DIR/gateway.pid")" 2>/dev/null || true
  rm -f "$RUN_DIR/gateway.pid"
  echo "静态仿真 gateway 未就绪；查看 evidence/raw/nav_gateway.log" >&2
  exit 2
fi
nohup python3 -B "$SIM_DIR/ros_bridge.py" >"$ROOT/evidence/raw/ros_bridge.log" 2>&1 &
echo $! > "$RUN_DIR/bridge.pid"
sleep 3
if ! kill -0 "$(cat "$RUN_DIR/bridge.pid")" 2>/dev/null; then
  echo "ROS bridge 未运行；gateway 仍保持启动。查看 evidence/raw/ros_bridge.log" >&2
  exit 2
fi
echo "静态仿真与 ROS bridge 已启动。所有数据均为仿真数据。"
echo "停止时运行 scripts/stop_sim_bridge.sh。"
if [[ "${1:-}" == "--foreground" ]]; then
  trap 'bash "$ROOT/scripts/stop_sim_bridge.sh"' EXIT
  wait
fi
