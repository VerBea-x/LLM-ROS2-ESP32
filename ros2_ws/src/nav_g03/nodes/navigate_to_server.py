#!/usr/bin/env python3
"""One-shot `/navigate_to` adapter with costmap gate and verified timeout stop."""
from __future__ import annotations

import math
import threading
import time

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import OccupancyGrid, Odometry
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy

from nav_g03.srv import NavigateTo


def yaw_from_quaternion(q) -> float:
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                      1.0 - 2.0 * (q.y * q.y + q.z * q.z))


class NavigateToServer(Node):
    def __init__(self, timeout_s: float = 60.0, occupied_threshold: int = 50):
        super().__init__("course_navigate_to_server")
        self.timeout_s = float(timeout_s)
        self.occupied_threshold = int(occupied_threshold)
        self.group = ReentrantCallbackGroup()
        self._busy_lock = threading.Lock()
        self._busy = False
        self._costmap = None
        self._speed = None
        self._odom_received_mono = None
        qos = QoSProfile(depth=1, reliability=QoSReliabilityPolicy.RELIABLE,
                         durability=QoSDurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(OccupancyGrid, "/global_costmap/costmap", self._costmap_cb,
                                 qos, callback_group=self.group)
        self.create_subscription(Odometry, "/odom", self._odom_cb, 10,
                                 callback_group=self.group)
        self._action = ActionClient(self, NavigateToPose, "/navigate_to_pose",
                                    callback_group=self.group)
        self.create_service(NavigateTo, "/navigate_to", self._handle,
                            callback_group=self.group)
        self.get_logger().info(
            f"/navigate_to ready; timeout={self.timeout_s:.1f}s; "
            "global costmap precheck enabled; no automatic retries")

    def _costmap_cb(self, message: OccupancyGrid) -> None:
        self._costmap = message

    def _odom_cb(self, message: Odometry) -> None:
        twist = message.twist.twist
        self._speed = (abs(float(twist.linear.x)), abs(float(twist.angular.z)))
        self._odom_received_mono = time.monotonic()

    def _cost_at(self, x: float, y: float) -> tuple[int | None, str]:
        grid = self._costmap
        if grid is None:
            return None, "global costmap has not published"
        origin = grid.info.origin
        yaw = yaw_from_quaternion(origin.orientation)
        dx, dy = x - origin.position.x, y - origin.position.y
        c, s = math.cos(yaw), math.sin(yaw)
        local_x, local_y = c * dx + s * dy, -s * dx + c * dy
        resolution = float(grid.info.resolution)
        if resolution <= 0:
            return None, "global costmap resolution is invalid"
        mx, my = math.floor(local_x / resolution), math.floor(local_y / resolution)
        if mx < 0 or my < 0 or mx >= grid.info.width or my >= grid.info.height:
            return None, "target is outside global costmap bounds"
        return int(grid.data[my * grid.info.width + mx]), ""

    @staticmethod
    def _set_response(response, result: str, reason: str, started: float):
        response.result = result
        response.reason = reason
        response.elapsed = time.monotonic() - started
        return response

    @staticmethod
    def _wait_future(future, timeout_s: float) -> bool:
        event = threading.Event()
        future.add_done_callback(lambda _future: event.set())
        return event.wait(timeout_s)

    def _wait_stopped(self, timeout_s: float = 3.0) -> bool:
        deadline = time.monotonic() + timeout_s
        stopped_since = None
        while time.monotonic() < deadline:
            now = time.monotonic()
            fresh = (self._odom_received_mono is not None and
                     now - self._odom_received_mono <= 0.5)
            speed = self._speed
            if fresh and speed is not None and speed[0] < 0.02 and speed[1] < 0.05:
                if stopped_since is None:
                    stopped_since = now
                elif now - stopped_since >= 0.5:
                    return True
            else:
                stopped_since = None
            time.sleep(0.05)
        return False

    def _handle(self, request, response):
        started = time.monotonic()
        with self._busy_lock:
            if self._busy:
                return self._set_response(response, "FAILED", "服务忙：已有导航请求；拒绝并发。", started)
            self._busy = True
        try:
            if not all(math.isfinite(v) for v in (request.x, request.y, request.theta)):
                return self._set_response(response, "FAILED", "目标 x/y/theta 必须是有限数值。", started)
            cost, cost_error = self._cost_at(float(request.x), float(request.y))
            if cost_error:
                return self._set_response(response, "FAILED", f"无法验证目标可行性：{cost_error}。", started)
            if cost is None or cost < 0 or cost >= self.occupied_threshold:
                return self._set_response(
                    response, "FAILED",
                    f"目标不是已知空闲栅格（cost={cost}，阈值<{self.occupied_threshold}）；未派发导航。",
                    started)
            if not self._action.wait_for_server(timeout_sec=5.0):
                return self._set_response(response, "FAILED", "Nav2 /navigate_to_pose 动作服务器不可用。", started)

            goal = NavigateToPose.Goal()
            pose = PoseStamped()
            pose.header.frame_id = "map"
            pose.header.stamp = self.get_clock().now().to_msg()
            pose.pose.position.x = float(request.x)
            pose.pose.position.y = float(request.y)
            pose.pose.orientation.z = math.sin(float(request.theta) / 2.0)
            pose.pose.orientation.w = math.cos(float(request.theta) / 2.0)
            goal.pose = pose

            send_future = self._action.send_goal_async(goal)
            if not self._wait_future(send_future, 5.0):
                return self._set_response(response, "FAILED", "Nav2 接受目标响应超时；未自动重发。", started)
            handle = send_future.result()
            if handle is None or not handle.accepted:
                return self._set_response(response, "FAILED", "Nav2 拒绝目标；未自动重发。", started)

            result_future = handle.get_result_async()
            if self._wait_future(result_future, self.timeout_s):
                wrapped = result_future.result()
                if wrapped.status == GoalStatus.STATUS_SUCCEEDED:
                    return self._set_response(response, "SUCCEEDED", "Nav2 报告目标到达。", started)
                error = getattr(getattr(wrapped, "result", None), "error_msg", "")
                reason = f"Nav2 结果状态 {wrapped.status}" + (f"：{error}" if error else "")
                return self._set_response(response, "FAILED", reason, started)

            cancel_future = handle.cancel_goal_async()
            cancel_ack = self._wait_future(cancel_future, 5.0)
            stopped = self._wait_stopped(3.0)
            if stopped:
                reason = f"超过 {self.timeout_s:.1f}s；已请求取消，且新鲜 /odom 连续0.5s确认静止。"
            else:
                reason = f"超过 {self.timeout_s:.1f}s；取消确认={cancel_ack}，但未能由新鲜 /odom 确认静止。"
            return self._set_response(response, "TIMEOUT", reason, started)
        except Exception as exc:  # return a visible failure; do not swallow as success
            self.get_logger().error(f"/navigate_to internal failure: {type(exc).__name__}: {exc}")
            return self._set_response(response, "FAILED", f"服务内部错误：{type(exc).__name__}: {exc}", started)
        finally:
            with self._busy_lock:
                self._busy = False


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--occupied-threshold", type=int, default=50)
    args, ros_args = parser.parse_known_args()
    rclpy.init(args=ros_args)
    node = NavigateToServer(args.timeout, args.occupied_threshold)
    executor = MultiThreadedExecutor(num_threads=3)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
