"""Capture a non-secret system baseline and optionally the live ROS graph."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any


EXPECTED_TOPICS = {
    "/cmd_vel": {"type": "geometry_msgs/msg/Twist", "frequency": "<=20 Hz"},
    "/odom": {"type": "nav_msgs/msg/Odometry", "frequency": "50 Hz (course target)"},
    "/imu": {"type": "sensor_msgs/msg/Imu", "frequency": "50 Hz (course target)"},
    "/scan": {"type": "sensor_msgs/msg/LaserScan", "frequency": "10 Hz (course target)"},
}


def _run(command: list[str], timeout_s: float = 8.0) -> dict[str, Any]:
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=timeout_s, check=False)
        return {"command": command, "returncode": result.returncode,
                "stdout": result.stdout.strip(), "stderr": result.stderr.strip()[:1200]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"command": command, "returncode": None, "stdout": "",
                "stderr": f"{type(exc).__name__}: {exc}"}


def collect(include_ros: bool = False, measure_rates: bool = False,
            rate_window_s: int = 3) -> dict[str, Any]:
    disk = shutil.disk_usage("/")
    mem = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, _, value = line.partition(":")
            if key in ("MemTotal", "MemAvailable"):
                mem[key] = value.strip()
    except OSError:
        pass
    distro = {}
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            key, sep, value = line.partition("=")
            if sep and key in ("NAME", "VERSION", "VERSION_ID", "PRETTY_NAME"):
                distro[key] = value.strip().strip('"')
    except OSError:
        pass
    report: dict[str, Any] = {
        "schema_version": 1,
        "captured_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_kind": "vm_host_snapshot",
        "platform": {"os": distro, "kernel": platform.release(),
                     "architecture": platform.machine(), "python": platform.python_version(),
                     "cpu_count": os.cpu_count(), "memory": mem,
                     "root_disk_bytes": {"total": disk.total, "used": disk.used, "free": disk.free},
                     "ros_distro_env": os.environ.get("ROS_DISTRO", "not_set")},
        "ros_graph": {"collected": False},
        "expected_course_contract": EXPECTED_TOPICS,
        "disclaimer": "系统信息是真实采集；若未启用ROS采集或话题无发布者，不推断课程接口已通过。",
    }
    if include_ros:
        topic_result = _run(["ros2", "topic", "list", "-t", "--no-daemon"])
        node_result = _run(["ros2", "node", "list", "--no-daemon"])
        topic_types: dict[str, str] = {}
        if topic_result["returncode"] == 0:
            for line in topic_result["stdout"].splitlines():
                parts = line.split(maxsplit=1)
                if len(parts) == 2:
                    topic_types[parts[0]] = parts[1].strip().strip("[]")
        observed = {}
        for topic, expected in EXPECTED_TOPICS.items():
            rate_result = None
            rate_status = "not_measured" if topic in topic_types else "no_publisher_seen"
            if measure_rates and topic in topic_types:
                rate_result = _run(["ros2", "topic", "hz", topic,
                                    "--window", str(rate_window_s), "--no-daemon"],
                                   timeout_s=rate_window_s + 4.0)
                rate_status = "captured" if rate_result["returncode"] == 0 else "measurement_incomplete"
            observed[topic] = {
                "expected": expected,
                "observed_type": topic_types.get(topic),
                "present": topic in topic_types,
                "rate_measurement": rate_result,
                "rate_status": rate_status,
            }
        report["ros_graph"] = {"collected": True, "topic_command": topic_result,
                               "node_command": node_result, "topics": topic_types,
                               "course_topics": observed,
                               "packages": {name: _run(["ros2", "pkg", "prefix", name])
                                            for name in ("nav2_bringup", "slam_toolbox", "nav_g03")}}
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ros", action="store_true", help="query the current ROS 2 graph (read-only)")
    parser.add_argument("--measure-rates", action="store_true",
                        help="also measure active course-topic rates for a short window")
    parser.add_argument("--rate-window-s", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("evidence/raw/week1_environment.json"))
    args = parser.parse_args()
    report = collect(args.ros, args.measure_rates, args.rate_window_s)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
