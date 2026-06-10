#!/usr/bin/env bash
# 智学工坊 — 轻量应用服务器一键部署脚本
# 在 Ubuntu + Docker 的轻量应用服务器上执行

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "==> 检查 Docker..."
if ! command -v docker >/dev/null 2>&1; then
  echo "未检测到 Docker，请先安装 Docker 与 Compose 插件。"
  exit 1
fi

if [ ! -f .env ]; then
  echo "==> 从 .env.example 创建 .env（请随后编辑密钥与 LLM 配置）"
  cp .env.example .env
  # 生产默认值
  sed -i 's/^APP_ENV=development/APP_ENV=production/' .env || true
  sed -i 's/^DEBUG=true/DEBUG=false/' .env || true
  sed -i 's|^NEXT_PUBLIC_API_BASE_URL=.*|NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1/api/v1|' .env || true
  sed -i 's|^BACKEND_CORS_ORIGINS=.*|BACKEND_CORS_ORIGINS=http://127.0.0.1,http://localhost|' .env || true
fi

# 若已知公网 IP/域名，可写入 CORS 与前端 API 地址
if [ -n "${PUBLIC_HOST:-}" ]; then
  echo "==> 使用 PUBLIC_HOST=$PUBLIC_HOST 更新 CORS 与 NEXT_PUBLIC_API_BASE_URL"
  sed -i "s|^NEXT_PUBLIC_API_BASE_URL=.*|NEXT_PUBLIC_API_BASE_URL=http://${PUBLIC_HOST}/api/v1|" .env
  sed -i "s|^BACKEND_CORS_ORIGINS=.*|BACKEND_CORS_ORIGINS=http://${PUBLIC_HOST},http://127.0.0.1,http://localhost|" .env
fi

echo "==> 构建并启动服务（首次可能需 5–15 分钟）..."
docker compose -f docker-compose.prod.yml up -d --build

echo "==> 等待健康检查..."
sleep 8
curl -sf "http://127.0.0.1/health" && echo "" || echo "警告: /health 暂未就绪，请稍后重试"

echo ""
echo "部署完成。访问: http://<你的公网IP>/"
echo "API 文档: http://<你的公网IP>/docs"
echo ""
echo "请在轻量应用服务器防火墙中放行 TCP 80 端口。"
