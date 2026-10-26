# 第1–8周课程重做项目

主要环境：Ubuntu虚拟机、ROS2 Humble、Embodied-SimLite、无摄像头的ESP32小车。当前使用20张公开室内场景进行离线视觉评测。

## 从这里查看

| 内容 | 入口 |
|---|---|
| 最新未通过项修复 | [四版导航与同帧双杯重测](evidence/reports/未通过项修复与重测.md) |
| 逐周目标、交付与待补项 | [前八周交付清单](docs/前八周交付清单.md) |
| 多站位与目标歧义 | [第6周边界报告](evidence/reports/第6周_多站位与登记边界.md) |
| 定位不可信点与统计 | [第3周证据表](evidence/reports/第3周_定位不可信点与统计.md) |
| 无摄像头语义地图实验 | [第6周报告](evidence/reports/第6周_受控语义地图验证.md) |
| 执行前计划完整性 | [第8周修订](evidence/reports/第8周_计划完整性修订.md) |
| 各周进度与实际结果 | [验收进度与结果](验收进度与结果.md) |
| 当前20张室内图片 | [图片目录](data/coco_indoor20_v2/images/) · [选图总览](data/coco_indoor20_v2/scene_contact_sheet.jpg) |
| 第5周三阈值评测 | [室内公开场景评测](evidence/reports/第5周_室内公开场景评测.md) |
| 改进后的SLAM地图 | [地图对照](outputs/slam_improvement/map_comparison.png) · [地图文件](outputs/slam_improvement/map_slam.yaml) |
| SLAM改进与局限 | [实验记录](evidence/reports/SLAM质量改进记录.md) |
| 第8周新增SLAM图+AMCL执行 | [V3报告](evidence/reports/第8周_V3地图仿真执行.md) · [V3新录像](outputs/week8/v3_slam_live_sim.mp4) |
| 第8周原始录像 | [real_model_live_sim.mp4](outputs/week8/real_model_live_sim.mp4) |
| 实车待验证项目 | [ESP32现场流程](docs/ESP32实车验证.md) |

## 目录

| 目录 | 用途 |
|---|---|
| `data/` | 当前室内数据集、共享COCO标注、数据来源 |
| `models/` | 已实际评测的ONNX检测模型 |
| `outputs/` | 便于查看的图片、地图、原始MP4入口 |
| `evidence/raw/` | 原始采样、模型回答、轨迹、ROS包和运行日志 |
| `evidence/reports/` | 当前统计、图表和实验结论 |
| `config/` | 改进配置、冻结实验协议、测试夹具和本机私有模型配置 |
| `scripts/` | 启动、采集、评测及导出脚本，见[脚本入口](scripts/README.md) |
| `src/course_audit/` | 工具契约、审计器、状态机及模型/ROS适配器 |
| `ros2_ws/src/` | ROS服务包源代码；构建产物可重新生成 |
| `tests/` | 针对性回归测试 |
| `archive/` | 旧选图协议、历史探索报告和退役脚本 |

## 常用操作

在本项目目录执行：

```bash
bash scripts/build_ros.sh
bash scripts/run_slam_improved.sh
```

重做离线检测时指定新的结果名，已有实验不会覆盖：

```bash
python3 scripts/run_public_detection.py --run-tag week5_indoor_newrun
python3 scripts/render_public_detection.py --run-tag week5_indoor_newrun
```

受控语义地图：`bash scripts/run_week6_lab.sh`（只运行合成检测，无电机命令）。离线复核：`python3 scripts/check_week6_auditor_bridge.py`、`python3 scripts/replay_task_contracts.py`、`python3 scripts/check_project_evidence.py`。

上述检测默认使用当前室内数据集。不要再次调用API来重算已有统计；原始40次回答已经保存。

## 当前边界

SLAM质量已经改善，但最终定位误差仍约36.8cm，尚未全部验收通过。公开图片结果属于离线替代实验，小车没有摄像头；仿真雷达和真值定位均不能作为实车证据。`/home/yahboom/results`仍为只读历史材料。

密钥保留于本机私有配置中，不写入报告或聊天。文件整理说明见 [清理记录](docs/文件整理记录_20261026.md)。

当前局部导航验证入口：`bash scripts/run_slam_map_validation.sh`，默认使用已修复的安全返回路线和精细配置；原路线可用`COURSE_PROTOCOL`明确指定旧协议复现。双杯整帧登记实验见最新修复报告。
