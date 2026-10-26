#!/usr/bin/env python3
"""Record a live simulator view, not a replay or a physical camera recording."""
import argparse
import datetime as dt
import json
import math
import subprocess
import time
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from sim_truth_driver import read_truth

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--events',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--map',type=Path,required=True);p.add_argument('--seconds',type=float,default=80)
    a=p.parse_args()
    if a.output.exists():p.error('output exists')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    base=Image.open(a.map).convert('RGB').resize((600,600))
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',15)
    small=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',12)
    err=a.output.with_suffix('.ffmpeg.log').open('wb')
    process=subprocess.Popen(['ffmpeg','-y','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24',
      '-s','900x650','-r','5','-i','-','-an','-c:v','libx264','-preset','fast','-crf','23','-pix_fmt','yuv420p',str(a.output)],
      stdin=subprocess.PIPE,stderr=err)
    frames=[];start=time.monotonic();finished=None
    try:
        while time.monotonic()-start<a.seconds:
            begin=time.monotonic();state=read_truth(8002)
            events=[]
            if a.events.exists():
                for line in a.events.read_text().splitlines():
                    try:events.append(json.loads(line))
                    except json.JSONDecodeError:pass
            canvas=Image.new('RGB',(900,650),'#16202b');canvas.paste(base,(0,40));d=ImageDraw.Draw(canvas)
            d.text((12,9),'LIVE SIMULATION | real model -> audit -> navigation',font=font,fill='white')
            truth=state['robot_truth'];x=truth['x']*60;y=640-truth['y']*60;yaw=math.radians(truth['theta_deg'])
            d.ellipse((x-12,y-12,x+12,y+12),fill='#10b981',outline='#064e3b',width=2)
            d.line((x,y,x+24*math.cos(yaw),y-24*math.sin(yaw)),fill='#b91c1c',width=3)
            d.ellipse((7*60-8,640-6*60-8,7*60+8,640-6*60+8),outline='#ef4444',width=3)
            lines=['Truth localization, slip=0','Virtual landmarks, not images',
                   f"t={time.monotonic()-start:5.1f}s  tick={state['tick_n']}",
                   f"x={truth['x']:.3f} y={truth['y']:.3f}",f"yaw={truth['theta_deg']:.1f}deg",'','Recorded event sequence:']
            for e in events[-15:]:
                text=e['type']
                if e['type']=='audit':text+=' '+e['decision']['rule_id']
                if e['type']=='exec':text+=' '+e['call']['name']+' '+str(e['ok'])
                if e['type']=='report':text+=' '+str(e.get('result',''))
                lines.append(text)
            for i,line in enumerate(lines):d.text((614,55+i*22),line[:36],font=small,fill='white')
            frames.append({'frame':len(frames),'captured_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
                           'elapsed_s':time.monotonic()-start,'truth':state,'event_count':len(events)})
            process.stdin.write(canvas.tobytes())
            if any('final_report' in e for e in events):
                if finished is None:finished=time.monotonic()
                elif time.monotonic()-finished>2:break
            time.sleep(max(0,.2-(time.monotonic()-begin)))
    finally:
        process.stdin.close();code=process.wait(timeout=20);err.close()
        a.output.with_suffix('.capture.json').write_text(json.dumps({'source_kind':'live_simulator_visualization_capture',
          'frames':frames,'fps':5,'video_duration_s':len(frames)/5,'wall_duration_s':time.monotonic()-start,
          'ffmpeg_exit_code':code,'limitations':['Not a physical camera video or desktop screen capture.',
             'Rendered live from simulator truth and actual agent log; not an offline replay.']},indent=2)+'\n')
        if code:raise RuntimeError('ffmpeg failed')
        print('Saved live simulator visualization:',a.output)

if __name__=='__main__':main()
