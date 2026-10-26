#!/usr/bin/env python3
"""Check current evidence paths, document links and recorded regression claims."""
import csv,hashlib,json,re
from pathlib import Path
from urllib.parse import unquote
ROOT=Path(__file__).resolve().parents[1]

def main():
    problems=[];files=set();references=[]
    for name,column in [('evidence/progress.csv','evidence_path'),('docs/rules_traceability.csv','evidence_path')]:
        for row in csv.DictReader((ROOT/name).open()):
            for value in row[column].split(';'):
                value=value.strip()
                if not value:continue
                target=ROOT/value;references.append({'table':name,'path':value,'exists':target.exists()})
                if not target.exists():problems.append(f'{name}: {value}')
                elif target.is_file():files.add(target)
    documents=[ROOT/'README.md',ROOT/'验收进度与结果.md',*sorted((ROOT/'docs').glob('*.md')),
               *sorted((ROOT/'docs/weeks').glob('*.md')),
               ROOT/'evidence/reports/第6周_受控语义地图验证.md',ROOT/'evidence/reports/第8周_计划完整性修订.md',
               ROOT/'evidence/reports/第8周_V3地图仿真执行.md',ROOT/'evidence/reports/SLAM地图定位导航复核.md',ROOT/'evidence/reports/第3周_定位不可信点与统计.md',
               ROOT/'evidence/reports/第6周_多站位与登记边界.md',ROOT/'evidence/reports/命名点地图迁移核对.md',ROOT/'evidence/reports/未通过项修复与重测.md']
    # The cleanup log is historical and deliberately mentions retired assets.
    documents=[d for d in documents if d.name!='文件整理记录_20261026.md']
    for doc in documents:
        if not doc.exists():problems.append(str(doc.relative_to(ROOT)));continue
        files.add(doc)
        for link in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',doc.read_text()):
            link=unquote(link.strip('<>').split('#')[0])
            if not link or re.match(r'^[a-z]+://',link):continue
            target=doc.parent/link
            if not target.exists():problems.append(f'{doc.relative_to(ROOT)}: {link}')
    lab=json.loads((ROOT/'evidence/raw/week6_ros_lab_v3/lab_result.json').read_text())
    bridge=json.loads((ROOT/'evidence/reports/week6_to_week8_auditor_bridge.json').read_text())
    replay=json.loads((ROOT/'evidence/reports/week8_task_contract_replay_v3.json').read_text())
    checks={'week6_ros_10_checks':len(lab['checks'])==10 and all(lab['checks'].values()),
            'week6_auditor_6_checks':len(bridge['checks'])==6 and bridge['all_checks_passed'],
            'original40_replayed':len(replay['rows'])==40,
            'rejected_plans_never_executed':all(r['executed_dry_run_calls']==0 for r in replay['rows'] if r['result']=='REJECTED'),
            'api_key_file_private':(ROOT/'config/model.local.json').stat().st_mode&0o777==0o600}
    v3dir=ROOT/'evidence/raw/week8_v3_slam/20261026_frozen_plan_v2/agent'
    trace=json.loads((v3dir/'execution_trace.json').read_text())
    media=json.loads((v3dir/'media_validation.json').read_text())
    nav=json.loads((ROOT/'evidence/reports/week34_slam_map_validation_v1.json').read_text())
    boundary=json.loads((ROOT/'evidence/reports/week34_costmap_boundary_check.json').read_text())
    checks.update(v3_live_sim_checks=all(trace['checks'].values()),
      v3_video_verified=media['full_decode_exit_code']==0 and hashlib.sha256((ROOT/'outputs/week8/v3_slam_live_sim.mp4').read_bytes()).hexdigest()==media['sha256'],
      two_rounds_six_trials_preserved=nav['rounds']==2 and nav['total']==6 and nav['truth_tolerance_passes']==4 and not nav['course_full_gate_passed'],
      map_costmap_boundary_checked=boundary['all_checks_passed'])
    stress=json.loads((ROOT/'evidence/raw/week6_stress_v1.json').read_text())
    lab2=json.loads((ROOT/'evidence/raw/week6_ros_after_clock_guard_v1/lab_result.json').read_text())
    strict=json.loads((ROOT/'evidence/reports/week6_to_week8_strict_bridge_v2.json').read_text())
    points=json.loads((ROOT/'evidence/reports/week3_evidence_linked_points.json').read_text())
    checks.update(semantic_stress_expected_checks=stress['all_checks_passed'],
      historical_dense_failure_preserved=stress['known_limitations']['near_same_class_objects_still_merge'],
      modified_mapper_ROS_regression=lab2['all_checks_passed'],strict_semantic_bridge=strict['all_checks_passed'],
      original_localization_points_traced=len(points['rows'])==10 and points['source_sha256']==hashlib.sha256((ROOT/'evidence/raw/week3_localization_selected.csv').read_bytes()).hexdigest())
    fixes=json.loads((ROOT/'evidence/reports/failed_items_remediation_20261026.json').read_text())
    dense=json.loads((ROOT/'evidence/raw/week6_dense_frame_v2/lab_result.json').read_text())
    regression=json.loads((ROOT/'evidence/raw/week6_frame_v2_regression/lab_result.json').read_text())
    bridge_dense=json.loads((ROOT/'evidence/reports/week6_dense_frame_v2_auditor_bridge.json').read_text())
    bridge_reg=json.loads((ROOT/'evidence/reports/week6_frame_v2_regression_bridge.json').read_text())
    checks.update(new_safe_route_six_truth_passes=fixes['new_navigation_local_gate_passed'],
      all_four_navigation_versions_preserved=len(fixes['navigation_versions'])==4,
      simultaneous_dense_pair_nine_checks=len(dense['checks'])==9 and dense['all_checks_passed'],
      frame_registration_legacy_ROS_regression=regression['all_checks_passed'],
      frame_registration_auditor_bridges=bridge_dense['all_checks_passed'] and bridge_reg['all_checks_passed'])
    # Hash explicitly referenced artifacts, never read or fingerprint secret configuration.
    for name in ['config/task_contracts_v3.json','config/week6_controlled_lab_protocol.json',
                 'config/week6_controlled_tau_rules.json','src/course_audit/task_contract.py',
                 'src/course_audit/state_machine.py','src/course_audit/agent_ros_node.py',
                 'scripts/semantic_mapper_node.py','scripts/run_week6_ros_lab.py','scripts/run_week6_lab.sh',
                 'scripts/run_v3_slam_validation.sh','scripts/run_slam_map_validation.sh',
                 'scripts/run_slam_map_benchmark.py','scripts/prepare_v3_slam_integration.py',
                 'scripts/record_v3_slam_integration.py','scripts/finalize_v3_slam_evidence.py',
                 'config/week34_slam_map_validation_v1.json','evidence/reports/week34_costmap_boundary_check.json',
                 'evidence/raw/continuation_tests_20261026.log','evidence/raw/alignment_tests_20261026.log',
                 'src/course_audit/semantic_registration.py','src/course_audit/semantic_world.py',
                 'scripts/check_week6_auditor_bridge.py','config/week6_stress_protocol_v1.json',
                 'scripts/run_semantic_stress.py','scripts/export_localization_evidence.py',
                 'evidence/reports/week7_to_slam_waypoint_migration.json','config/week34_safe_return_v2.json',
                 'config/week34_safe_return_precise_v3.json','config/week34_safe_return_precise_v4.json',
                 'config/week34_precise_protocol_clarification.json','config/week6_dense_frame_protocol_v2.json',
                 'scripts/run_dense_semantic_ros_lab.py','scripts/summarize_failed_item_fixes.py',
                 'scripts/render_dense_registration_fix.py','scripts/run_week6_lab.sh',
                 'tests/test_frame_registration.py','evidence/raw/failed_items_fix_tests_20261026.log']:
        files.add(ROOT/name)
    report={'scope':'Current document/evidence consistency; not course acceptance certification.',
      'references':references,'checks':checks,'problems':problems,
      'all_checks_passed':not problems and all(checks.values()),
      'sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}}
    (ROOT/'evidence/reports/project_evidence_check_20261026.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'all_checks_passed':report['all_checks_passed'],'files_hashed':len(files),
                      'problems':problems,'checks':checks},ensure_ascii=False))
    return 0 if report['all_checks_passed'] else 1
if __name__=='__main__':raise SystemExit(main())
