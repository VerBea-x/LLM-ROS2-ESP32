"""W6 geometry, registration and ISO timestamp freshness; requires evidence-backed tau."""
from __future__ import annotations
import datetime as dt
import copy
import math


def timestamp(value):
    parsed=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None:raise ValueError('timestamps require a timezone')
    return parsed


def project(u,fx,cx,width,detection_width,pose,range_m=1.0,cam_offset_rad=0.0):
    values=[u,fx,cx,width,detection_width,*pose,range_m,cam_offset_rad]
    if not all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in values):
        raise ValueError('geometry inputs must be finite numbers')
    if fx<=0 or range_m<=0 or width<=0 or detection_width!=width or not 0<=u<width:
        raise ValueError('invalid intrinsics, range, pixel, or calibration/detection resolution mismatch')
    bearing=math.atan2(cx-u,fx)+cam_offset_rad
    x,y,yaw=pose
    return {'x':x+range_m*math.cos(yaw+bearing),'y':y+range_m*math.sin(yaw+bearing),
            'bearing_rad':bearing,'range_assumption_m':range_m}


def register(items,detection,pose,intrinsics,conf_th,seen_at,merge_radius=1.0):
    """Legacy single-observation baseline; runtime uses register_frame instead."""
    timestamp(seen_at)
    score=detection['conf']
    if not math.isfinite(score) or not 0<=score<=1 or not 0<=conf_th<=1 or merge_radius<=0:
        raise ValueError('invalid score, working threshold, or merge radius')
    if score<conf_th:return items
    if not detection.get('evidence_id'):raise ValueError('detection evidence_id required')
    projected=project(detection['u'],intrinsics['fx'],intrinsics['cx'],intrinsics['width'],
                      detection['image_width'],pose)
    label=detection['label']
    candidates=[(math.hypot(item['x']-projected['x'],item['y']-projected['y']),i)
                for i,item in enumerate(items) if item['label']==label]
    distance,index=min(candidates,default=(math.inf,None))
    if distance<=merge_radius:
        old=items[index];count=old['n_obs']
        if timestamp(seen_at)<timestamp(old['last_seen']):
            raise ValueError('out-of-order observation cannot rewind last_seen or update the landmark')
        items[index]={**old,'x':(old['x']*count+projected['x'])/(count+1),
                     'y':(old['y']*count+projected['y'])/(count+1),'conf':max(old['conf'],score),
                     'last_seen':seen_at,'n_obs':count+1,
                     'evidence_ids':old['evidence_ids']+[detection['evidence_id']]}
    else:
        items.append({'label':label,'x':projected['x'],'y':projected['y'],'conf':score,
                      'last_seen':seen_at,'n_obs':1,'evidence_ids':[detection['evidence_id']]})
    return items


def export_map(items,rules,now):
    current=timestamp(now);result=[]
    for item in items:
        rule=rules.get(item['label'])
        if not rule or not rule.get('observation_evidence_id'):
            raise ValueError('tau must cite observation evidence; no unmarked default')
        tau=rule['tau_s']
        if isinstance(tau,bool) or not isinstance(tau,(int,float)) or not math.isfinite(tau) or tau<=0:
            raise ValueError('tau_s must be positive finite seconds')
        age=(current-timestamp(item['last_seen'])).total_seconds()
        result.append({**item,'age_s':age,'tau_s':tau,
                       'state':'fresh' if 0<=age<=tau else 'stale',
                       'tau_evidence_id':rule['observation_evidence_id']})
    return {'schema_version':1,'frame_id':'map','generated_at':now,'items':result,
            'limitations':['range=1m is an explicit teaching approximation; not measured object depth.']}


def register_frame(items,detections,pose,intrinsics,conf_th,seen_at,merge_radius=1.0,ambiguity_gap=0.15):
    """Atomic one-to-one association against the map BEFORE this frame.

    Same-frame detections never merge into newly created entries. Stable map
    names identify entries, not detector-provided tracking identities. Missing
    or newly appearing objects still require conservative association checks.
    """
    seen=timestamp(seen_at)
    if not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
               for v in (conf_th,merge_radius,ambiguity_gap)) or not 0<=conf_th<=1 or merge_radius<=0 or ambiguity_gap<0:
        raise ValueError('invalid registration thresholds')
    prepared=[]
    for detection in detections:
        score=detection['conf']
        if isinstance(score,bool) or not isinstance(score,(int,float)) or not math.isfinite(score) or not 0<=score<=1:
            raise ValueError('invalid confidence')
        if score<conf_th:continue
        if not detection.get('evidence_id') or not isinstance(detection.get('label'),str) or not detection['label']:
            raise ValueError('class and observation evidence required')
        projected=project(detection['u'],intrinsics['fx'],intrinsics['cx'],intrinsics['width'],detection['image_width'],pose)
        candidates=sorted((math.hypot(row['x']-projected['x'],row['y']-projected['y']),i)
                          for i,row in enumerate(items) if row['label']==detection['label'])
        candidates=[c for c in candidates if c[0]<=merge_radius]
        if len(candidates)>1 and candidates[1][0]-candidates[0][0]<=ambiguity_gap:
            raise ValueError('ambiguous same-class association; frame not committed')
        index=candidates[0][1] if candidates else None
        if index is not None and seen<timestamp(items[index]['last_seen']):
            raise ValueError('out-of-order observation cannot rewind last_seen')
        prepared.append((detection,projected,index))
    assigned=[index for _,_,index in prepared if index is not None]
    if len(set(assigned))!=len(assigned):
        raise ValueError('multiple detections compete for one target; frame not committed')
    result=copy.deepcopy(items)
    for detection,projected,index in prepared:
        if index is not None:
            old=result[index];count=old['n_obs']
            result[index]={**old,'x':(old['x']*count+projected['x'])/(count+1),
                           'y':(old['y']*count+projected['y'])/(count+1),
                           'conf':max(old['conf'],detection['conf']),'n_obs':count+1,'last_seen':seen_at,
                           'evidence_ids':old['evidence_ids']+[detection['evidence_id']]}
        else:
            label=detection['label'];existing={r.get('target_name') for r in result};serial=1
            while f'{label}__{serial:03d}' in existing:serial+=1
            result.append({'label':label,'target_name':f'{label}__{serial:03d}',
                           'x':projected['x'],'y':projected['y'],'conf':detection['conf'],
                           'n_obs':1,'last_seen':seen_at,'evidence_ids':[detection['evidence_id']]})
    return result


def error_components(estimate,truth,station):
    dx,dy=truth[0]-station[0],truth[1]-station[1]
    distance=math.hypot(dx,dy)
    if distance<=0:raise ValueError('truth and station must differ')
    ex,ey=estimate[0]-truth[0],estimate[1]-truth[1]
    radial=(ex*dx+ey*dy)/distance
    tangential=abs((ex*dy-ey*dx)/distance)
    return {'error_m':math.hypot(ex,ey),'radial_m':radial,'tangential_m':tangential,
            'dominant':'radial' if abs(radial)>=tangential else 'tangential'}
