#!/usr/bin/env python3
"""Actual ROS synthetic injection: front/left/right/merge/threshold/resolution/expiry."""
import argparse,copy,json,math,os,time
from pathlib import Path
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile,DurabilityPolicy
from geometry_msgs.msg import TransformStamped
from sensor_msgs.msg import CameraInfo
from vision_msgs.msg import Detection2DArray,Detection2D,ObjectHypothesisWithPose
from visualization_msgs.msg import MarkerArray
from tf2_ros import StaticTransformBroadcaster

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--node-output',type=Path,required=True);a=p.parse_args()
    if os.environ.get('ROS_DOMAIN_ID')!='50':p.error('requires isolated domain50')
    rclpy.init();n=Node('course_synthetic_detection_injector');pub=n.create_publisher(Detection2DArray,'/detections',10)
    camera=n.create_publisher(CameraInfo,'/camera_info',10);broadcaster=StaticTransformBroadcaster(n);latest_markers=[None]
    sub=n.create_subscription(MarkerArray,'/semantic_markers',lambda msg:latest_markers.__setitem__(0,msg),QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
    width=[640]
    def info():
        msg=CameraInfo();msg.header.stamp=n.get_clock().now().to_msg();msg.header.frame_id='synthetic_camera'
        msg.width=width[0];msg.height=480;msg.k=[320.,0.,320.,0.,320.,240.,0.,0.,1.];camera.publish(msg)
    timer=n.create_timer(.2,info)
    transform=TransformStamped();transform.header.frame_id='map';transform.child_frame_id='base_footprint'
    transform.transform.translation.x=2.;transform.transform.translation.y=3.;transform.transform.rotation.w=1.
    broadcaster.sendTransform(transform)
    def spin(seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:rclpy.spin_once(n,timeout_sec=.05)
    spin(2)
    if pub.get_subscription_count()!=1:raise RuntimeError('expected one semantic mapper subscription')
    injected=[];snapshots={}
    def inject(case,label,u,confidence=.8,old=False):
        msg=Detection2DArray();msg.header.frame_id='synthetic_camera';msg.header.stamp=n.get_clock().now().to_msg()
        if old:msg.header.stamp.sec-=10
        d=Detection2D();d.header=msg.header;d.id='SYNTHETIC_'+case;d.bbox.center.position.x=float(u);d.bbox.center.position.y=240.;d.bbox.size_x=40.;d.bbox.size_y=60.
        h=ObjectHypothesisWithPose();h.hypothesis.class_id=label;h.hypothesis.score=confidence;d.results=[h];msg.detections=[d]
        pub.publish(msg);injected.append({'case':case,'label':label,'u':u,'score':confidence,'synthetic':True,
          'stamp_ns':msg.header.stamp.sec*10**9+msg.header.stamp.nanosec});spin(.6)
        snapshots[case]=json.loads((a.node_output/'semantic_map.json').read_text())
    inject('front','cup',320);inject('left','bottle',220);inject('right','backpack',420);inject('merge','cup',330)
    inject('low_confidence','person',320,.4)
    width[0]=320;spin(.3);inject('wrong_resolution','cup',320);width[0]=640;spin(.3)
    inject('stale_stamp','cup',320,old=True)
    fresh=copy.deepcopy(snapshots['merge']);spin(5)
    stale=json.loads((a.node_output/'semantic_map.json').read_text());markers=latest_markers[0]
    front=snapshots['front']['items'][0];items={i['label']:i for i in snapshots['merge']['items']}
    events=[json.loads(s) for s in (a.node_output/'events.jsonl').read_text().splitlines()]
    checks={'front_within_5cm':math.hypot(front['x']-3,front['y']-3)<=.05,
      'left_positive_y':items['bottle']['y']>3,'right_negative_y':items['backpack']['y']<3,
      'merge_one_cup_two_observations':len([i for i in fresh['items'] if i['label']=='cup'])==1 and items['cup']['n_obs']==2,
      'low_confidence_not_registered':not any(i['label']=='person' for i in snapshots['low_confidence']['items']),
      'wrong_resolution_rejected':any(e['event']=='rejected' and 'SYNTHETIC_wrong_resolution' in e['ids'] for e in events),
      'old_stamp_rejected':any(e['event']=='rejected' and 'SYNTHETIC_stale_stamp' in e['ids'] for e in events),
      'fresh_to_stale_without_reobservation':all(i['state']=='fresh' for i in fresh['items']) and all(i['state']=='stale' for i in stale['items']),
      'marker_count_matches_json':markers is not None and len(markers.markers)==len(stale['items']),
      'marker_positions_match_json':markers is not None and all(math.hypot(m.pose.position.x-i['x'],m.pose.position.y-i['y'])<1e-9 for m,i in zip(markers.markers,stale['items']))}
    result={'source_kind':'actual_ROS_controlled_synthetic_injection','checks':checks,'all_checks_passed':all(checks.values()),
      'injections':injected,'snapshots':snapshots,'fresh_snapshot':fresh,'stale_snapshot':stale,
      'marker_count':len(markers.markers) if markers else None,
      'limitations':['Synthetic detections and virtual camera intrinsics; no COCO photo localization or physical camera claim.',
                     'TTL derived from a declared synthetic motion trace, not field observations.']}
    (a.node_output/'lab_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(checks,ensure_ascii=False),flush=True)
    n.destroy_node();rclpy.shutdown()
    return 0 if all(checks.values()) else 1

if __name__=='__main__':raise SystemExit(main())
