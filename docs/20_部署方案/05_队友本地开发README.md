# 智学工坊 · 队友本地开发 README

> 从拉代码到和演示服务器一致的数据库，按本文顺序操作即可。  
> 演示服务器：http://49.235.190.234/  
> 仓库：https://github.com/mapleleaves28744/zhixue

---

## 你需要什么

| 软件 | 说明 |
|------|------|
| Git | 拉代码 |
| Python 3.11+ | 后端 |
| Node.js 18+ | 前端 |
| PostgreSQL 17（或 16+） | **本地数据库**，安装时勾选 **Command Line Tools**（含 `psql` / `pg_restore`） |
| Redis 7 | 任务队列与缓存 |

数据库类型：**PostgreSQL + pgvector**（与线上一致，不是 MySQL / SQLite）。

---

## 第一步：克隆代码

```powershell
git clone https://github.com/mapleleaves28744/zhixue.git
cd zhixue
git pull origin main
```

> 若 `main` 尚未包含 `scripts/sync_dev_from_server.py`，临时使用：`git checkout change_3 && git pull origin change_3`。

---

## 第二步：确认本机 PostgreSQL / Redis 已启动

```powershell
# PostgreSQL（默认 5432）
Get-Service *postgres*

# Redis（默认 6379）
redis-cli ping
# 应返回 PONG
```

Windows 若无 Redis，可用 [Memurai](https://www.memurai.com/) 或 WSL 安装 Redis。

---

## 第三步：从演示服务器同步数据库（重要）

线上 Wiki、资料切片、演示账号等都在 PostgreSQL 里。请**把 dump 拉到本机导入**，不要长期直连远程数据库。

向项目负责人索取 **SSH 密码**（仅通过环境变量使用，**勿提交 git**）。

```powershell
cd zhixue

pip install paramiko

$env:ZHIXUE_SSH_PASSWORD='向负责人索取'

python scripts/sync_dev_from_server.py
```

脚本会自动：

1. SSH 连接 `49.235.190.234`
2. 在 Docker 容器 `zhixue-postgres` 内执行 `pg_dump`
3. 下载到 `data/zhixue-remote.dump`
4. 若无 `.env`，从 `.env.example` 生成本地配置（`localhost` PostgreSQL / Redis）
5. 重建本地 `zhixue` 库并 `pg_restore` 导入
6. 尝试执行 `alembic upgrade head`

**可选参数：**

```powershell
# 连同上传文件 storage 一起同步（可能较大）
python scripts/sync_dev_from_server.py --with-storage

# 只下载 dump，不导入
python scripts/sync_dev_from_server.py --skip-restore
```

**若建库失败**，用 pgAdmin 或 `psql` 手动执行：

```sql
CREATE USER zhixue WITH PASSWORD 'zhixue_password';
CREATE DATABASE zhixue OWNER zhixue;
```

然后重新运行同步脚本。

---

## 第四步：配置 LLM（按需）

编辑项目根目录 `.env`：

**无 API Key（可跑普通生成主链路，Mock 模式）：**

```env
LLM_PROVIDER=mock
EMBEDDING_PROVIDER=mock
```

> 当前 `/assistant` LangGraph Agent Runtime 不允许 Mock fallback。以上配置可用于普通 Tutor、Wiki、资源、练习和诊断等 Mock 链路，但智能体模式仍需真实 Provider。

**使用 OpenAI-compatible 大模型（示例）：**

```env
LLM_PROVIDER=compatible
LLM_BASE_URL=https://api.xiaomimimo.com/v1
LLM_API_KEY=你的密钥
LLM_MODEL_NAME=mimo-v2.5-pro
EMBEDDING_PROVIDER=mock
```

> 脚本不会从服务器复制 API Key，需自行配置。

本地数据库连接应类似：

```env
DATABASE_URL=postgresql+asyncpg://zhixue:zhixue_password@localhost:5432/zhixue
REDIS_URL=redis://localhost:6379/0
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
```

---

## 第五步：启动服务

### 方式 A：一键启动（推荐演示 / Agent 联调）

```powershell
cd zhixue
scripts/start_phase31_demo.ps1
```

会同时启动：FastAPI（8000）、arq Worker、Next.js（3000）。

### 方式 B：手动分终端启动

**终端 1 — 后端：**

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**终端 2 — Agent Worker（`/assistant` 智能体必需）：**

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m arq app.workers.agent_worker.WorkerSettings
```

**终端 3 — 前端：**

```powershell
cd frontend
npm install
npm run dev -- --hostname 127.0.0.1 --port 3000
```

---

## 第六步：登录验证

| 项目 | 值 |
|------|-----|
| 前端地址 | http://127.0.0.1:3000 |
| 后端健康检查 | http://127.0.0.1:8000/health |
| 演示账号 | `stu_01` |
| 密码 | `123456` |

检查清单：

- [ ] 课程 / Wiki / 练习页显示**真实数据**（不是 Stitch 占位文案）
- [ ] 浏览器 Network 中 API 指向 `localhost:8000`
- [ ] `/health` 返回 `{"status":"ok",...}`

---

## 数据更新

演示环境数据有更新时，重新同步：

```powershell
$env:ZHIXUE_SSH_PASSWORD='密码'
python scripts/sync_dev_from_server.py
```

---

## 给 AI 助手的提示词（复制即用）

```text
我在 Windows 上开发智学工坊。请阅读 docs/20_部署方案/05_队友本地开发README.md，依次完成：
1. git pull origin main（确认存在 scripts/sync_dev_from_server.py）
2. pip install paramiko 后执行 python scripts/sync_dev_from_server.py（SSH 密码我提供）
3. 启动 backend、arq worker、frontend
4. 用 stu_01 / 123456 验证 http://localhost:3000
```

---

## 常见问题

| 问题 | 处理 |
|------|------|
| `找不到 scripts/sync_dev_from_server.py` | 你 clone 的可能是旧 `main`，执行 `git pull origin main`；仍没有则 `git checkout change_3` |
| SSH 进服务器后 `postgresql.service` 不存在 | **正常**。演示库在 Docker 容器 `zhixue-postgres` 里，用 `docker exec -it zhixue-postgres psql -U zhixue -d zhixue` 检查 |
| `未找到 pg_restore` | 重装 PostgreSQL 并勾选 Command Line Tools；或将 `C:\Program Files\PostgreSQL\17\bin` 加入 PATH |
| `Redis connection refused` | 启动本机 Redis |
| 页面仍是占位数据（24 文档、高等数学等） | 重新登录；确认后端已启动；检查 `.env` 中 `NEXT_PUBLIC_API_BASE_URL`；清 `localStorage` 中 `zhixue_api_base` |
| SSH / paramiko 失败 | 向负责人确认密码；确认能访问 `49.235.190.234` |
| 端口被占用 | `Get-NetTCPConnection -LocalPort 3000,8000` 查 PID，`Stop-Process -Id <PID> -Force` |
| 只想改前端 UI | 可不跑同步；`frontend/.env.local` 设 `NEXT_PUBLIC_API_BASE_URL=http://49.235.190.234/api/v1`，只跑 `npm run dev` |

---

## 相关文档

- 详细启动说明：`docs/20_部署方案/04_本地开发启动指南.md`
- 部署总览：`docs/20_部署方案/20_部署方案.md`
- 项目主 README：`README.md`

---

## 安全提醒

- **不要**把 `ZHIXUE_SSH_PASSWORD`、`.env`、JWT Secret、LLM API Key 提交到 GitHub
- **不要**把 PostgreSQL 5432 端口暴露到公网
- 日常开发用**本地库**；演示服务器仅用于同步 dump 或纯前端联调 API
