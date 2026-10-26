#!/usr/bin/env bash
# Run with: source scripts/configure_model_session.sh
# Input is held in this terminal's environment, not written to a file.
read -r -p 'OpenAI兼容API地址（LLM_BASE_URL）: ' LLM_BASE_URL
read -r -p '模型名称（LLM_MODEL）: ' LLM_MODEL
read -r -s -p 'API密钥（输入不回显）: ' LLM_API_KEY
echo
export LLM_BASE_URL LLM_MODEL LLM_API_KEY
echo '三个变量已在本终端设置；密钥未写入项目。完成后可 unset LLM_API_KEY。'
