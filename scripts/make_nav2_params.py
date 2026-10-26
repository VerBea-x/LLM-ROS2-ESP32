#!/usr/bin/env python3
"""Create a Humble Nav2 config from the installed defaults and simulator contract."""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path,
                        default=Path("/opt/ros/humble/share/nav2_bringup/params/nav2_params.yaml"))
    parser.add_argument("--output", type=Path,
                        default=Path("ros2_ws/src/nav_g03/config/nav2_params.yaml"))
    args = parser.parse_args()
    data = yaml.safe_load(args.source.read_text(encoding="utf-8"))
    for node in data.values():
        if isinstance(node, dict) and isinstance(node.get("ros__parameters"), dict):
            node["ros__parameters"]["use_sim_time"] = False
    for name in ("global_costmap", "local_costmap"):
        data[name][name]["ros__parameters"]["use_sim_time"] = False
    data["amcl"]["ros__parameters"].update({
        "base_frame_id": "base_footprint", "odom_frame_id": "odom", "global_frame_id": "map",
        "scan_topic": "/scan", "laser_max_range": 5.0, "max_beams": 24,
    })
    controller = data["controller_server"]["ros__parameters"]["FollowPath"]
    controller.update({"max_vel_x": 1.0, "max_speed_xy": 1.0, "max_vel_theta": 1.5,
                       "min_vel_x": 0.0, "min_vel_y": 0.0})
    for name in ("global_costmap", "local_costmap"):
        params = data[name][name]["ros__parameters"]
        params.update({"robot_base_frame": "base_footprint", "robot_radius": 0.20})
        if name == "global_costmap":
            params["global_frame"] = "map"
        else:
            params["global_frame"] = "odom"
        for layer_name in ("obstacle_layer", "voxel_layer"):
            layer = params.get(layer_name)
            if isinstance(layer, dict) and "scan" in layer:
                layer["scan"].update({"topic": "/scan", "raytrace_max_range": 5.0,
                                      "obstacle_max_range": 5.0})
    velocity = data["velocity_smoother"]["ros__parameters"]
    velocity["max_velocity"] = [1.0, 0.0, 1.5]
    velocity["min_velocity"] = [0.0, 0.0, -1.5]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"Wrote {args.output}; ROS Humble defaults + simulator limits 1.0 m/s, 1.5 rad/s, radius 0.20 m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
