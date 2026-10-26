#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export COURSE_SLAM_RAYS=720 COURSE_SLAM_SLIP=0.05 COURSE_SLAM_MATCH_RANGE=4.9
export COURSE_SLAM_PROFILE=local_tracking COURSE_RECORD_BAG=1
exec bash "$ROOT/scripts/run_slam_session.sh"
