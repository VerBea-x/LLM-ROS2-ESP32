#!/usr/bin/env python3
"""Explicit cleanup whitelist; keep raw evidence and verify compressed history."""
import argparse
import hashlib
import json
import os
import shutil
import tarfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def files(path):return sorted(p for p in path.rglob('*') if p.is_file() and not p.is_symlink()) if path.is_dir() else [path] if path.is_file() else []
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    previous=ROOT/'docs/cleanup_inventory_20261026.json'
    if previous.exists() and json.loads(previous.read_text()).get('protected_assets_verified'):
        raise SystemExit('这次整理已经完成，请查看docs/cleanup_inventory_20261026.json；不重复删除或覆盖清理记录。')
    before=sum(p.stat().st_size for p in files(ROOT))
    # A held experiment lock means transient files must not be cleaned.
    import fcntl
    for lock in (ROOT/'run').glob('*.lock'):
        with lock.open('a') as f:
            fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
    moves={
      'data/coco_public20/instances_val2017.json':'data/annotations/instances_val2017.json',
      'data/coco_public20/annotation_source.json':'data/annotations/annotation_source.json',
      'data/coco_public20/dataset.json':'archive/vision_v1/dataset.json',
      'data/coco_public20/selection_frozen.json':'archive/vision_v1/selection_frozen.json',
      'data/coco_indoor20_v2/candidate_protocol.json':'archive/indoor_selection/candidate_protocol.json',
      'data/coco_indoor20_v2/candidate_sheet_1.jpg':'archive/indoor_selection/candidate_sheet_1.jpg',
      'data/coco_indoor20_v2/candidate_sheet_2.jpg':'archive/indoor_selection/candidate_sheet_2.jpg',
      'scripts/prepare_coco_public20.py':'archive/legacy_scripts/prepare_coco_public20.py',
      'scripts/configure_model_session.sh':'archive/legacy_scripts/configure_model_session.sh',
    }
    for name in ['week3_360ray_ideal_map_metrics.json','week3_360ray_noisy_map_metrics.json',
      'week3_360ray_slip005_map_metrics.json','week3_conservative_matching_360_metrics.json',
      'week3_no_return_fix_360_metrics.json','week5_public20_metrics.json','week5_public20_summary.json']:
        moves['evidence/reports/'+name]='archive/exploration_reports/'+name
    delete_dirs=['outputs/week5_public20','outputs/videos','data/coco_public20/images',
                 'data/coco_indoor20_v2/candidates','ros2_ws/build','ros2_ws/install','ros2_ws/log']
    delete_dirs += [str(p.relative_to(ROOT)) for p in ROOT.rglob('__pycache__')]
    delete_files=[str(p.relative_to(ROOT)) for p in (ROOT/'run').iterdir() if p.is_file()]
    delete_files+=['evidence/lesson8_trap_matrix.csv','data/coco_public20/README_旧版选图不再使用.md']
    obsolete_bag=ROOT/'evidence/raw/week3_slam/20261026T025521Z/rosbag'
    protected=[]
    for base in ['evidence/raw','data/coco_indoor20_v2/images','models']:
        for p in files(ROOT/base):
            if obsolete_bag in p.parents:continue
            protected.append({'path':str(p.relative_to(ROOT)),'sha256':digest(p)})
    manifest={'scope':'this project only','before_logical_bytes':before,
      'moves':[{'from':src,'to':dst,'sha256':digest(ROOT/src)} for src,dst in moves.items() if (ROOT/src).is_file()],
      'deletions':[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':digest(p)}
                   for rel in delete_dirs+delete_files for p in files(ROOT/rel)],
      'protected_assets':protected,'compression':'historical unsafe-route ROS bag only; final safe-route bag stays directly readable'}
    plan=ROOT/'docs/cleanup_inventory_20261026.json';plan.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    if not args.apply:print('Cleanup inventory saved; --apply required');return
    for item in manifest['moves']:
        src=ROOT/item['from'];dst=ROOT/item['to'];dst.parent.mkdir(parents=True,exist_ok=True)
        if dst.exists():raise FileExistsError(dst)
        src.rename(dst)
    if obsolete_bag.exists():
        original={str(p.relative_to(obsolete_bag.parent)):digest(p) for p in files(obsolete_bag)}
        archive=obsolete_bag.with_suffix('.tar.gz')
        with tarfile.open(archive,'w:gz',compresslevel=6) as tar:tar.add(obsolete_bag,arcname='rosbag')
        with tarfile.open(archive,'r:gz') as tar:
            recovered={m.name:hashlib.sha256(tar.extractfile(m).read()).hexdigest() for m in tar.getmembers() if m.isfile()}
        if recovered!=original:raise RuntimeError('Archive verification failed; original retained')
        manifest['compressed_bag']={'path':str(archive.relative_to(ROOT)),'sha256':digest(archive),
                                    'members':original,'original_bytes':sum(p.stat().st_size for p in files(obsolete_bag)),
                                    'compressed_bytes':archive.stat().st_size}
        shutil.rmtree(obsolete_bag)
    for rel in delete_dirs:
        p=ROOT/rel
        if p.exists():shutil.rmtree(p)
    for rel in delete_files:(ROOT/rel).unlink(missing_ok=True)
    old=ROOT/'data/coco_public20'
    if old.exists() and not any(old.iterdir()):old.rmdir()
    downloads=ROOT/'data/downloads'
    if downloads.exists() and not any(downloads.iterdir()):downloads.rmdir()
    source=ROOT/'evidence/raw/week8_integration/20261026T021310Z/real_model_live_sim.mp4'
    dest=ROOT/'outputs/week8/real_model_live_sim.mp4';dest.parent.mkdir(parents=True,exist_ok=True)
    if not dest.exists():os.link(source,dest)
    if digest(source)!=digest(dest):raise RuntimeError('Video entry differs from original')
    bad=[item['path'] for item in protected if not (ROOT/item['path']).exists() or digest(ROOT/item['path'])!=item['sha256']]
    if bad:raise RuntimeError('Protected evidence changed: '+repr(bad))
    manifest['protected_assets_verified']=len(protected)
    manifest['after_logical_bytes']=sum(p.stat().st_size for p in files(ROOT))
    manifest['freed_logical_bytes']=before-manifest['after_logical_bytes']
    plan.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:manifest[k] for k in ['before_logical_bytes','after_logical_bytes','freed_logical_bytes','protected_assets_verified']},ensure_ascii=False))

if __name__=='__main__':main()
