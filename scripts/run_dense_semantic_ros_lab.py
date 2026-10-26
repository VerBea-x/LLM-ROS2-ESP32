#!/usr/bin/env python3
"""Actual ROS synthetic dense same-class observations; no motor/model interface."""
import argparse,copy,json,os,time
from pathlib import Path
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile,DurabilityPolicy
from sensor_msgs.msg import CameraInfo
from vision_msgs.msg import Detection2DArray,Detection2D,ObjectHypothesisWithPose
from visualization_msgs.msg import MarkerArray
from geometry_msgs.msg import TransformStamped
from tf2_ros import StaticTransformBroadcaster
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from course_audit.semantic_world import semantic_world_fields

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--node-output',type=Path,required=True);a=p.parse_args()
 if os.environ.get('ROS_DOMAIN_ID')!='50':p.error('isolated synthetic domain50 required')
 rclpy.init();n=Node('dense_semantic_injector');pub=n.create_publisher(Detection2DArray,'/detections',10);cam=n.create_publisher(CameraInfo,'/camera_info',10);markers=[None]
 sub=n.create_subscription(MarkerArray,'/semantic_markers',lambda m:markers.__setitem__(0,m),QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
 broadcaster=StaticTransformBroadcaster(n);t=TransformStamped();t.header.frame_id='map';t.child_frame_id='base_footprint';t.transform.translation.x=2.;t.transform.translation.y=3.;t.transform.rotation.w=1.;broadcaster.sendTransform(t)
 def camera():
  m=CameraInfo();m.header.stamp=n.get_clock().now().to_msg();m.header.frame_id='synthetic_camera';m.width=640;m.height=480;m.k=[320.,0.,320.,0.,320.,240.,0.,0.,1.];cam.publish(m)
 timer=n.create_timer(.2,camera)
 def spin(seconds):
  end=time.monotonic()+seconds
  while time.monotonic()<end:rclpy.spin_once(n,timeout_sec=.05)
 spin(2);deadline=time.monotonic()+10
 while pub.get_subscription_count()==0 and time.monotonic()<deadline:spin(.2)
 if pub.get_subscription_count()!=1:raise RuntimeError('expected exactly one semantic mapper')
 raw=[];snapshots=[]
 for name,pixels in [('two_objects',[220,420]),('repeat_with_jitter',[222,418]),('ambiguous_single',[320])]:
  m=Detection2DArray();m.header.stamp=n.get_clock().now().to_msg();m.header.frame_id='synthetic_camera'
  for index,u in enumerate(pixels):
   d=Detection2D();d.header=m.header;d.id=f'SYNTHETIC_{name}_{index}';d.bbox.center.position.x=float(u);d.bbox.center.position.y=240.;d.bbox.size_x=30.;d.bbox.size_y=50.
   h=ObjectHypothesisWithPose();h.hypothesis.class_id='cup';h.hypothesis.score=.8;d.results=[h];m.detections.append(d)
  pub.publish(m);raw.append({'case':name,'stamp_ns':m.header.stamp.sec*10**9+m.header.stamp.nanosec,'pixels':pixels});spin(.6)
  snapshots.append(json.loads((a.node_output/'semantic_map.json').read_text()))
 first,repeat,ambiguous=snapshots;fresh=copy.deepcopy(ambiguous);spin(5);stale=json.loads((a.node_output/'semantic_map.json').read_text());events=[json.loads(s) for s in (a.node_output/'events.jsonl').read_text().splitlines()]
 def identity(doc):return [{k:r[k] for k in ['target_name','x','y','n_obs','last_seen','evidence_ids']} for r in doc['items']]
 fields=semantic_world_fields(fresh);names=[r['target_name'] for r in first['items']]
 checks={'two_close_cups_separate':len(first['items'])==2 and abs(first['items'][0]['y']-first['items'][1]['y'])<.61,
  'unique_target_names':len(set(names))==2,'repeat_keeps_names':[r['target_name'] for r in repeat['items']]==names,
  'repeat_increments_each_once':[r['n_obs'] for r in repeat['items']]==[2,2],
  'ambiguous_frame_rejected':any(e['event']=='rejected' and 'ambiguous' in e['reason'] for e in events),
  'ambiguous_frame_does_not_mutate_targets':identity(repeat)==identity(ambiguous),
  'auditor_conversion_retains_both':set(fields['semantic_items'])==set(names),
  'two_markers':markers[0] is not None and len(markers[0].markers)==2,
  'both_expire':len(stale['items'])==2 and all(r['state']=='stale' for r in stale['items'])}
 result={'source_kind':'actual_ROS_controlled_synthetic_dense_frame','checks':checks,'all_checks_passed':all(checks.values()),
  'injections':raw,'snapshots':snapshots,'fresh_snapshot':fresh,'stale_snapshot':stale,
  'limitations':['Synthetic simultaneous same-class detections with virtual1m range.',
   'Not a general identity tracker; staggered appearance, occlusion and crossings unverified.']}
 (a.node_output/'lab_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(checks));n.destroy_node();rclpy.try_shutdown()
 return 0 if result['all_checks_passed'] else 1
if __name__=='__main__':raise SystemExit(main())
