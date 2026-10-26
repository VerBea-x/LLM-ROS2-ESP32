"""Score raw ROS occupancy snapshots using a frozen initial-frame calibration."""
import argparse
import json
import math
from pathlib import Path
import numpy as np


def compare(truth_snapshot,estimate_snapshot,initial_snapshot):
    truth_doc=json.loads(truth_snapshot.read_text());est_doc=json.loads(estimate_snapshot.read_text())
    calibration=json.loads(initial_snapshot.read_text())['transforms']['map->odom']
    gt=truth_doc['grids']['/map'];est=est_doc['grids']['/map']
    truth=np.array(gt['data']).reshape(gt['height'],gt['width'])
    estimate=np.array(est['data']).reshape(est['height'],est['width'])
    y,x=np.mgrid[0:gt['height'],0:gt['width']]
    gx=gt['origin'][0]+(x+.5)*gt['resolution'];gy=gt['origin'][1]+(y+.5)*gt['resolution']
    q=calibration['rotation'];yaw=math.atan2(2*(q[3]*q[2]+q[0]*q[1]),1-2*(q[1]**2+q[2]**2))
    # At startup the simulator's odom frame shares world coordinates. Use only
    # the pre-route calibration, never optimize an alignment against final map.
    sx=calibration['translation'][0]+math.cos(yaw)*gx-math.sin(yaw)*gy
    sy=calibration['translation'][1]+math.sin(yaw)*gx+math.cos(yaw)*gy
    ox,oy=est['origin'];angle=est['origin_yaw'];dx=sx-ox;dy=sy-oy
    ix=np.floor((math.cos(angle)*dx+math.sin(angle)*dy)/est['resolution']).astype(int)
    iy=np.floor((-math.sin(angle)*dx+math.cos(angle)*dy)/est['resolution']).astype(int)
    inside=(ix>=0)&(iy>=0)&(ix<est['width'])&(iy<est['height'])
    aligned=np.full(truth.shape,-1,dtype=int)
    aligned[inside]=estimate[iy[inside],ix[inside]]
    domain=truth>=0;known=domain&(aligned>=0);gocc=truth>=50;eocc=aligned>=50
    tp=int(np.sum(domain&gocc&eocc));fp=int(np.sum(domain&~gocc&eocc))
    fn=int(np.sum(domain&gocc&~eocc));tn=int(np.sum(known&~gocc&~eocc))
    report={'source_kind':'actual_ros_map_snapshots_fixed_initial_registration',
      'truth_snapshot':str(truth_snapshot),'estimate_snapshot':str(estimate_snapshot),
      'initial_calibration_snapshot':str(initial_snapshot),
      'initial_frame_calibration':calibration,'registration':'fixed initial map->odom; nearest-neighbor cell lookup, no fitted alignment',
      'known_coverage':float(known.sum()/domain.sum()),'occupied_tp':tp,'occupied_fp':fp,'occupied_fn_including_unobserved':fn,
      'known_free_tn':tn,'occupied_precision':tp/(tp+fp) if tp+fp else None,
      'occupied_recall_full_truth_domain':tp/(tp+fn) if tp+fn else None,
      'occupied_iou_full_truth_domain':tp/(tp+fp+fn) if tp+fp+fn else None,
      'limitations':['Missing/unknown estimates count as missed occupied truth cells in full-domain recall.',
                     'Raw occupancy -1 preserved; no inference from ambiguous PGM gray values.',
                     'The start odom/world relation is specific to this simulator; no physical-map alignment claim.',
                     'Metrics do not establish localization or navigation acceptance.']}
    import cv2
    gt_boundary=gocc&~cv2.erode(gocc.astype('uint8'),np.ones((3,3),dtype='uint8')).astype(bool)
    est_boundary=eocc&~cv2.erode(eocc.astype('uint8'),np.ones((3,3),dtype='uint8')).astype(bool)
    if gt_boundary.any() and est_boundary.any():
        dt_gt=cv2.distanceTransform((~gt_boundary).astype('uint8'),cv2.DIST_L2,cv2.DIST_MASK_PRECISE)*gt['resolution']
        dt_est=cv2.distanceTransform((~est_boundary).astype('uint8'),cv2.DIST_L2,cv2.DIST_MASK_PRECISE)*gt['resolution']
        a=dt_gt[est_boundary&domain];b=dt_est[gt_boundary]
        report['boundary_distances_m']={'estimate_to_truth_mean':float(a.mean()),'estimate_to_truth_p95':float(np.quantile(a,.95)),
          'truth_to_estimate_mean':float(b.mean()),'truth_to_estimate_p95':float(np.quantile(b,.95)),
          'note':'Additional descriptive distances; no new pass threshold or optimized alignment.'}
    return report,truth,aligned


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--truth',type=Path,required=True);p.add_argument('--estimate',type=Path,required=True)
    p.add_argument('--initial',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r,_,_=compare(a.truth,a.estimate,a.initial)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
