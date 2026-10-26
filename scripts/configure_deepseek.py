#!/usr/bin/env python3
"""Locally enter credentials without chat, terminal history, or echo."""
import getpass
import json
import os
from pathlib import Path

root=Path(__file__).resolve().parents[1]
path=root/'config/model.local.json'
base=input('API地址 [https://api.deepseek.com]: ').strip() or 'https://api.deepseek.com'
model=input('模型 [deepseek-flash]: ').strip() or 'deepseek-flash'
key=getpass.getpass('API密钥（不回显）: ').strip()
if not key:raise SystemExit('未输入密钥；没有保存')
fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
os.fchmod(fd,0o600)
with os.fdopen(fd,'w') as f:
    json.dump({'LLM_BASE_URL':base,'LLM_MODEL':model,'LLM_API_KEY':key},f)
print('已保存本机配置（仅当前用户可读）；请在聊天中回复“已配置”，不要发送密钥。')
