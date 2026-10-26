"""Strict semantic JSON -> auditor fields; ambiguous class names fail closed."""
import math
from .semantic_registration import timestamp


def semantic_world_fields(document):
    """Preserve every target or reject; never silently overwrite duplicate labels.

    Class-only duplicate labels require explicit target names. Frame registration
    supplies unique map names; this conversion preserves them and never infers
    object identity from a class label.
    """
    if document.get('frame_id')!='map':
        raise ValueError('semantic target frame must be map')
    now=timestamp(document['generated_at']).timestamp()
    items={};tau={}
    for row in document['items']:
        label=row.get('target_name',row['label'])
        if not isinstance(label,str) or not label.strip():
            raise ValueError('semantic target requires a nonempty label')
        if label in items:
            raise ValueError(f'ambiguous semantic label {label}: multiple targets require explicit unique names')
        values=[row['x'],row['y'],row['tau_s']]
        if not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in values) or row['tau_s']<=0:
            raise ValueError('semantic coordinates and tau must be finite; tau must be positive')
        if not row.get('tau_evidence_id') or not row.get('evidence_ids'):
            raise ValueError('semantic target and tau must cite source evidence')
        items[label]={'x_m':row['x'],'y_m':row['y'],
                      'last_seen_s':timestamp(row['last_seen']).timestamp()}
        tau[label]=row['tau_s']
    return {'now_s':now,'semantic_items':items,'tau_s':tau}
