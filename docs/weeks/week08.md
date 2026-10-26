# 第8周：审计器、状态机与证据闭环

状态：四规则独立正反8/8、6条回归、12格冻结输出对照和一次真实模型仿真执行已有证据；课程完整验收仍受地图、真实观测τ及完整对照过程录屏缺项限制。

[规则溯源](../rules_traceability.csv)、[八用例](../../evidence/reports/week8_actual_map_eight_cases.json)、[12格](../../evidence/raw/week8_trap_paired_12cells_20261026.csv)。白名单先于四规则；全案审计通过才执行。事件为plan/audit/exec/report，失败最多两次重规划，汇报包含结果/证据/局限。

6条陷阱这次全部被模型自行拒绝/追问或只产生say/stop，未复现危险导航，不能宣传审计“拦截6次”。关闭审计只干跑，没有接电机。完整采样与对照过程录像缺项不能用事后动画补成原始录像。

[原始真实模型仿真录像](../../outputs/week8/real_model_live_sim.mp4)及[运行记录](../../evidence/raw/week8_integration/20261026T021310Z/)保留。一次导航7.15秒、真值终点误差24.8cm、重规划0次、fresh odom确认停车；使用真值定位/slip0/人工点/模拟电量，仅证明当时版本链路。播放器问题已由用户解决。

本次新增V3执行前任务契约：[配置](../../config/task_contracts_v3.json)、[40回答回归](../../evidence/reports/week8_task_contract_replay_v3.json)。除了工具逐条合法，还要求整条指令步骤、目标顺序和能力可用。25拒绝=20条无相机观察任务+5条不完整门口路线，15完整路线仅干跑通过；拒绝项执行次数为0。单独stop仍可执行，结果STOPPED，不能冒充原任务COMPLETED。异常规划输出被记录为拒绝/规划失败。

V3仅支持配置内精确指令；未登记指令拒绝，不擅自补全或同义改写。`agent_ros_node --execute-sim`现在要求`--task-contracts config/task_contracts_v3.json`；历史录像V2未重录，不能当作V3真执行。旧四规则与原实验判据不变，完整性检查是新增执行门。

新增[第6周观测桥接](../../evidence/reports/week6_to_week8_auditor_bridge.json)6/6改善R2数据溯源，仍属于合成观测的离线回归，未替换旧40采样的冻结世界。后续优先项：当前SLAM地图下全路线稳定性；多任务/失效的V3验证；条件具备后测真实τ与车载链路。尚无摄像头时“观察现场物品”必须明确拒绝或改为事先声明的模拟任务。

## 新增V3仿真执行

已单开版本在实际SLAM地图和AMCL上完成一次V3执行：6项检查通过，真值终点误差6.65cm，重规划0次，停车连续核验。使用冻结真实模型回答，无新API调用；19.6秒实时可视化录像完整解码通过。[新报告](../../evidence/reports/第8周_V3地图仿真执行.md)、[新录像](../../outputs/week8/v3_slam_live_sim.mp4)。旧V2仍为历史版本，原40回答及12格未改。
