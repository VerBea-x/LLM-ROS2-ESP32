# 脚本入口

| 操作 | 脚本 |
|---|---|
| 重建ROS包 | `build_ros.sh` |
| 启动改进SLAM仿真 | `run_slam_improved.sh` |
| 采集带保护的路线 | `run_mapping_route.py --route-file config/mapping_route_safe_v2.json --output 新运行目录/mapping_route.json` |
| 查看/采集仿真话题与TF | `collect_sim_evidence.py` |
| 公开室内图片检测 | `run_public_detection.py --run-tag 新实验名` |
| 生成逐图框与阈值曲线 | `render_public_detection.py --run-tag 新实验名` |
| 导出当前SLAM对照 | `render_slam_improvement.py` |
| 复算已有模型统计 | `summarize_evidence.py` |
| 受控ROS合成语义地图 | `run_week6_lab.sh`（新目录、域50） |
| 第6→8周观测回归 | `check_week6_auditor_bridge.py`（无API） |
| V3任务完整性回归 | `replay_task_contracts.py`（复用40回答） |
| SLAM图AMCL两轮导航 | `run_slam_map_validation.sh`（新编号、域47） |
| V3地图仿真执行和录像 | `run_v3_slam_validation.sh`（冻结真实模型计划，无新API） |
| SLAM图导航复算 | `summarize_slam_map_validation.py` |
| V3媒体与costmap复核 | `finalize_v3_slam_evidence.py` |
| 第3周原始表复算与点图 | `export_localization_evidence.py`（无新增采样） |
| 多站位/同名/乱序压力检查 | `run_semantic_stress.py --output 新路径.json`（离线合成） |
| 命名点地图迁移核对 | `check_waypoint_map_migration.py`（仅查图） |
| 当前证据与文档检查 | `check_project_evidence.py` |
| 本地设置API | `configure_deepseek.py` |
| 只读检查ESP32话题 | `probe_esp32_readonly.py` |

数据下载和选图脚本读取 `data/annotations/`；已有冻结数据会拒绝覆盖。重做采集须使用新结果路径。ROS启动和实验域约定见 `docs/rebuild_procedure.md`。

`organize_project.py`是本次一次性整理脚本，已经执行，拒绝重复覆盖清理记录。退役的通用选图/终端配置脚本在 `../archive/legacy_scripts/`，当前不用它们作为运行入口。

新版安全返回路线：`COURSE_PROTOCOL="$PWD/config/week34_safe_return_precise_v4.json" bash scripts/run_slam_map_validation.sh`。双杯同帧实验：`COURSE_SEMANTIC_LAB=run_dense_semantic_ros_lab.py bash scripts/run_week6_lab.sh 新目录`。原实验不覆盖。`summarize_failed_item_fixes.py`复算四版结果，`render_dense_registration_fix.py`对照旧算法离线回放与新实际ROS合成结果。
