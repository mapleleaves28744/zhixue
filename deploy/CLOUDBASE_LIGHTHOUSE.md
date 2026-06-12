# CloudBase 轻量应用服务器部署说明

## 为什么用轻量应用服务器

智学工坊依赖 **PostgreSQL（pgvector）+ Redis + arq Worker + FastAPI + Next.js**，是一套完整 Docker 栈。CloudBase 云托管/静态托管适合拆分的 Serverless 场景，而 **轻量应用服务器（Lighthouse）** 可以一次性跑 `docker-compose.prod.yml`，与项目现有架构最匹配。

## 前置条件

1. CloudBase 环境已绑定（当前：`jiaoyuagent-2gbbi3sddc043643`）
2. 已创建轻量应用服务器，推荐：
   - **2 核 4GB** 或以上
   - 镜像选 **Ubuntu** 或 **Docker 容器镜像**
3. 防火墙放行 **TCP 80**（如需 HTTPS 再放行 443）

控制台入口：[轻量应用服务器](https://tcb.cloud.tencent.com/dev/lighthouse)

## 部署步骤

### 1. SSH 登录服务器

在 CloudBase 控制台 → 轻量应用服务器 → 管理 → 获取 SSH 登录方式。

### 2. 安装 Docker（若镜像未预装）

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# 重新登录 SSH 后生效
```

### 3. 上传代码

```bash
git clone <你的仓库地址> zhixue
cd zhixue
```

或使用 `scp`/SFTP 上传整个项目目录。

### 4. 配置环境变量

```bash
cp .env.example .env
nano .env
```

至少修改：

| 变量 | 说明 |
|------|------|
| `JWT_SECRET` | 随机长字符串 |
| `POSTGRES_PASSWORD` | 数据库密码 |
| `LLM_PROVIDER` / `LLM_API_KEY` | 真实大模型（演示可保持 `mock`） |
| `PUBLIC_HOST` | 部署脚本用，设为公网 IP 或域名 |

`docker-compose.prod.yml` 会自动把 `DATABASE_URL`、`REDIS_URL` 指向 compose 内的 postgres/redis，**无需单独购买云数据库**。

### 5. 一键部署

```bash
chmod +x scripts/deploy-lighthouse.sh
# 可选：export PUBLIC_HOST=你的公网IP
./scripts/deploy-lighthouse.sh
```

### 6. 验证

```bash
curl http://127.0.0.1/health
curl http://127.0.0.1/api/v1/...
```

浏览器访问：`http://<公网IP>/`

## 服务架构

```text
Internet :80
    └── nginx
          ├── /        → frontend (Next.js :3000)
          └── /api/*   → backend (FastAPI :8000)
postgres + redis + arq worker（内网，不对外暴露）
```

## 与 CloudBase MCP 的关系

| 能力 | MCP 工具 | 本方案 |
|------|----------|--------|
| 环境查询 | `envQuery` | 已绑定 `jiaoyuagent` |
| 云托管 | `manageCloudRun` | 可选，需外接 PG/Redis |
| 静态托管 | `manageHosting` | 仅适合纯前端 |
| **轻量服务器** | **无 SSH 工具** | **SSH + docker-compose（推荐）** |

MCP 目前不能直接 SSH 到轻量服务器，因此 **在服务器上执行 `deploy-lighthouse.sh`** 是最稳妥路径。

## 可选：仅前端上 CloudBase 静态托管

若后端已在轻量服务器，可把 `frontend` 构建产物上传到静态托管，并通过 URL 参数指定 API：

```text
https://<cdn-domain>/assistant?api_base=http%3A%2F%2F<后端IP>%2Fapi%2Fv1
```

前端已支持 `api_base` 运行时覆盖（见 `frontend/lib/api.ts`）。

## 故障排查

| 现象 | 处理 |
|------|------|
| 外网无法访问 | 检查 Lighthouse 防火墙是否放行 80 |
| `/health` 失败 | `docker compose -f docker-compose.prod.yml logs backend` |
| Agent 一直排队 | 确认 `zhixue-worker` 容器在运行 |
| 迁移失败 | `docker compose -f docker-compose.prod.yml exec backend alembic upgrade head` |
