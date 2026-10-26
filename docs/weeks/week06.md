# 第6周：无摄像头条件下的受控语义地图

状态：受控ROS合成检测验证完成；真实站位回放、相机标定和场地移动规律仍未验证。课件P10/P14允许孪生det_inject检验几何，这部分不需要摄像头。合成实验不替代课件其余公共站位/现场误差要求。

输入冻结于[实验协议](../../config/week6_controlled_lab_protocol.json)，原始证据在[ROS实验v3](../../evidence/raw/week6_ros_lab_v3/lab_result.json)。域50独立于导航域；没有发布运动命令。

`/detections` Detection2DArray + `/camera_info` CameraInfo + map→base_footprint TF → semantic_mapper → `/semantic_map` JSON和`/semantic_markers` MarkerArray。

虚拟相机640×480、fx=320、cx=320，光轴与底盘前向对齐，站位(2,3,0)。这些是声明的模拟参数，不是标定结果。方位β=atan2(cx-u,fx)，固定距离r=1m，x=xb+r·cos(yaw+β)，y=yb+r·sin(yaw+β)。不能从单张图片测得真实深度。

10项实跑检查全通过：正前方≤5cm、左侧y增大、右侧y减小、同杯两次合并、0.4置信度不登记、错误分辨率拒绝、旧检测时间戳拒绝、停止观测后fresh→stale、Marker数量相同、位置相同。阈值沿用第5周0.5；bottle/cup/backpack注入验证接口，其中backpack没有第5周检测精度证据。

[误差分解](../../evidence/reports/week6_controlled_error_components.json)：真实距离0.8m/2.5m而固定估1m时，径向误差+0.2m/-1.5m；5像素偏置导致约1.56cm切向误差。这是已知虚拟几何的计算，不是现场量尺结果，不能当作A/B/C实测残差。

[合成移动日志](../../evidence/raw/week6_controlled_mobility.json)按seed601生成600逻辑秒，使用前300秒最小移动间隔的一半推导τ：person1.5s、手持物4s、家具15s。不是实际观察600秒，也没有证明真实物体满足此上界；后300秒未用于选τ，尚未形成外部验证。课堂场地τ仍待实测。

[第6→8周桥接回归](../../evidence/reports/week6_to_week8_auditor_bridge.json)：3目标新鲜允许、同一记录自然过期后R2拒绝，共6/6。属于离线读取实际ROS合成登记记录，不是持续运行的视觉导航闭环；查图仍用既有已知地图快照。

复现见[一键受控实验](../../scripts/run_week6_lab.sh)。v1/v2因重复节点未通过唯一订阅检查而中止，保留RUN_STATUS；v3是当前有效结果。上述v3历史节点使用类别+距离逐条合并；当前运行时已改为整帧一对一关联，同帧约0.6m双杯已重测通过。跨时出现、遮挡、交叉和实景鲁棒性仍未验证。

新增对齐材料见[详细报告](../../evidence/reports/第6周_多站位与登记边界.md)，保留原始数据及未通过边界。

## 同帧近距离同类目标修复

运行时现使用register_frame整帧一对一关联，同帧新目标不互相合并，输出唯一target_name；歧义关联拒绝整帧。约0.6m双杯ROS9/9，原ROS回归10/10通过。[最新报告](../../evidence/reports/未通过项修复与重测.md)。旧逐条算法负例留作历史，分时出现、遮挡和交叉仍未验证。
