# 证据与结果

- `progress.csv`：每周验收门及证据来源。
- `raw/`：原始事实。模型回答、冻结协议、失败与网络恢复记录、轨迹和地图均保留。
- `reports/`：当前结论和可复算统计；它们不能代替原始数据。

当前安全路线原始ROS包仍在 `raw/week3_slam/20261026T030832Z/rosbag/`，可直接用ROS工具读取。

历史旧路线的大包压缩为 `raw/week3_slam/20261026T025521Z/rosbag.tar.gz`。归档前后所有成员SHA256相同；需要重放时在同目录解压恢复 `rosbag/`。

早期探索报告移至 `../archive/exploration_reports/`。第8周原始MP4仍保存在原始运行目录，`../outputs/week8/`提供同一文件的常用入口。
