"""Reproduce the course's fixed motion sequence inside Embodied-SimLite.

This is simulator-model evidence only. It is not a physical ESP32 measurement.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import sys
from pathlib import Path


SEQUENCE = [
    {"stage": "straight_1m", "linear_mps": 0.2, "angular_rps": 0.0, "duration_s": 5.0},
    {"stage": "pause_1s", "linear_mps": 0.0, "angular_rps": 0.0, "duration_s": 1.0},
    {"stage": "turn_90deg", "linear_mps": 0.0, "angular_rps": math.pi / 8.0, "duration_s": 4.0},
    {"stage": "straight_0.5m", "linear_mps": 0.2, "angular_rps": 0.0, "duration_s": 2.5},
]


def run(simulator_dir: Path, output_dir: Path, seeds: list[int], slip: float) -> dict:
    sys.path.insert(0, str(simulator_dir.resolve()))
    from embodied_env import EmbodiedNavEnv
    import numpy as np

    output_dir.mkdir(parents=True, exist_ok=True)
    trajectory_path = output_dir / "week2_sim_trajectory.csv"
    summary = {
        "schema_version": 1,
        "captured_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_kind": "simulator_model_only",
        "simulator_path": str(simulator_dir.resolve()),
        "simulator_slip_setting": slip,
        "slip_is_physical_calibration": False,
        "sequence": SEQUENCE,
        "repeats": [],
    }
    rows = []
    canonical = EmbodiedNavEnv(seed=42, slip=slip)
    fixed_obstacles = canonical.obstacles.copy()
    start = np.array([1.0, 1.0], dtype=np.float64)
    goal = np.array([9.0, 9.0], dtype=np.float64)
    theta0 = 0.0
    expected_final = np.array([2.0, 1.5])

    for repetition, seed in enumerate(seeds, start=1):
        env = EmbodiedNavEnv(seed=seed, slip=slip)
        env.obstacles = fixed_obstacles.copy()
        env.pos = start.copy()
        env.theta = theta0
        env.odom_pos = start.copy()
        env.odom_theta = theta0
        env.goal = goal.copy()
        env.prev_dist = float(np.linalg.norm(goal - env.pos))
        elapsed = 0.0
        rows.append({"repeat": repetition, "seed": seed, "step": env.step_count,
                     "elapsed_s": elapsed, "stage": "start", "truth_x": env.pos[0],
                     "truth_y": env.pos[1], "truth_yaw_rad": env.theta,
                     "odom_x": env.odom_pos[0], "odom_y": env.odom_pos[1],
                     "odom_yaw_rad": env.odom_theta, "error_xy_m": 0.0,
                     "error_yaw_deg": 0.0, "collided": False})
        run_failed = False
        for segment in SEQUENCE:
            count = round(segment["duration_s"] / env.DT)
            action = np.array([segment["linear_mps"] / env.MAX_LIN_VEL,
                               segment["angular_rps"] / env.MAX_ANG_VEL], dtype=np.float32)
            for _ in range(count):
                _, _, terminated, truncated, info = env.step(action)
                elapsed += env.DT
                error_xy = float(np.linalg.norm(env.pos - env.odom_pos))
                yaw_err = math.degrees(math.atan2(math.sin(env.theta - env.odom_theta),
                                                 math.cos(env.theta - env.odom_theta)))
                rows.append({"repeat": repetition, "seed": seed, "step": env.step_count,
                             "elapsed_s": elapsed, "stage": segment["stage"],
                             "truth_x": float(env.pos[0]), "truth_y": float(env.pos[1]),
                             "truth_yaw_rad": float(env.theta), "odom_x": float(env.odom_pos[0]),
                             "odom_y": float(env.odom_pos[1]), "odom_yaw_rad": float(env.odom_theta),
                             "error_xy_m": error_xy, "error_yaw_deg": yaw_err,
                             "collided": bool(info["collided"])})
                if terminated or truncated:
                    run_failed = True
                    break
            if run_failed:
                break
        final_pos_error = float(np.linalg.norm(env.pos - expected_final))
        final_yaw_error = math.degrees(math.atan2(math.sin(env.theta - math.pi / 2),
                                                  math.cos(env.theta - math.pi / 2)))
        summary["repeats"].append({
            "repeat": repetition, "seed": seed, "status": "simulated_sequence_complete" if not run_failed else "simulated_sequence_interrupted",
            "start_truth_m_rad": [1.0, 1.0, 0.0],
            "expected_final_truth_m_rad": [2.0, 1.5, math.pi / 2],
            "actual_final_truth_m_rad": [float(env.pos[0]), float(env.pos[1]), float(env.theta)],
            "final_position_error_to_ideal_m": final_pos_error,
            "final_yaw_error_to_ideal_deg": final_yaw_error,
            "truth_vs_odom_position_error_m": float(np.linalg.norm(env.pos - env.odom_pos)),
            "truth_vs_odom_yaw_error_deg": math.degrees(math.atan2(math.sin(env.theta - env.odom_theta),
                                                                       math.cos(env.theta - env.odom_theta))),
            "collided_or_terminated": run_failed,
        })
        env.close()
    with trajectory_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary["trajectory_csv"] = str(trajectory_path)
    summary["note"] = "固定起点/路径用于仿真运动学回归；slip来自模型设定，非实车测量。"
    summary_path = output_dir / "week2_sim_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                            encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulator-dir", type=Path,
                        default=Path("/home/yahboom/embodied-sim-lite/embodied-sim-lite"))
    parser.add_argument("--output-dir", type=Path, default=Path("evidence/raw"))
    parser.add_argument("--seeds", type=int, nargs=3, default=[101, 102, 103])
    parser.add_argument("--slip", type=float, default=0.05,
                        help="simulator parameter only; do not treat as measured vehicle slip")
    args = parser.parse_args()
    result = run(args.simulator_dir, args.output_dir, args.seeds, args.slip)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if all(row["status"] == "simulated_sequence_complete" for row in result["repeats"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
