#!/usr/bin/env bash
# 言权后端一键启动脚本
# 用法：bash backend/run.sh（在项目根目录或任意目录均可）
set -e

cd "$(dirname "$0")/.."

if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
  echo "已创建 backend/.env（默认演示模式，无需任何 API Key 即可运行）"
fi

# ---------- 自动选择 Python 环境 ----------
# 优先级：项目 venv > conda rag_env（本项目开发环境）> 系统 python3
PYTHON=""
if [ -f "backend/venv/bin/python" ]; then
  PYTHON="backend/venv/bin/python"
elif [ -x "/opt/anaconda3/envs/rag_env/bin/python" ]; then
  PYTHON="/opt/anaconda3/envs/rag_env/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
fi

echo "使用 Python：$($PYTHON --version 2>&1)"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

exec "$PYTHON" -m uvicorn backend.main:app --host "$HOST" --port "$PORT" --reload
