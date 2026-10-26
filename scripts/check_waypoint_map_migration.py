#!/usr/bin/env python3
"""Spatial compatibility audit only: original frozen names versus actual SLAM costmap."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from course_audit.plan_auditor import OccupancyGridSnapshot
source=ROOT/'config/week7_world_frozen_v2.json';base=ROOT/'evidence/raw/week8_v3_slam/20261026_frozen_plan_v2/initialization'
paths=[source,base/'map_snapshot.json',base/'costmap_snapshot.json']
world=json.loads(source.read_text());raw=OccupancyGridSnapshot.from_mapping(json.loads(paths[1].read_text()));cost=OccupancyGridSnapshot.from_mapping(json.loads(paths[2].read_text()));rows=[]
for item in world['semantic_map']:
 x,y=item['x'],item['y'];rv=raw.cell_value(x,y);cv=cost.cell_value(x,y)
 rows.append({'label':item['label'],'name':item['name'],'position':[x,y],
 'original_declared_cost':item.get('cost_at_registration'),'SLAM_occupancy':rv,'Nav2_cost':cv,
 'spatial_candidate':rv is not None and cv is not None and 0<=rv<50 and 0<=cv<50})
report={'source_kind':'offline_map_migration_check_of_declared_virtual_landmarks','rows':rows,
 'candidate_count':sum(r['spatial_candidate'] for r in rows),'total':len(rows),
 'sources_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
 'limits':['Static snapshot spatial admissibility, not path reachability, localization confidence, freshness or successful navigation.',
 'Original frozen model world unchanged; no automatic landmark relocation or relabeling.',
 'Known virtual landmarks are not camera observations. Execution still requires live costmap recheck.']}
(ROOT/'evidence/reports/week7_to_slam_waypoint_migration.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
lines=['# 冻结命名点迁移到SLAM地图的检查','',
'检查旧第7周命名点在本次实际SLAM图和Nav2代价地图中的空间兼容性，不移动目标，不改原模型世界。',
'', '| 命名点 | 坐标 | 原声明cost | SLAM占据值 | Nav2代价值 | 空间候选 |', '|---|---|---:|---:|---:|---|']
for r in rows:lines.append(f"| {r['label']} {r['name']} | {r['position']} | {r['original_declared_cost']} | {r['SLAM_occupancy']} | {r['Nav2_cost']} | {'是' if r['spatial_candidate'] else '否，需复核'} |")
lines+=['',f"共{report['candidate_count']}/{len(rows)}个点在这份快照中符合点栅格空闲条件。该数字不是导航成功率，也不代表新鲜度、定位可信度或路径可达已通过。",'',
'本轮导航失败的(8,5.5)是重复路线的return目标，不是默认W8_home坐标；不能把二者混写或暗中互换。改名/移点须有新协议，旧4/6结果仍保留。',
'', '[原始点位核对JSON](week7_to_slam_waypoint_migration.json)。没有发送导航命令，没有新API请求。']
(ROOT/'evidence/reports/命名点地图迁移核对.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({'candidate_count':report['candidate_count'],'total':len(rows),'blocked':[r['label'] for r in rows if not r['spatial_candidate']]}))
