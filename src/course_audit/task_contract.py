"""Explicit task contract: validate ordered steps without inferring or repairing intent."""
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TaskContract:
    required_sequence: tuple[str, ...]
    navigation_labels: tuple[str, ...] = ()
    unavailable_tools: tuple[str, ...] = ()
    evidence_id: str = ''

    @classmethod
    def from_mapping(cls, value):
        seq=value['required_sequence'];labels=value.get('navigation_labels',[])
        unavailable=value.get('unavailable_tools',[])
        if (not all(isinstance(v,(list,tuple)) for v in (seq,labels,unavailable)) or
                not seq or not all(isinstance(x,str) and x for x in [*seq,*labels,*unavailable])):
            raise ValueError('task contract requires explicit nonempty tool names and labels')
        if not value.get('evidence_id'):raise ValueError('task contract requires a source evidence_id')
        return cls(tuple(seq),tuple(labels),tuple(unavailable),value['evidence_id'])

    def check(self,calls:list[dict[str,Any]]) -> dict:
        sequence=[c['name'] for c in calls]
        # Emergency stop remains available even for an abandoned/incomplete task.
        if sequence==['stop']:
            return {'allowed':True,'rule_id':'TASK_SAFE_STOP','reason':'Only safe stop requested; task completion is not claimed.'}
        missing_capabilities=sorted(set(self.required_sequence)&set(self.unavailable_tools))
        if missing_capabilities:
            return {'allowed':False,'rule_id':'TASK_CAPABILITY','reason':'任务需要当前不可用能力：'+','.join(missing_capabilities),
                    'evidence':self.evidence_id,'missing_capabilities':missing_capabilities}
        if sequence!=list(self.required_sequence):
            return {'allowed':False,'rule_id':'TASK_SEQUENCE','reason':'实际工具顺序与显式任务契约不一致；不自动补步骤。',
                    'expected':list(self.required_sequence),'actual':sequence,'evidence':self.evidence_id}
        labels=[c['arguments']['label'] for c in calls if c['name']=='navigate_to']
        if self.navigation_labels and labels!=list(self.navigation_labels):
            return {'allowed':False,'rule_id':'TASK_TARGETS','reason':'导航目标顺序与任务契约不一致。',
                    'expected':list(self.navigation_labels),'actual':labels,'evidence':self.evidence_id}
        return {'allowed':True,'rule_id':'TASK_PASS','reason':'完整步骤和目标顺序符合显式契约。','evidence':self.evidence_id}
