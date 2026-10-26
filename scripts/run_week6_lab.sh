#!/usr/bin/env bash
# Controlled synthetic ROS input only. No motor publishers or model calls.
set -eo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=50 ROS_LOG_DIR=/tmp/course_week6_ros_logs PYTHONDONTWRITEBYTECODE=1
mkdir -p run
exec 9>run/domain50.lock
flock -n 9 || { echo '域50受控实验已在运行'; exit 2; }
OUT="${1:-evidence/raw/week6_ros_lab_$(date -u +%Y%m%dT%H%M%SZ)}"
[[ ! -e "$OUT" ]] || { echo '输出目录已存在，请换新目录'; exit 2; }
python3 scripts/semantic_mapper_node.py --rules config/week6_controlled_tau_rules.json --output "$OUT" &
course_mapper_pid=$!
trap 'kill -INT "$course_mapper_pid" 2>/dev/null || true; wait "$course_mapper_pid" || true' EXIT
LAB="${COURSE_SEMANTIC_LAB:-run_week6_ros_lab.py}"
case "$LAB" in run_week6_ros_lab.py|run_dense_semantic_ros_lab.py) ;; *) echo "未知实验入口"; exit 2;; esac
python3 "$ROOT/scripts/$LAB" --node-output "$OUT"
