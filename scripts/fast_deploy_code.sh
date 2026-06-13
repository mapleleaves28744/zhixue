#!/usr/bin/env bash
# 仅同步业务代码到运行中容器，避免重装 torch / npm ci。
# 用法（在服务器项目根目录）:
#   ./scripts/fast_deploy_code.sh              # backend + worker + frontend
#   ./scripts/fast_deploy_code.sh backend      # 只更新 Python 服务
#   ./scripts/fast_deploy_code.sh frontend     # 只重建前端应用层（复用 deps 缓存）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="${ROOT}/docker-compose.prod.yml"
TARGET="${1:-all}"

log() { echo "[fast-deploy] $*"; }

sync_backend() {
  log "同步 backend/app → zhixue-backend / zhixue-worker"
  docker cp "${ROOT}/backend/app/." zhixue-backend:/app/app/
  docker cp "${ROOT}/backend/app/." zhixue-worker:/app/app/
  log "重启 backend worker"
  docker compose -f "${COMPOSE_FILE}" restart backend worker
  log "检查 worker 关键依赖 moviepy"
  docker exec zhixue-worker python -c "import moviepy" 2>/dev/null \
    || docker exec zhixue-worker pip install -q 'moviepy>=2.0.0'
}

build_frontend_app_layer() {
  log "同步 stitch-pages → frontend 容器 public 目录"
  docker cp "${ROOT}/frontend/public/stitch-pages/." zhixue-frontend:/app/public/stitch-pages/ 2>/dev/null || true
  log "仅重建 frontend 应用层（deps 层走 Docker 缓存，不装 torch）"
  docker compose -f "${COMPOSE_FILE}" build frontend
  docker compose -f "${COMPOSE_FILE}" up -d --no-deps frontend
  docker compose -f "${COMPOSE_FILE}" restart nginx 2>/dev/null || true
}

case "${TARGET}" in
  backend)
    sync_backend
    ;;
  frontend)
    build_frontend_app_layer
    ;;
  all)
    sync_backend
    build_frontend_app_layer
    ;;
  *)
    echo "未知目标: ${TARGET}（backend | frontend | all）" >&2
    exit 1
    ;;
esac

log "完成。backend 健康检查:"
curl -sf http://127.0.0.1/api/v1/health >/dev/null && echo "  OK" || echo "  等待 backend 启动…"
