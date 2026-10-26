#!/usr/bin/env python3
"""Publish one explicitly labeled truth-seeded AMCL initial pose for the simulator."""
from __future__ import annotations

import argparse
import json
import math
import time
import urllib.request

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.node import Node


def read_truth(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=3.0) as response:
        state = json.loads(response.read().decode("utf-8"))
    return state["robot_truth"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--health-url", default="http://127.0.0.1:8000/health")
    parser.add_argument("--sigma-x-m", type=float, required=True)
    parser.add_argument("--sigma-y-m", type=float, required=True)
    parser.add_argument("--sigma-yaw-deg", type=float, required=True)
    parser.add_argument("--offset-x-m", type=float, default=0.0)
    parser.add_argument("--offset-y-m", type=float, default=0.0)
    parser.add_argument("--offset-yaw-deg", type=float, default=0.0)
    args, ros_args = parser.parse_known_args()
    if min(args.sigma_x_m, args.sigma_y_m, args.sigma_yaw_deg) <= 0:
        parser.error("covariance sigmas must be positive and pre-registered")
    truth = read_truth(args.health_url)
    rclpy.init(args=ros_args)
    node = Node("course_truth_seeded_initial_pose")
    publisher = node.create_publisher(PoseWithCovarianceStamped, "/initialpose", 10)
    deadline = time.monotonic() + 5.0
    while publisher.get_subscription_count() == 0 and time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.1)
    if publisher.get_subscription_count() == 0:
        node.destroy_node()
        rclpy.shutdown()
        raise RuntimeError("No AMCL initialpose subscriber discovered; nothing published")
    message = PoseWithCovarianceStamped()
    message.header.frame_id = "map"
    message.header.stamp = node.get_clock().now().to_msg()
    message.pose.pose.position.x = float(truth["x"]) + args.offset_x_m
    message.pose.pose.position.y = float(truth["y"]) + args.offset_y_m
    yaw = math.radians(float(truth["theta_deg"]) + args.offset_yaw_deg)
    message.pose.pose.orientation.z = math.sin(yaw / 2.0)
    message.pose.pose.orientation.w = math.cos(yaw / 2.0)
    cov = message.pose.covariance
    cov[0] = args.sigma_x_m ** 2
    cov[7] = args.sigma_y_m ** 2
    cov[35] = math.radians(args.sigma_yaw_deg) ** 2
    # DDS discovery can precede usable transport matching; keep publishing for
    # a bounded interval instead of exiting before the initial pose is delivered.
    for _ in range(10):
        message.header.stamp = node.get_clock().now().to_msg()
        publisher.publish(message)
        rclpy.spin_once(node, timeout_sec=0.5)
    node.get_logger().info(
        f"initialpose published at ({message.pose.pose.position.x:.3f}, "
        f"{message.pose.pose.position.y:.3f}, {math.degrees(yaw):.1f} deg); "
        "seeded from simulator truth plus explicit offsets; not an independent localization result")
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
