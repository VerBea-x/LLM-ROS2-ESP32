#!/usr/bin/env python3
"""Record AMCL initialization and Nav2 trials on the actual frozen SLAM map."""
import argparse,hashlib,json,math,os,time
from pathlib import Path
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile,DurabilityPolicy
from geometry_msgs.msg import PoseWithCovarianceStamped,Twist
from nav_msgs.msg import OccupancyGrid,Odometry
from std_srvs.srv import Empty
from nav_g03.srv import NavigateTo
from sim_truth_driver import read_truth
ROOT=Path(__file__).resolve().parents[1]

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--round',type=int,required=True);p.add_argument('--initialize-only',action='store_true');p.add_argument('--protocol',type=Path,default=ROOT/'config/week34_slam_map_validation_v1.json');a=p.parse_args()
 if os.environ.get('ROS_DOMAIN_ID')!='47':p.error('isolated simulation domain47 required')
 target=a.output/'trials.json'
 if target.exists():p.error('existing trial must not be overwritten')
 protocol=json.loads(a.protocol.read_text())
 a.output.mkdir(parents=True,exist_ok=True);rclpy.init();n=Node('course_slam_map_benchmark')
 events=[];samples=[];trials=[];maps={};latest_speed=[None];initial_stamp=[None];start=time.monotonic()
 def emit(kind,**kw):events.append({'event':kind,'wall_ns':time.time_ns(),'elapsed_s':time.monotonic()-start,**kw})
 def sample(msg):
  stamp=msg.header.stamp.sec*10**9+msg.header.stamp.nanosec
  if initial_stamp[0] is None or stamp<=initial_stamp[0] or any(s['stamp_ns']==stamp for s in samples):return
  t0=time.time_ns();truth=read_truth()['robot_truth'];t1=time.time_ns();pose=msg.pose.pose;q=pose.orientation
  yaw=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z));age=(t0-stamp)/1e9;latency=(t1-t0)/1e9
  samples.append({'stamp_ns':stamp,'estimate':[pose.position.x,pose.position.y,yaw],
   'truth':truth,'age_s':age,'truth_request_s':latency,'valid_timing':0<=age<=protocol['sample_max_age_s'] and latency<=protocol['truth_http_max_latency_s'],
   'position_error_m':math.hypot(pose.position.x-truth['x'],pose.position.y-truth['y']),
   'yaw_error_deg':math.degrees(math.atan2(math.sin(yaw-math.radians(truth['theta_deg'])),math.cos(yaw-math.radians(truth['theta_deg']))))})
 qos=QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL)
 subs=[n.create_subscription(PoseWithCovarianceStamped,'/amcl_pose',sample,qos),
       n.create_subscription(OccupancyGrid,'/map',lambda m:maps.__setitem__('map',m),qos),
       n.create_subscription(OccupancyGrid,'/global_costmap/costmap',lambda m:maps.__setitem__('costmap',m),qos),
       n.create_subscription(Odometry,'/odom',lambda m:latest_speed.__setitem__(0,{'wall_ns':time.time_ns(),'linear':m.twist.twist.linear.x,'angular':m.twist.twist.angular.z}),10)]
 initial=n.create_publisher(PoseWithCovarianceStamped,'/initialpose',10);zero=n.create_publisher(Twist,'/cmd_vel',10)
 update=n.create_client(Empty,'/request_nomotion_update');client=n.create_client(NavigateTo,'/navigate_to')
 report={'protocol':protocol,'round':a.round,'source_kind':protocol['source_kind'],'initial_gate':None,'trials':trials,'amcl_samples':samples,'events':events,'limitations':protocol['limits']}
 def save():target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 def spin(seconds):
  deadline=time.monotonic()+seconds
  while time.monotonic()<deadline:rclpy.spin_once(n,timeout_sec=.05)
 try:
  if not update.wait_for_service(timeout_sec=30) or not client.wait_for_service(timeout_sec=10):raise RuntimeError('AMCL or navigate service unavailable')
  spin(2);t=read_truth()['robot_truth'];msg=PoseWithCovarianceStamped();msg.header.frame_id='map';msg.header.stamp=n.get_clock().now().to_msg()
  initial_stamp[0]=msg.header.stamp.sec*10**9+msg.header.stamp.nanosec
  msg.pose.pose.position.x=t['x'];msg.pose.pose.position.y=t['y'];yaw=math.radians(t['theta_deg'])
  msg.pose.pose.orientation.z=math.sin(yaw/2);msg.pose.pose.orientation.w=math.cos(yaw/2)
  msg.pose.covariance[0]=msg.pose.covariance[7]=protocol['initial_covariance_xy_m']**2;msg.pose.covariance[35]=math.radians(protocol['initial_covariance_yaw_deg'])**2
  initial.publish(msg);emit('explicit_initial_pose',truth=t,truth_tf_published=False)
  for _ in range(protocol['initial_observation_s']):
   if update.service_is_ready():update.call_async(Empty.Request())
   spin(1)
  initial_samples=[s for s in samples if s['valid_timing']];last=initial_samples[-protocol['initial_gate_required_fresh_samples']:]
  report['initial_gate']={'passed':len(last)==protocol['initial_gate_required_fresh_samples'] and all(s['position_error_m']<=protocol['initial_gate_position_error_m'] for s in last),
   'valid_sample_count':len(initial_samples),'selected_stamps':[s['stamp_ns'] for s in last],'errors_m':[s['position_error_m'] for s in last],
   'limits':'Distinct stationary updates are correlated, not independent experimental replicates.'}
  if 'map' not in maps:raise RuntimeError('no map received')
  grid=maps['map'];origin=grid.info.origin
  mapdata={'width':grid.info.width,'height':grid.info.height,'resolution_m':grid.info.resolution,
   'origin_x_m':origin.position.x,'origin_y_m':origin.position.y,'origin_yaw_rad':0.,'data':list(grid.data),'occupied_threshold':50}
  (a.output/'map_snapshot.json').write_text(json.dumps(mapdata)+'\n');save()
  print(json.dumps({'round':a.round,'initial_gate':report['initial_gate']}),flush=True)
  if not report['initial_gate']['passed']:report['result']='INITIAL_LOCALIZATION_GATE_FAILED';return 2
  # Let costmaps consume the initialized map->odom before issuing goals.
  spin(2)
  if 'costmap' in maps:
   grid=maps['costmap'];origin=grid.info.origin
   cost={'width':grid.info.width,'height':grid.info.height,'resolution_m':grid.info.resolution,
    'origin_x_m':origin.position.x,'origin_y_m':origin.position.y,'origin_yaw_rad':0.,'data':list(grid.data),'occupied_threshold':50}
   (a.output/'costmap_snapshot.json').write_text(json.dumps(cost)+'\n')
  if a.initialize_only:
   report['result']='INITIALIZED_ONLY';return 0
  for goal in protocol['goals']:
   before=read_truth();req=NavigateTo.Request();req.x,req.y,req.theta=map(float,goal['pose']);emit('request',goal=goal,start_truth=before)
   future=client.call_async(req);deadline=time.monotonic()+75
   while not future.done() and time.monotonic()<deadline:rclpy.spin_once(n,timeout_sec=.05)
   if not future.done():raise RuntimeError('client75s watchdog; no further goals')
   response=future.result();truth0=time.time_ns();after=read_truth();truth1=time.time_ns();t=after['robot_truth']
   row={'id':goal['id'],'pose':goal['pose'],'result':response.result,'reason':response.reason,'elapsed_s':response.elapsed,
     'start_truth':before,'end_truth':after,'truth_endpoint_request_s':(truth1-truth0)/1e9,
     'truth_goal_error_m':math.hypot(t['x']-req.x,t['y']-req.y)}
   row['passed']=row['result']=='SUCCEEDED' and row['truth_goal_error_m']<=protocol['truth_goal_tolerance_m'] and row['truth_endpoint_request_s']<=protocol['truth_http_max_latency_s']
   spin(.7);speed=latest_speed[0];row['post_response_odom']=speed;row['post_response_stationary']=bool(speed and (time.time_ns()-speed['wall_ns'])/1e9<.5 and abs(speed['linear'])<.02 and abs(speed['angular'])<.05)
   trials.append(row);emit('response',**row);save();print(json.dumps({'round':a.round,**{k:row[k] for k in ['id','result','elapsed_s','truth_goal_error_m','passed']}}),flush=True)
  report['result']='PASSED' if all(t['passed'] for t in trials) else 'NAVIGATION_GATE_FAILED'
  return 0
 except Exception as exc:report['result']='EXPERIMENT_ERROR';report['error']=str(exc);raise
 finally:
  for _ in range(3):zero.publish(Twist());rclpy.spin_once(n,timeout_sec=.05)
  save();n.destroy_node();rclpy.try_shutdown()
if __name__=='__main__':raise SystemExit(main())
