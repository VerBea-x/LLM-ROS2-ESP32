#!/usr/bin/env python3
"""Record live V3 agent messages, AMCL, independent truth and a simulation video."""
import argparse,hashlib,json,math,os,subprocess,time
from pathlib import Path
import rclpy,yaml
from rclpy.node import Node
from rclpy.qos import QoSProfile,DurabilityPolicy
from geometry_msgs.msg import PoseWithCovarianceStamped
from std_msgs.msg import String
from PIL import Image,ImageDraw,ImageFont
from sim_truth_driver import read_truth
ROOT=Path(__file__).resolve().parents[1]

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if os.environ.get('ROS_DOMAIN_ID')!='47':p.error('isolated AMCL simulation domain47 required')
 if (a.output/'execution_trace.json').exists():p.error('existing run must not be overwritten')
 provenance=json.loads((a.output/'provenance.json').read_text());mapfile=ROOT/'outputs/slam_improvement/map_slam.yaml';meta=yaml.safe_load(mapfile.read_text())
 image=Image.open(mapfile.parent/meta['image']).convert('RGB');width,height=image.size;image=image.resize((600,600));res=meta['resolution'];ox,oy,_=meta['origin']
 font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',13)
 rclpy.init();n=Node('course_v3_live_recorder');events=[];truths=[];frames=[];amcl=[None]
 pub=n.create_publisher(String,'/agent/instruction',10)
 def receive(msg):events.append(json.loads(msg.data))
 sub=n.create_subscription(String,'/agent/plan_events',receive,100)
 def pose(msg):
  p=msg.pose.pose.position;amcl[0]={'x':p.x,'y':p.y,'stamp_ns':msg.header.stamp.sec*10**9+msg.header.stamp.nanosec}
 posesub=n.create_subscription(PoseWithCovarianceStamped,'/amcl_pose',pose,QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
 def xy(x,y):return ((x-ox)/res*600/width,640-(y-oy)/res*600/height)
 video=a.output/'v3_slam_live_sim.mp4';err=(a.output/'ffmpeg.log').open('wb')
 ff=subprocess.Popen(['ffmpeg','-y','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s','1000x650','-r','5','-i','-','-an','-c:v','libx264','-preset','fast','-crf','23','-pix_fmt','yuv420p',str(video)],stdin=subprocess.PIPE,stderr=err)
 start=time.monotonic();sent=False;finished=None
 try:
  while time.monotonic()-start<90:
   tick=time.monotonic()
   while time.monotonic()-tick<.10:rclpy.spin_once(n,timeout_sec=.01)
   state=read_truth();truth=state['robot_truth'];wall=time.time_ns();truths.append({'wall_ns':wall,**state})
   if not sent and time.monotonic()-start>=2:
    count=pub.get_subscription_count()
    if count>1 or (count==0 and time.monotonic()-start>=15):raise RuntimeError(f'expected one course_agent subscription, got {count}')
    if count==1:
     msg=String();msg.data=provenance['instruction'];pub.publish(msg);sent=True
   canvas=Image.new('RGB',(1000,650),'#172333');canvas.paste(image,(0,40));d=ImageDraw.Draw(canvas)
   d.text((8,8),'LIVE: AMCL on SLAM map | frozen model plan | V3 task contract',font=font,fill='white')
   x,y=xy(truth['x'],truth['y']);d.ellipse((x-8,y-8,x+8,y+8),fill='#10b981')
   if amcl[0]:
    x,y=xy(amcl[0]['x'],amcl[0]['y']);d.ellipse((x-10,y-10,x+10,y+10),outline='#3b82f6',width=3)
   x,y=xy(7,6);d.line((x-8,y-8,x+8,y+8),fill='#ef4444',width=3);d.line((x-8,y+8,x+8,y-8),fill='#ef4444',width=3)
   lines=['Green: simulator truth; blue: AMCL','Red: fixed virtual waypoint',f"t={time.monotonic()-start:.1f}s | tick={state['tick_n']}",
    f"truth x={truth['x']:.3f} y={truth['y']:.3f}",'No new API request; no physical car','slip=.05;720 simulated lidar rays','', 'Actual event stream:']
   for e in events[-16:]:
    line=e['type']
    if e['type']=='audit':line+=' '+e['decision']['rule_id']
    if e['type']=='exec':line+=' '+e['call']['name']+' '+str(e['ok'])
    if e['type']=='report':line+=' '+str(e.get('result',''))
    lines.append(line)
   for i,line in enumerate(lines):d.text((610,48+i*22),line[:48],font=font,fill='white')
   ff.stdin.write(canvas.tobytes());frames.append({'frame':len(frames),'wall_ns':wall,'event_count':len(events),'amcl':amcl[0]})
   if any('final_report' in e for e in events):
    if finished is None:finished=time.monotonic()
    elif time.monotonic()-finished>=2:break
   time.sleep(max(0,.2-(time.monotonic()-tick)))
 finally:
  ff.stdin.close();code=ff.wait(timeout=20);err.close();final=read_truth()['robot_truth']
  last=next((e for e in reversed(events) if 'final_report' in e),None)
  error=math.hypot(final['x']-7,final['y']-6)
  stop=any(e['type']=='exec' and e['call']['name']=='stop' and e['ok'] and e['evidence'].get('verified') for e in events)
  contract=any(e['type']=='audit' and e.get('stage')=='task_contract' and e['decision']['allowed'] for e in events)
  checks={'final_completed':bool(last and last['result']=='COMPLETED'),'truth_error_le_30cm':error<=.30,'stop_verified':stop,
   'task_contract_pass_before_exec':contract and next((i for i,e in enumerate(events) if e.get('stage')=='task_contract'),10**6)<next((i for i,e in enumerate(events) if e['type']=='exec'),-1),
   'replans_le_two':max([e.get('replan_count',0) for e in events],default=0)<=2,'ffmpeg_success':code==0}
  report={'source_kind':provenance['source_kind'],'instruction':provenance['instruction'],'events':events,'truth_trace':truths,
   'final_truth':final,'truth_goal_error_m':error,'checks':checks,'all_checks_passed':all(checks.values()),
   'frames':frames,'video_duration_s':len(frames)/5,'wall_duration_s':time.monotonic()-start,'fps':5,
   'new_model_requests':0,'limitations':provenance['limits']+['Video rendered during execution from live truth, AMCL and agent events; not a physical-camera video or an offline replay.']}
  (a.output/'execution_trace.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');n.destroy_node();rclpy.try_shutdown()
  print(json.dumps({'checks':checks,'truth_goal_error_m':error,'frames':len(frames)},ensure_ascii=False),flush=True)
 return 0 if report['all_checks_passed'] else 1
if __name__=='__main__':raise SystemExit(main())
