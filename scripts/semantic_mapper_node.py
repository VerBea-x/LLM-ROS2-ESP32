#!/usr/bin/env python3
"""Course ROS semantic registration; this run uses explicitly synthetic detections."""
import argparse,copy,datetime as dt,json,math,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from course_audit.semantic_registration import register_frame,export_map
import rclpy
from rclpy.node import Node
from rclpy.time import Time
from rclpy.duration import Duration
from rclpy.executors import ExternalShutdownException
from rclpy._rclpy_pybind11 import RCLError
from rclpy.qos import QoSProfile,DurabilityPolicy
from sensor_msgs.msg import CameraInfo
from vision_msgs.msg import Detection2DArray
from visualization_msgs.msg import Marker,MarkerArray
from std_msgs.msg import String
from tf2_ros import Buffer,TransformListener

class SemanticMapper(Node):
    def __init__(self,rules,out):
        super().__init__('course_semantic_mapper');self.rules=rules;self.out=out;self.items=[];self.info=None;self.seen=set()
        self.buffer=Buffer(cache_time=Duration(seconds=5));self.listener=TransformListener(self.buffer,self)
        self.create_subscription(CameraInfo,'/camera_info',self.camera_cb,10)
        self.create_subscription(Detection2DArray,'/detections',self.detection_cb,10)
        qos=QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.markers=self.create_publisher(MarkerArray,'/semantic_markers',qos)
        self.documents=self.create_publisher(String,'/semantic_map',qos)
        self.create_timer(.2,self.publish)
    def log(self,event,**kw):
        with (self.out/'events.jsonl').open('a') as f:f.write(json.dumps({'event':event,'wall_ns':time.time_ns(),**kw},ensure_ascii=False)+'\n')
    def camera_cb(self,msg):self.info=msg
    def detection_cb(self,msg):
        try:
            stamp=msg.header.stamp.sec*10**9+msg.header.stamp.nanosec
            age=(self.get_clock().now().nanoseconds-stamp)/1e9
            if stamp<=0 or not -.1<=age<=1:raise ValueError('检测时间戳过期或来自未来')
            info=self.info
            if info is None or info.width!=640 or info.height!=480:raise ValueError('camera_info分辨率与冻结原图640x480不一致')
            if info.header.frame_id!=msg.header.frame_id:raise ValueError('相机与检测frame_id不一致')
            camera_age=(self.get_clock().now().nanoseconds-(info.header.stamp.sec*10**9+info.header.stamp.nanosec))/1e9
            if not -.1<=camera_age<=2:raise ValueError('camera_info不新鲜')
            transform=self.buffer.lookup_transform('map','base_footprint',Time.from_msg(msg.header.stamp),timeout=Duration(seconds=.2))
            t=transform.transform;q=t.rotation;yaw=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))
            observations=[];keys=[]
            for detection in msg.detections:
                key=(stamp,detection.id)
                if key in self.seen:continue
                if not detection.results:raise ValueError('缺少分类假设')
                h=max(detection.results,key=lambda x:x.hypothesis.score).hypothesis
                if h.score<.5:
                    self.log('below_threshold',id=detection.id,score=h.score);continue
                if h.class_id not in self.rules:raise ValueError('缺少该类别的τ依据')
                seen_at=dt.datetime.fromtimestamp(stamp/1e9,dt.timezone.utc).isoformat()
                observations.append({'u':detection.bbox.center.position.x,'image_width':640,'conf':h.score,
                  'label':h.class_id,'evidence_id':detection.id})
                keys.append(key)
            candidate=register_frame(self.items,observations,(t.translation.x,t.translation.y,yaw),
              {'fx':info.k[0],'cx':info.k[2],'width':info.width},.5,
              dt.datetime.fromtimestamp(stamp/1e9,dt.timezone.utc).isoformat())
            export_map(candidate,self.rules,dt.datetime.now(dt.timezone.utc).isoformat())
            self.items=candidate;self.seen.update(keys)
            self.log('accepted',stamp_ns=stamp,ids=[d.id for d in msg.detections],item_count=len(self.items))
            self.publish()
        except Exception as exc:self.log('rejected',reason=str(exc),ids=[d.id for d in msg.detections])
    def publish(self):
        doc=export_map(self.items,self.rules,dt.datetime.now(dt.timezone.utc).isoformat())
        doc.update(source_kind='controlled_synthetic_detection_ros_lab',camera_calibration='declared virtual intrinsics, not hardware calibration',registration_policy='frame_one_to_one_v2')
        markers=MarkerArray()
        for index,item in enumerate(doc['items']):
            m=Marker();m.header.frame_id='map';m.header.stamp=self.get_clock().now().to_msg();m.ns=item['label'];m.id=index
            m.type=Marker.SPHERE;m.action=Marker.ADD;m.pose.position.x=item['x'];m.pose.position.y=item['y'];m.pose.orientation.w=1.
            m.scale.x=m.scale.y=m.scale.z=.12;m.color.a=1.
            m.color.r=.1 if item['state']=='fresh' else 1.;m.color.g=.8 if item['state']=='fresh' else .5;m.color.b=.1
            markers.markers.append(m)
        tmp=self.out/'semantic_map.tmp';tmp.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n');tmp.replace(self.out/'semantic_map.json')
        text=String();text.data=json.dumps(doc,ensure_ascii=False);self.documents.publish(text);self.markers.publish(markers)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--rules',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():p.error('use a new output directory')
    import os
    if os.environ.get('ROS_DOMAIN_ID')!='50':p.error('controlled lab requires isolated domain50')
    a.output.mkdir(parents=True);rclpy.init();node=SemanticMapper(json.loads(a.rules.read_text()),a.output)
    try:rclpy.spin(node)
    except (KeyboardInterrupt,ExternalShutdownException):pass
    except RCLError:
        if rclpy.ok():raise
    finally:node.destroy_node();rclpy.try_shutdown()

if __name__=='__main__':main()
