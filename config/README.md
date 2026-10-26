# 配置入口

## 当前实验

- `mapper_sim_improved.yaml`：已实际测试的SLAM改进参数。
- `mapping_route_safe_v2.json`：带净空保护的采图路线。
- `week5_working_threshold_v2.json`：室内公开数据评测后的候选登记阈值。
- `week7_world_frozen_v2.json`：真实模型实验使用的冻结虚拟世界。
- `week8_auditor_world_bound_v2.json`：绑定标签/坐标的审计输入。
- `week8_execution_semantic_v2.json`：仿真执行的目标朝向等参数。

## 可复核材料

`*_preregister.json`保留各轮实验的预注册；早期冻结输入保留原名与原内容，供哈希和版本核对。`lesson8_fixture.json`、`semantic_map_fixture.json`只供离线测试，不是课程实测。

`model.local.json`是私有本机配置，权限保持600，已被Git忽略；文件整理没有读取或修改密钥。

当前局部导航默认协议为`week34_safe_return_precise_v4.json`，实际参数以每次运行的`params_snapshot.yaml`为准。旧v1/v2/v3协议与失败结果保留。精细版继承字段说明见`week34_precise_protocol_clarification.json`。同帧双杯协议为`week6_dense_frame_protocol_v2.json`，运行时登记函数为`register_frame`。
