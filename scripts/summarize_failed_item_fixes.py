#!/usr/bin/env python3
"""Summarize all new runs, retaining both failed baselines and scope changes."""
import hashlib,json,yaml
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
runs=['20261026_slam_amcl_v1','20261026_safe_return_v2','20261026_safe_return_precise_v3','20261026_safe_return_precise_v4'];versions=[]
for run in runs:
 base=ROOT/'evidence/raw/week34_slam_map'/run
 rounds=[json.loads((base/f'round{i}/trials.json').read_text()) for i in [1,2]]
 rows=[{'round':r['round'],**t} for r in rounds for t in r['trials']]
 if len(rows)!=6:raise SystemExit(f'{run} not finished, refuse summary')
 versions.append({'run':run,'protocol':rounds[0]['protocol'],'effective_parameters':yaml.safe_load((base/'params_snapshot.yaml').read_text()),'rows':rows,'service_successes':sum(r['result']=='SUCCEEDED' for r in rows),
  'truth_gate_passes':sum(r['passed'] for r in rows),'full_gate_passed':all(r['passed'] for r in rows),
  'max_error_on_success_m':max(r['truth_goal_error_m'] for r in rows if r['result']=='SUCCEEDED'),
  'sources_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [base/'protocol.json',base/'params_snapshot.yaml',*[base/f'round{i}/trials.json' for i in [1,2]]]}})
densepath=ROOT/'evidence/raw/week6_dense_frame_v2/lab_result.json';dense=json.loads(densepath.read_text())
report={'source_kind':'actual_ROS_simulation_failed_item_remediation','navigation_versions':versions,
 'dense_registration_source':str(densepath.relative_to(ROOT)),'dense_registration_checks':dense['checks'],
 'new_navigation_local_gate_passed':versions[-1]['full_gate_passed'],
 'simultaneous_dense_pair_gate_passed':dense['all_checks_passed'],
 'limitations':['Old target rejected on currentSLAMcostmap retained as negative case; new route returns to preexisting W8_home.',
 'Same SLAM map, new navigation speed/goal/update configuration; no single-factor causal claim.',
 'Dense fix applies to jointly observed same-frame objects. Staggered arrivals, occlusion, crossing and real-camera identity tracking remain unverified.',
 'No new model requests, no physical vehicle execution, no full-field or kidnapping recovery claim.']}
(ROOT/'evidence/reports/failed_items_remediation_20261026.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
lines=['# 未通过项修复与重测','',
'本轮处理导航到点失败和近距离同类误合并。原始失败版本保留，当前结果按新冻结协议独立判断。',
'', '| 导航版本 | 第三个目标 | 服务成功 | 真值≤30cm | 结论 |','|---|---|---:|---:|---|']
for v in versions:
 lines.append(f"| {v['protocol']['version']} | {v['protocol']['goals'][2]['pose'][:2]} | {v['service_successes']}/6 | {v['truth_gate_passes']}/6 | {'本地路线门通过' if v['full_gate_passed'] else '未通过'} |")
lines+=['', '第一版(8,5.5)在SLAM图上不足以放入完整车体，costmap拒绝是正确边界。第二版明确返回此前冻结的W8_home，服务6/6成功，但实际到点仍超30cm。第三版保留这条安全路线，将速度上限降到0.35m/s、估计到点容差收紧到0.08m、AMCL更新门槛降到0.05m/0.05rad并用90beams，结果仍为5/6。第四版只把估计xy到点容差从8cm再收紧到2cm。地图与障碍拒绝阈值未放宽，30cm真值标准未改。',
'',
'', '## 最新两轮逐项结果','', '| 轮 | 目标 | 服务耗时s | 真值终点误差cm | 30cm门 |','|---|---|---:|---:|---|']
for r in versions[-1]['rows']:lines.append(f"| {r['round']} | {r['id']} | {r['elapsed_s']:.2f} | {r['truth_goal_error_m']*100:.2f} | {'通过' if r['passed'] else '未通过'} |")
lines+=['', '返回点接近30cm门限时必须保留余量不足的局限；两次同种子重启不等于跨环境可靠性。原版4/6未被回填，换返回点后的6次结果也不能证明旧不安全点可达。',
'', '## 同类误合并修复','',
'运行时改用整帧关联：一帧所有检测只与帧前地图作一对一匹配，同帧新目标之间不再相互合并；每个目标有独立target_name。重复观测保留名称，候选间差距≤0.15m或多个检测竞争一个旧目标时拒绝整帧，原地图不改。没有使用模拟真值身份代替关联。',
'', '[双杯ROS实验](../raw/week6_dense_frame_v2/lab_result.json)：约0.6m间距双杯独立建档、重复计数、歧义拒绝、名称保留、两个Marker和过期，共9项检查全部通过。[双杯审计桥接](week6_dense_frame_v2_auditor_bridge.json)新鲜/过期4/4；[原10项ROS回归](../raw/week6_frame_v2_regression/lab_result.json)10/10，回归审计6/6。',
'', '该修复解决同帧双目标误合并，不是通用跟踪：分时出现的新物体、遮挡后重现、交叉和错误检测仍需独立验证。旧register()只留作历史逐条算法对照，当前ROS节点使用register_frame()。旧stress_v1中的0.6m失败是历史基线，不再代表新版同帧能力。',
'', '协议说明：精细版parameter_overrides声明90beams并实际生效，继承的顶层60beams描述未同步，已用[独立说明](../../config/week34_precise_protocol_clarification.json)澄清，未回改冻结协议。参数以原始params_snapshot.yaml为准。',
'', '38项软件测试通过，见[测试日志](../raw/failed_items_fix_tests_20261026.log)。本轮没有新API请求或实车动作。',
'', '[四版本复算数据](failed_items_remediation_20261026.json) · [新导航原始运行](../raw/week34_slam_map/20261026_safe_return_precise_v4/) · [新协议](../../config/week34_safe_return_precise_v4.json)。全场定位、搬运恢复、真实相机/雷达/车辆及完整陷阱采样录屏仍未因此通过。']
(ROOT/'evidence/reports/未通过项修复与重测.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({'navigation_local_gate':report['new_navigation_local_gate_passed'],'dense_pair_gate':report['simultaneous_dense_pair_gate_passed'],'max_error_m':versions[-1]['max_error_on_success_m']}))
