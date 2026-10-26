#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SIM_DIR="/home/yahboom/embodied-sim-lite/embodied-sim-lite"
RUN_DIR="$ROOT/run"
for name in bridge gateway; do
  pid_file="$RUN_DIR/$name.pid"
  if [[ ! -f "$pid_file" ]]; then continue; fi
  pid="$(cat "$pid_file")"
  expected="$SIM_DIR/ros_bridge.py"
  [[ "$name" == "gateway" ]] && expected="$SIM_DIR/nav_gateway.py"
  cmdline="$(ps -p "$pid" -o args= 2>/dev/null || true)"
  if [[ "$pid" =~ ^[0-9]+$ ]] && [[ "$cmdline" == *"$expected"* ]]; then
    kill "$pid"
    for _ in $(seq 1 20); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.1
    done
    if kill -0 "$pid" 2>/dev/null; then kill -TERM "$pid" 2>/dev/null || true; fi
  else
    echo "$name PID 未匹配本项目启动命令，未终止：$pid" >&2
  fi
  rm -f "$pid_file"
done
echo "已停止本项目记录且命令行匹配的仿真进程。"
