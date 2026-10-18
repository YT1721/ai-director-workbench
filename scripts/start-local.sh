#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-6001}"
HOST="${HOST:-127.0.0.1}"
LOG_DIR="$ROOT_DIR/.local-run/logs"

cd "$ROOT_DIR"
mkdir -p "$LOG_DIR"

echo "AI导演工作台｜本地启动"
echo "项目目录：$ROOT_DIR"
echo "后端地址：http://$HOST:$API_PORT"
echo "前端地址：http://$HOST:$WEB_PORT"
echo ""

need_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "缺少命令：$1"
    echo "$2"
    exit 1
  fi
}

port_in_use() {
  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$1" -sTCP:LISTEN -Pn >/dev/null 2>&1
  else
    return 1
  fi
}

if port_in_use "$API_PORT"; then
  echo "端口 $API_PORT 已被占用。"
  echo "如果 AI导演工作台已经启动，请直接打开：http://$HOST:$WEB_PORT"
  echo "否则请关闭占用端口的程序后再双击启动。"
  exit 1
fi

if port_in_use "$WEB_PORT"; then
  echo "端口 $WEB_PORT 已被占用。"
  echo "如果 AI导演工作台已经启动，请直接打开：http://$HOST:$WEB_PORT"
  echo "否则请关闭占用端口的程序后再双击启动。"
  exit 1
fi

need_command "python3" "请先安装 Python 3。"
need_command "npm" "请先安装 Node.js / npm。"

if [ ! -x "$ROOT_DIR/.venv/bin/python" ]; then
  echo "首次启动：创建 Python 虚拟环境..."
  python3 -m venv "$ROOT_DIR/.venv"
fi

if [ ! -x "$ROOT_DIR/.venv/bin/uvicorn" ]; then
  echo "安装后端依赖..."
  "$ROOT_DIR/.venv/bin/python" -m pip install --upgrade pip
  "$ROOT_DIR/.venv/bin/python" -m pip install -r "$ROOT_DIR/apps/api/requirements.txt"
fi

if [ ! -d "$ROOT_DIR/apps/web/node_modules" ]; then
  echo "首次启动：安装前端依赖..."
  npm --prefix apps/web install
fi

if [ ! -f "$ROOT_DIR/.env" ] && [ -f "$ROOT_DIR/.env.example" ]; then
  echo "首次启动：创建本地配置文件 .env"
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
fi

cleanup() {
  echo ""
  echo "正在关闭本地服务..."
  if [ -n "${API_PID:-}" ]; then kill "$API_PID" 2>/dev/null || true; fi
  if [ -n "${WEB_PID:-}" ]; then kill "$WEB_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

echo "启动后端 FastAPI..."
"$ROOT_DIR/.venv/bin/uvicorn" app.main:app \
  --app-dir apps/api \
  --host "$HOST" \
  --port "$API_PORT" \
  --reload \
  > "$LOG_DIR/api.log" 2>&1 &
API_PID=$!

echo "启动前端 Vite..."
npm --prefix apps/web run dev -- --host "$HOST" --port "$WEB_PORT" \
  > "$LOG_DIR/web.log" 2>&1 &
WEB_PID=$!

echo "等待服务就绪..."
for _ in {1..60}; do
  if curl -fsS "http://$HOST:$API_PORT/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

if ! curl -fsS "http://$HOST:$API_PORT/health" >/dev/null 2>&1; then
  echo "后端没有启动成功。请查看日志：$LOG_DIR/api.log"
  exit 1
fi

echo "服务已启动。"
echo "前端日志：$LOG_DIR/web.log"
echo "后端日志：$LOG_DIR/api.log"
echo ""
echo "浏览器地址：http://$HOST:$WEB_PORT"

if command -v open >/dev/null 2>&1; then
  open "http://$HOST:$WEB_PORT" >/dev/null 2>&1 || true
fi

echo ""
echo "保持这个窗口打开即可使用；关闭窗口会停止本地服务。"
wait
