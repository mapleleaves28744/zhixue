#!/usr/bin/env python3
"""从远程演示服务器拉取 PostgreSQL 并配置本地开发环境。

队友或 AI 助手一键用法（PowerShell）:

  $env:ZHIXUE_SSH_PASSWORD='向负责人索取，勿提交 git'
  python scripts/sync_dev_from_server.py

可选:
  python scripts/sync_dev_from_server.py --skip-restore   # 只下载 dump
  python scripts/sync_dev_from_server.py --with-storage   # 同步 storage/uploads（可能较大）
  python scripts/sync_dev_from_server.py --dump-only data/zhixue.dump

前置: 本机已安装 PostgreSQL 客户端（pg_dump/pg_restore/psql 在 PATH 或默认安装路径）。
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

try:
    import paramiko
except ImportError:
    print("缺少 paramiko，请先执行: pip install paramiko", file=sys.stderr)
    raise SystemExit(1)

HOST = os.environ.get("ZHIXUE_DEPLOY_HOST", "49.235.190.234")
USER = os.environ.get("ZHIXUE_DEPLOY_USER", "ubuntu")
PASSWORD = os.environ.get("ZHIXUE_SSH_PASSWORD", "")
REMOTE_DIR = "/home/ubuntu/zhixue"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DUMP = ROOT / "data" / "zhixue-remote.dump"
ENV_EXAMPLE = ROOT / ".env.example"
ENV_FILE = ROOT / ".env"

PG_BIN_CANDIDATES = [
    Path(r"C:\Program Files\PostgreSQL\17\bin"),
    Path(r"C:\Program Files\PostgreSQL\16\bin"),
    Path(r"C:\Program Files\PostgreSQL\15\bin"),
    Path(r"C:\Program Files\PostgreSQL\14\bin"),
]
PG_TOOLS = ("pg_restore", "psql")


def configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def read_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.is_file():
        return data
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def parse_database_url(url: str) -> dict[str, str]:
    normalized = re.sub(r"^postgresql\+asyncpg://", "postgresql://", url)
    parsed = urlparse(normalized)
    return {
        "user": unquote(parsed.username or "zhixue"),
        "password": unquote(parsed.password or "zhixue_password"),
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 5432),
        "dbname": unquote(parsed.path.lstrip("/") or "zhixue"),
    }


def find_pg_tool(name: str) -> Path | None:
    found = shutil.which(name)
    if found:
        return Path(found)
    for base in PG_BIN_CANDIDATES:
        candidate = base / f"{name}.exe"
        if candidate.is_file():
            return candidate
        candidate = base / name
        if candidate.is_file():
            return candidate
    return None


def run_local(cmd: list[str], *, env: dict[str, str] | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    print(f"    $ {' '.join(cmd)}")
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(detail or f"命令失败: {cmd[0]}")
    return result


def ssh_run(client: paramiko.SSHClient, cmd: str, *, timeout: int = 1800) -> tuple[int, str, str]:
    _, stdout, stderr = client.exec_command(f"bash -lc {repr(cmd)}", timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return stdout.channel.recv_exit_status(), out, err


def remote_pg_dump(client: paramiko.SSHClient, remote_dump: str) -> None:
    script = f"""
set -euo pipefail
cd {REMOTE_DIR}
if ! docker ps --format '{{{{.Names}}}}' | grep -qx zhixue-postgres; then
  echo "容器 zhixue-postgres 未运行" >&2
  exit 1
fi
docker exec zhixue-postgres pg_dump -U zhixue -d zhixue --no-owner --no-acl -Fc -f /tmp/zhixue-remote.dump
docker cp zhixue-postgres:/tmp/zhixue-remote.dump {remote_dump}
docker exec zhixue-postgres rm -f /tmp/zhixue-remote.dump
ls -lh {remote_dump}
echo REMOTE_DUMP_OK
"""
    code, out, err = ssh_run(client, script, timeout=1800)
    print(out)
    if code != 0:
        raise RuntimeError(err.strip() or "远程 pg_dump 失败")


def download_file(sftp: paramiko.SFTPClient, remote_path: str, local_path: Path) -> None:
    local_path.parent.mkdir(parents=True, exist_ok=True)
    size = sftp.stat(remote_path).st_size
    print(f"    下载 {remote_path} ({size / 1024 / 1024:.1f} MB) -> {local_path}")
    sftp.get(remote_path, str(local_path))


def ensure_local_env() -> dict[str, str]:
    if not ENV_FILE.is_file():
        if not ENV_EXAMPLE.is_file():
            raise RuntimeError("缺少 .env 与 .env.example")
        shutil.copy(ENV_EXAMPLE, ENV_FILE)
        print(f"==> 已从 .env.example 创建 {ENV_FILE.name}")

    lines = ENV_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    replacements = {
        "DATABASE_URL": "postgresql+asyncpg://zhixue:zhixue_password@localhost:5432/zhixue",
        "REDIS_URL": "redis://localhost:6379/0",
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
        "REDIS_HOST": "localhost",
        "REDIS_PORT": "6379",
        "NEXT_PUBLIC_API_BASE_URL": "http://localhost:8000/api/v1",
        "APP_ENV": "development",
        "DEBUG": "true",
    }
    seen: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        if "=" in line and not line.lstrip().startswith("#"):
            key = line.split("=", 1)[0].strip()
            if key in replacements:
                new_lines.append(f"{key}={replacements[key]}")
                seen.add(key)
                continue
        new_lines.append(line)
    for key, value in replacements.items():
        if key not in seen:
            new_lines.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print("==> 已写入本地开发 .env（localhost PostgreSQL / Redis）")
    return read_env_file(ENV_FILE)


def ensure_local_database(conn: dict[str, str]) -> None:
    psql = find_pg_tool("psql")
    if psql is None:
        print("[WARN] 未找到 psql，跳过建库；请手动创建用户 zhixue 与数据库 zhixue")
        return

    env = os.environ.copy()
    env["PGPASSWORD"] = conn["password"]
    admin_url = os.environ.get(
        "ZHIXUE_PG_ADMIN_URL",
        f"postgresql://postgres@{conn['host']}:{conn['port']}/postgres",
    )
    admin = parse_database_url(admin_url)
    if admin.get("password"):
        env["PGPASSWORD"] = admin["password"]

    admin_base = [
        str(psql),
        "-h",
        admin["host"],
        "-p",
        admin["port"],
        "-U",
        admin["user"],
        "-d",
        "postgres",
        "-v",
        "ON_ERROR_STOP=1",
        "-c",
    ]
    print("==> 确保本地 PostgreSQL 用户与数据库存在 ...")
    run_local(admin_base + [f"DO $$ BEGIN CREATE USER {conn['user']} WITH PASSWORD '{conn['password']}'; EXCEPTION WHEN duplicate_object THEN NULL; END $$;"], env=env, check=False)
    run_local(admin_base + [f"ALTER USER {conn['user']} WITH PASSWORD '{conn['password']}';"], env=env, check=False)
    run_local(admin_base + [f"SELECT 1 FROM pg_database WHERE datname = '{conn['dbname']}'"], env=env, check=False)
    run_local(admin_base + [f"CREATE DATABASE {conn['dbname']} OWNER {conn['user']};"], env=env, check=False)

    env["PGPASSWORD"] = conn["password"]
    run_local(
        [
            str(psql),
            "-h",
            conn["host"],
            "-p",
            conn["port"],
            "-U",
            conn["user"],
            "-d",
            conn["dbname"],
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            "CREATE EXTENSION IF NOT EXISTS vector;",
        ],
        env=env,
        check=False,
    )


def restore_local_database(dump_path: Path, conn: dict[str, str]) -> None:
    pg_restore = find_pg_tool("pg_restore")
    psql = find_pg_tool("psql")
    if pg_restore is None:
        raise RuntimeError("未找到 pg_restore，请安装 PostgreSQL 客户端")

    env = os.environ.copy()
    env["PGPASSWORD"] = conn["password"]

    if psql is not None:
        print("==> 断开现有连接并重建数据库 ...")
        admin_url = os.environ.get(
            "ZHIXUE_PG_ADMIN_URL",
            f"postgresql://postgres@{conn['host']}:{conn['port']}/postgres",
        )
        admin = parse_database_url(admin_url)
        admin_env = env.copy()
        if admin.get("password"):
            admin_env["PGPASSWORD"] = admin["password"]
        admin_base = [str(psql), "-h", admin["host"], "-p", admin["port"], "-U", admin["user"], "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c"]
        run_local(
            admin_base
            + [
                f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{conn['dbname']}' AND pid <> pg_backend_pid();"
            ],
            env=admin_env,
            check=False,
        )
        run_local(admin_base + [f"DROP DATABASE IF EXISTS {conn['dbname']};"], env=admin_env, check=False)
        run_local(admin_base + [f"CREATE DATABASE {conn['dbname']} OWNER {conn['user']};"], env=admin_env, check=False)
        run_local(
            [str(psql), "-h", conn["host"], "-p", conn["port"], "-U", conn["user"], "-d", conn["dbname"], "-c", "CREATE EXTENSION IF NOT EXISTS vector;"],
            env=env,
            check=False,
        )

    print("==> pg_restore 导入本地数据库 ...")
    cmd = [
        str(pg_restore),
        "-h",
        conn["host"],
        "-p",
        conn["port"],
        "-U",
        conn["user"],
        "-d",
        conn["dbname"],
        "--no-owner",
        "--no-acl",
        str(dump_path),
    ]
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode not in (0, 1):
        raise RuntimeError((result.stderr or result.stdout or "").strip() or "pg_restore 失败")
    print("    导入完成（pg_restore 警告可忽略）")


def sync_storage(client: paramiko.SSHClient) -> None:
    remote_tar = "/tmp/zhixue-storage-sync.tar.gz"
    local_storage = ROOT / "storage"
    local_storage.mkdir(parents=True, exist_ok=True)
    script = f"""
set -euo pipefail
cd {REMOTE_DIR}
if [ -d storage ] && [ "$(ls -A storage 2>/dev/null)" ]; then
  tar -czf {remote_tar} storage
  ls -lh {remote_tar}
  echo STORAGE_TAR_OK
else
  echo "服务器无 storage 目录，跳过"
fi
"""
    code, out, err = ssh_run(client, script, timeout=1800)
    print(out)
    if code != 0:
        raise RuntimeError(err.strip() or "打包 storage 失败")
    if "STORAGE_TAR_OK" not in out:
        return

    sftp = client.open_sftp()
    local_tar = ROOT / "data" / "zhixue-storage-sync.tar.gz"
    try:
        download_file(sftp, remote_tar, local_tar)
    finally:
        sftp.close()
        ssh_run(client, f"rm -f {remote_tar}")

    print("==> 解压 storage 到项目根目录 ...")
    run_local(["tar", "-xzf", str(local_tar), "-C", str(ROOT)], check=True)
    local_tar.unlink(missing_ok=True)


def run_alembic() -> None:
    backend = ROOT / "backend"
    if not backend.is_dir():
        return
    venv_python = backend / ".venv" / "Scripts" / "python.exe"
    python = str(venv_python) if venv_python.is_file() else sys.executable
    print("==> alembic upgrade head ...")
    result = subprocess.run(
        [python, "-m", "alembic", "upgrade", "head"],
        cwd=backend,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.stdout.strip():
        print(result.stdout)
    if result.returncode != 0:
        print("[WARN] alembic 未成功，请手动在 backend 目录执行: python -m alembic upgrade head")
        if result.stderr.strip():
            print(result.stderr)


def print_next_steps() -> None:
    print(
        """
[OK] 本地开发环境已对齐演示服务器数据库。

下一步:
  1. 确认本机 Redis 已启动 (localhost:6379)
  2. 后端:
       cd backend
       python -m venv .venv
       .venv\\Scripts\\activate
       pip install -r requirements.txt
       uvicorn app.main:app --reload
  3. 前端:
       cd frontend
       npm install
       npm run dev
  4. 浏览器打开 http://localhost:3000 ，登录 stu_01 / 123456

LLM Key 请自行写入 .env，勿从服务器复制密钥。
"""
    )


def main() -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description="从远程演示服务器同步 PostgreSQL 到本地开发环境")
    parser.add_argument("--skip-restore", action="store_true", help="只下载 dump，不导入本地库")
    parser.add_argument("--skip-env", action="store_true", help="不修改 .env")
    parser.add_argument("--with-storage", action="store_true", help="同步服务器 storage/ 上传文件")
    parser.add_argument("--dump-only", type=Path, default=DEFAULT_DUMP, help="本地 dump 保存路径")
    args = parser.parse_args()

    if not PASSWORD:
        print("请设置环境变量 ZHIXUE_SSH_PASSWORD（向项目负责人索取，勿提交 git）", file=sys.stderr)
        return 1

    remote_dump = "/home/ubuntu/zhixue-remote.dump"
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        print(f"==> 连接 {HOST} ...")
        client.connect(HOST, username=USER, password=PASSWORD, timeout=30)

        print("==> 远程 PostgreSQL 导出 ...")
        remote_pg_dump(client, remote_dump)

        sftp = client.open_sftp()
        try:
            download_file(sftp, remote_dump, args.dump_only)
        finally:
            sftp.close()
        ssh_run(client, f"rm -f {remote_dump}")
        print(f"    本地 dump: {args.dump_only}")

        if args.with_storage:
            print("==> 同步 storage ...")
            sync_storage(client)

        if args.skip_restore:
            print("[OK] 已下载 dump，未导入。手动导入:")
            print(f"    pg_restore -U zhixue -d zhixue --no-owner --no-acl {args.dump_only}")
            return 0

        env = read_env_file(ENV_FILE) if args.skip_env else ensure_local_env()
        conn = parse_database_url(env.get("DATABASE_URL", "postgresql+asyncpg://zhixue:zhixue_password@localhost:5432/zhixue"))
        ensure_local_database(conn)
        restore_local_database(args.dump_only, conn)
        run_alembic()
        print_next_steps()
        return 0
    except Exception as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
