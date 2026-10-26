#!/usr/bin/env python3
"""Load private local config into process env, then invoke one course module."""
import json
import os
import runpy
import stat
import sys
from pathlib import Path

root=Path(__file__).resolve().parents[1]
p=root/'config/model.local.json'
if p.exists():
    s=p.stat()
    if stat.S_IMODE(s.st_mode)&0o077:raise SystemExit('模型配置权限过宽；请运行chmod600或重新运行配置脚本')
    config=json.loads(p.read_text())
    for name in ('LLM_BASE_URL','LLM_MODEL','LLM_API_KEY'):
        if name not in os.environ and config.get(name):os.environ[name]=config[name]
if len(sys.argv)<2 or not sys.argv[1].startswith('course_audit.'):
    raise SystemExit('usage: python3 scripts/with_model_config.py course_audit.MODULE [args]')
sys.path.insert(0,str(root/'src'))
module=sys.argv[1];sys.argv=[module]+sys.argv[2:]
runpy.run_module(module,run_name='__main__')
