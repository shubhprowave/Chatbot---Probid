#!/usr/bin/env bash
# Bootstrap the stack on a fresh Linux VPS (Ubuntu).
# No reverse proxy needed: the FastAPI backend serves the API, the React
# chatbot (/) and the admin SPA (/admin/*) itself.
# Run as:  bash setup-vm.sh /opt/probee
set -euo pipefail

APP_DIR="${1:-/opt/probee}"
cd "$APP_DIR"

echo "== 1/5  System packages (python, node, postgres, mysql, redis) =="
sudo apt-get update -y
sudo apt-get install -y python3.13 python3.13-venv nodejs npm \
  postgresql postgresql-contrib redis-server mysql-server

echo "== 2/5  Preparing .env =="
if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
  echo ">>> CREATED backend/.env FROM TEMPLATE. STOP AND EDIT IT:"
  echo "    nano $APP_DIR/backend/.env"
  echo "    (set DATABASE_URL, LLM_API_KEY, ADMIN_TOKEN, REDIS_URL, MySQL creds, CORS_ORIGINS)"
  exit 1
fi

echo "== 3/5  Postgres schema (run once) =="
# Assumes the rag user/db already created; applies extensions + tables.
# sudo -u postgres psql -c "CREATE USER rag WITH PASSWORD '...'; CREATE DATABASE ragdb OWNER rag;"
# sudo -u postgres psql -d ragdb -f backend/db/schema.sql   # needs pgvector installed

echo "== 4/5  Python env =="
python3.13 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install --index-url https://download.pytorch.org/whl/cpu torch
venv/bin/pip install -r backend/requirements.txt

echo "== 5/5  Frontend build (chatbot at /, admin at /admin) =="
cd frontend
npm ci
npm run build
cd "$APP_DIR"

echo "== Starting API (serves API + frontend on :8000) =="
cd backend
nohup "$APP_DIR/venv/bin/python" -m uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/probee-backend.log 2>&1 &

echo ">> Waiting for http://127.0.0.1:8000/health ..."
for i in $(seq 1 60); do
  if curl -s -m 3 http://127.0.0.1:8000/health >/dev/null 2>&1; then
    IP=$(hostname -I 2>/dev/null | awk '{print $1}')
    echo ">>> CHATBOT : http://${IP:-<your-public-ip>}/"
    echo ">>> ADMIN   : http://${IP:-<your-public-ip>}/admin  (ADMIN_TOKEN from backend/.env)"
    echo ">>> API     : http://${IP:-<your-public-ip>}/api/...  (see /docs)"
    exit 0
  fi
  sleep 5
done

echo ">>> Timed out waiting for /health. Debug with:"
echo "    tail -50 /tmp/probee-backend.log"
