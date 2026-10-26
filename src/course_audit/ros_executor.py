"""Optional adapter to the existing ROS 2 `/navigate_to` course service.

It is intentionally opt-in. It only accepts already-audited calls and never
drives the ESP32 car; point this at the simulation stack only.
"""
from __future__ import annotations

import time
import os
from typing import Any

from .state_machine import ExecutionResult


def make_sim_navigate_executor(semantic_map: dict[str, Any], service_timeout_s: float = 70.0):
    if os.environ.get("ROS_DOMAIN_ID") not in {"47", "49"}:
        raise RuntimeError("仿真执行器只允许独立 ROS_DOMAIN_ID=47/49；请运行项目仿真启动脚本")
    try:
        from action_msgs.srv import CancelGoal
        from geometry_msgs.msg import Twist
        import rclpy
        from nav_g03.srv import NavigateTo
        from nav_msgs.msg import Odometry
        from rclpy.node import Node
    except ImportError as exc:
        raise RuntimeError("需先 source ROS 2 Humble 与包含 nav_g03 的工作区 overlay") from exc

    owns_context = not rclpy.ok()
    if owns_context:
        rclpy.init()
    node = Node("lesson8_sim_only_executor")
    client = node.create_client(NavigateTo, "/navigate_to")
    cancel_client = node.create_client(CancelGoal, "/navigate_to_pose/_action/cancel_goal")
    zero_pub = node.create_publisher(Twist, "/cmd_vel", 10)
    last_speed = {"value": None, "received_at": None}

    def on_odom(message: Any) -> None:
        twist = message.twist.twist
        last_speed["value"] = (abs(twist.linear.x), abs(twist.angular.z))
        last_speed["received_at"] = time.monotonic()

    odom_subscription = node.create_subscription(Odometry, "/odom", on_odom, 10)

    def execute(call: dict[str, Any]) -> ExecutionResult:
        if call.get('name') == 'get_semantic_map':
            return ExecutionResult(True,'返回已登记的仿真语义地图。',{'semantic_map':semantic_map})
        if call.get('name') == 'say':
            return ExecutionResult(True,'已记录文本播报；未生成音频。',{'text':call['arguments']['text'],'output_mode':'text_log'})
        if call.get("name") == "stop":
            if not cancel_client.wait_for_service(timeout_sec=2.0):
                return ExecutionResult(False, "仿真 Nav2 cancel 服务不可用；未声称停止成功。",
                                       {"service": "/navigate_to_pose/_action/cancel_goal"})
            request = CancelGoal.Request()
            request.goal_info.goal_id.uuid = [0] * 16  # ROS action protocol: cancel all goals
            request.goal_info.stamp.sec = 0
            request.goal_info.stamp.nanosec = 0
            future = cancel_client.call_async(request)
            rclpy.spin_until_future_complete(node, future, timeout_sec=5.0)
            if not future.done() or future.result() is None:
                return ExecutionResult(False, "仿真 Nav2 取消请求未确认；未声称停止成功。", {})
            cancel_response = future.result()
            # Send zero velocity repeatedly while confirming fresh odometry.
            deadline = time.monotonic() + 3.0
            stopped_since = None
            while time.monotonic() < deadline:
                zero_pub.publish(Twist())
                rclpy.spin_once(node, timeout_sec=0.05)
                speed = last_speed["value"]
                fresh = (last_speed["received_at"] is not None and
                         time.monotonic() - last_speed["received_at"] <= 0.5)
                if fresh and speed is not None and speed[0] < 0.02 and speed[1] < 0.05:
                    if stopped_since is None:
                        stopped_since = time.monotonic()
                    elif time.monotonic() - stopped_since >= 0.5:
                        return ExecutionResult(True, "Nav2 目标已取消并由新鲜 /odom 连续确认静止。",
                                               {"speed_mps_radps": list(speed),
                                                "cancel_return_code": cancel_response.return_code,
                                                "verified": True})
                else:
                    stopped_since = None
            return ExecutionResult(False, "已发取消/零速请求，但未能在3秒内由新鲜 /odom 确认静止。",
                                   {"last_speed": last_speed["value"], "verified": False})
        if call.get("name") != "navigate_to":
            return ExecutionResult(False, "该ROS导航适配器仅执行 navigate_to/stop；其他工具没有被执行。",
                                   {"tool": call.get("name")})
        args = call["arguments"]
        label = args["label"]
        item = semantic_map.get(label)
        if not isinstance(item, dict) or "theta" not in item:
            return ExecutionResult(False, f"语义地图 `{label}` 缺少已记录的朝向 theta；不猜测默认朝向。", {})
        if not client.wait_for_service(timeout_sec=2.0):
            return ExecutionResult(False, "仿真 /navigate_to 服务不可用。", {"service": "/navigate_to"})
        request = NavigateTo.Request()
        request.x = float(args["x"])
        request.y = float(args["y"])
        request.theta = float(item["theta"])
        start = time.monotonic()
        future = client.call_async(request)
        rclpy.spin_until_future_complete(node, future, timeout_sec=service_timeout_s)
        elapsed = time.monotonic() - start
        if not future.done():
            return ExecutionResult(False, "等待仿真导航服务响应超时。", {"elapsed_s": elapsed})
        response = future.result()
        if response is None:
            return ExecutionResult(False, "仿真导航服务没有返回响应。", {"elapsed_s": elapsed})
        return ExecutionResult(
            response.result == "SUCCEEDED", response.reason,
            {"result": response.result, "elapsed_s": response.elapsed,
             "requested_target_m": [request.x, request.y], "label": label},
        )

    def close() -> None:
        node.destroy_subscription(odom_subscription)
        node.destroy_node()
        if owns_context and rclpy.ok():
            rclpy.shutdown()

    execute.close = close  # type: ignore[attr-defined]
    return execute
