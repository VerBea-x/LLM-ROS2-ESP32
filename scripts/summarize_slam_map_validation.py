#!/usr/bin/env python3
"""Recompute the two-round SLAM-map AMCL/Nav2 experiment without ROS/API."""
import hashlib,json,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
base=ROOT/'evidence/raw/week34_slam_map/20261026_slam_amcl_v1'
rounds=[json.loads((base/f'round{i}/trials.json').read_text()) for i in [1,2]]
rows=[{'round':r['round'],**t} for r in rounds for t in r['trials']]
success=[r for r in rows if r['result']=='SUCCEEDED'];passed=[r for r in rows if r['passed']]
report={'source_kind':'actual_AMCL_Nav2_on_frozen_SLAM_map','rounds':2,'trials':rows,
 'service_successes':len(success),'truth_tolerance_passes':len(passed),'total':len(rows),
 'initial_gates_passed':all(r['initial_gate']['passed'] for r in rounds),
 'success_endpoint_errors_m':[r['truth_goal_error_m'] for r in success],
 'success_mean_error_m':statistics.mean(r['truth_goal_error_m'] for r in success),
 'course_full_gate_passed':len(rows)==6 and len(passed)==6,
 'sources_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [base/'protocol.json',base/'params_snapshot.yaml',*[base/f'round{i}/trials.json' for i in [1,2]],ROOT/'outputs/slam_improvement/map_slam.pgm',ROOT/'outputs/slam_improvement/map_slam.yaml']},
 'limitations':['Local route, truth-assisted initial pose only; no truth TF supplied to AMCL.',
 'Round starts reset; seed/configuration identical, not independent scenes or randomized AMCL trials.',
 '720 simulated rays +60 AMCL beams; previous24-ray known-map experiment is not a matched causal baseline.',
 'Rejected goals never dispatched; distance from stopped robot to rejected target is not a navigation accuracy measurement.',
 'Post-response stationary flag is a single fresh odom sample; not continuous braking validation.']}
(ROOT/'evidence/reports/week34_slam_map_validation_v1.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
lines=['# SLAM地图上的AMCL与导航复核','',
'结论：两次重启的局部路线中，4/6同时满足服务成功与30cm真值终点标准；另2次目标被代价地图拒绝，未派发导航。整体6/6验收未通过。',
'', '[冻结协议](../../config/week34_slam_map_validation_v1.json) · [原始两轮记录](../raw/week34_slam_map/20261026_slam_amcl_v1/) · [复算JSON](week34_slam_map_validation_v1.json)','',
'使用实际SLAM地图，不再用真值图替代。每轮重启模拟器与AMCL，起点相同；只用真值设置一次初始位姿，之后map→odom由AMCL估计。模拟器seed42、slip0.05、720束，AMCL max_beams=60，其他导航参数保留。',
'', '两轮初始化门都通过，末三个新鲜静态更新误差约9.1–9.8cm。不同时间戳保证非缓存重复，但静态更新相关，不能当多个独立样本。',
'', '| 轮次 | 目标 | 服务结果 | 已执行成功的终点误差 | 耗时 |', '|---|---|---|---:|---:|']
for r in rows:
 error=f"{r['truth_goal_error_m']*100:.1f}cm" if r['result']=='SUCCEEDED' else '未派发，不计到点精度'
 lines.append(f"| {r['round']} | {r['id']} {r['pose'][:2]} | {r['result']} | {error} | {r['elapsed_s']:.2f}s |")
lines += ['', '被拒绝的目标均为(8,5.5)，服务明确返回cost=99、要求<50。不能把它解释为AMCL误差2m；当时机器人停在上一目标，压根没有导航到该点。代价地图包含膨胀层，原始SLAM像素为空闲也不代表车体可安全到达。',
'', '旧24束/已知地图实验仅2/6达到真值标准；本次4/6来自地图、扫描束数、AMCL采样和重启起点的联合变化，不据此声称某个单一参数使成功率翻倍。两次重启结果也不等于跨场景统计可靠性。',
'', '下一步保持原失败记录，检查被拒目标附近的SLAM轮廓与代价膨胀配置，重新确定命名点应代表的可达位置。若修改目标或膨胀参数，应另开协议，不能覆盖这次结果。未验证搬运恢复、全场定位、动态障碍或真实车辆。']
(ROOT/'evidence/reports/SLAM地图定位导航复核.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({'service_successes':len(success),'endpoint_passes':len(passed),'total':len(rows),'full_gate':report['course_full_gate_passed']}))
