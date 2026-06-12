#!/usr/bin/env python3
"""整包上传本地项目到服务器并 docker compose 部署（可选同步 DB + BGE 模型缓存）。

用法（PowerShell）:
  $env:ZHIXUE_SSH_PASSWORD='你的密码'
  python scripts/deploy.py
  python scripts/deploy.py --skip-db          # 不导入本地 PostgreSQL
  python scripts/deploy.py --skip-models      # 不同步 HuggingFace 缓存

打包时排除 node_modules / .venv / .next 等可重建目录；
可选：pg_dump 本地库 → 导入服务器；同步 BAAI/bge-large-zh-v1.5 模型缓存。
"""
from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

import paramiko

HOST = os.environ.get("ZHIXUE_DEPLOY_HOST", "49.235.190.234")
USER = os.environ.get("ZHIXUE_DEPLOY_USER", "ubuntu")
PASSWORD = os.environ.get("ZHIXUE_SSH_PASSWORD", "")
REMOTE_DIR = "/home/ubuntu/zhixue"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-large-zh-v1.5"

SKIP_DIR_NAMES = {
    ".git",
    "node_modules",
    ".venv",
    "__pycache__",
    ".next",
    ".playwright-mcp",
    "runtime-logs",
}
SKIP_SUFFIX = {".pyc", ".pyo"}

PG_DUMP_CANDIDATES = [
    Path(r"C:\Program Files\PostgreSQL\17\bin\pg_dump.exe"),
    Path(r"C:\Program Files\PostgreSQL\16\bin\pg_dump.exe"),
    Path(r"C:\Program Files\PostgreSQL\15\bin\pg_dump.exe"),
    Path(r"C:\Program Files\PostgreSQL\14\bin\pg_dump.exe"),
    Path("pg_dump"),
]


def should_skip(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in SKIP_DIR_NAMES for part in rel.parts):
        return True
    return path.suffix in SKIP_SUFFIX


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
    """postgresql+asyncpg://user:pass@host:5432/dbname"""
    normalized = re.sub(r"^postgresql\+asyncpg://", "postgresql://", url)
    parsed = urlparse(normalized)
    dbname = parsed.path.lstrip("/") or "zhixue"
    return {
        "user": unquote(parsed.username or "zhixue"),
        "password": unquote(parsed.password or ""),
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 5432),
        "dbname": dbname,
    }


def find_pg_dump() -> Path | None:
    for candidate in PG_DUMP_CANDIDATES:
        if candidate.name == "pg_dump":
            found = shutil.which("pg_dump")
            if found:
                return Path(found)
            continue
        if candidate.is_file():
            return candidate
    return None


def dump_local_database(env: dict[str, str], out_path: Path) -> None:
    db_url = env.get("DATABASE_URL", "")
    if not db_url:
        raise RuntimeError(".env 中缺少 DATABASE_URL")
    pg_dump = find_pg_dump()
    if pg_dump is None:
        raise RuntimeError("未找到 pg_dump，请安装 PostgreSQL 客户端或把 pg_dump 加入 PATH")

    conn = parse_database_url(db_url)
    password = conn["password"] or env.get("POSTGRES_PASSWORD", "zhixue_password")
    env_vars = os.environ.copy()
    env_vars["PGPASSWORD"] = password

    cmd = [
        str(pg_dump),
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
        "-Fc",
        "-f",
        str(out_path),
    ]
    print(f"    pg_dump {conn['host']}:{conn['port']}/{conn['dbname']} ...")
    result = subprocess.run(cmd, env=env_vars, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "pg_dump 失败")
    if not out_path.is_file() or out_path.stat().st_size == 0:
        raise RuntimeError("pg_dump 输出为空")


def pack_hf_model_cache(out_path: Path, model_id: str = DEFAULT_EMBEDDING_MODEL) -> int:
    """只打包指定 embedding 模型目录（不压缩，避免 2.5GB gzip 卡死）。"""
    folder_name = f"models--{model_id.replace('/', '--')}"
    hub = Path.home() / ".cache" / "huggingface" / "hub"
    model_dir = hub / folder_name
    if not model_dir.is_dir():
        raise RuntimeError(f"未找到本地模型缓存: {model_dir}")

    files = [p for p in model_dir.rglob("*") if p.is_file()]
    print(f"    共 {len(files)} 个文件，打包中（不压缩）...")
    count = 0
    # 不 gzip：模型已是二进制，压缩慢且收益小
    with tarfile.open(out_path, "w") as tar:
        for path in files:
            arcname = f"{folder_name}/{path.relative_to(model_dir).as_posix()}"
            tar.add(path, arcname=arcname)
            count += 1
            if count % 20 == 0:
                print(f"    ... {count}/{len(files)}")
    return count


def make_project_tarball() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for path in ROOT.rglob("*"):
            if should_skip(path):
                continue
            arcname = str(path.relative_to(ROOT)).replace("\\", "/")
            if path.is_dir():
                continue
            tar.add(path, arcname=arcname)
    buf.seek(0)
    return buf.read()


def upload_file(sftp: paramiko.SFTPClient, local_path: Path, remote_path: str) -> None:
    size = local_path.stat().st_size
    print(f"    上传 {local_path.name} ({size / 1024 / 1024:.1f} MB) -> {remote_path}")
    with local_path.open("rb") as src, sftp.file(remote_path, "wb") as dst:
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            dst.write(chunk)


def upload_bytes(sftp: paramiko.SFTPClient, data: bytes, remote_path: str) -> None:
    print(f"    上传 {remote_path} ({len(data) / 1024 / 1024:.1f} MB)")
    with sftp.file(remote_path, "wb") as f:
        for i in range(0, len(data), 1024 * 1024):
            f.write(data[i : i + 1024 * 1024])


def run(client: paramiko.SSHClient, cmd: str, *, sudo: bool = False, timeout: int = 3600) -> tuple[int, str, str]:
    wrapped = f"echo '{PASSWORD}' | sudo -S bash -lc {repr(cmd)}" if sudo else f"bash -lc {repr(cmd)}"
    _, stdout, stderr = client.exec_command(wrapped, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return stdout.channel.recv_exit_status(), out, err


def run_script(client: paramiko.SSHClient, script: str, *, sudo: bool = False, timeout: int = 3600) -> tuple[int, str, str]:
    remote = f"/tmp/zhixue_deploy_{int(time.time())}.sh"
    sftp = client.open_sftp()
    with sftp.file(remote, "w") as f:
        f.write("#!/bin/bash\nset -euo pipefail\n")
        f.write(script)
        if not script.endswith("\n"):
            f.write("\n")
    sftp.chmod(remote, 0o755)
    sftp.close()
    try:
        return run(client, f"bash {remote}", sudo=sudo, timeout=timeout)
    finally:
        run(client, f"rm -f {remote}", sudo=sudo, timeout=30)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="整包部署智学工坊到远程服务器")
    parser.add_argument("--skip-db", action="store_true", help="不导入本地 PostgreSQL")
    parser.add_argument("--skip-models", action="store_true", help="不同步 HuggingFace 模型缓存")
    parser.add_argument("--skip-build", action="store_true", help="跳过 docker compose build（仅同步数据）")
    args = parser.parse_args()

    if not PASSWORD:
        print("请设置环境变量 ZHIXUE_SSH_PASSWORD", file=sys.stderr)
        return 1

    env_file = ROOT / ".env"
    env = read_env_file(env_file)
    tmp = Path(tempfile.mkdtemp(prefix="zhixue_deploy_"))
    db_dump = tmp / "zhixue.dump"
    hf_tar = tmp / "hf-bge-cache.tar"

    try:
        if not args.skip_db:
            print("==> 导出本地 PostgreSQL ...")
            try:
                dump_local_database(env, db_dump)
                print(f"    dump 大小: {db_dump.stat().st_size / 1024 / 1024:.1f} MB")
            except Exception as exc:
                print(f"[FAIL] {exc}", file=sys.stderr)
                return 1

        if not args.skip_models:
            print(f"==> 打包 HuggingFace 模型缓存 ({DEFAULT_EMBEDDING_MODEL}) ...")
            try:
                file_count = pack_hf_model_cache(hf_tar)
                print(f"    {file_count} 个文件, {hf_tar.stat().st_size / 1024 / 1024:.1f} MB")
            except Exception as exc:
                print(f"[FAIL] {exc}", file=sys.stderr)
                return 1

        print("==> 打包本地项目（含 .env / storage / data）...")
        tarball = make_project_tarball()
        print(f"    大小: {len(tarball) / 1024 / 1024:.1f} MB")

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        print(f"==> 连接 {HOST} ...")
        client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
        sftp = client.open_sftp()

        remote_tar = "/home/ubuntu/zhixue-full.tar.gz"
        remote_db = "/home/ubuntu/zhixue.dump"
        remote_hf = "/home/ubuntu/hf-bge-cache.tar"

        print("==> 上传文件 ...")
        upload_bytes(sftp, tarball, remote_tar)
        if not args.skip_db and db_dump.is_file():
            upload_file(sftp, db_dump, remote_db)
        if not args.skip_models and hf_tar.is_file():
            upload_file(sftp, hf_tar, remote_hf)
        sftp.close()

        print("==> 解压并写入生产环境连接配置 ...")
        setup = f"""
set -euo pipefail
rm -rf {REMOTE_DIR}
mkdir -p {REMOTE_DIR}
tar -xzf {remote_tar} -C {REMOTE_DIR}
cd {REMOTE_DIR}
mkdir -p storage
if [ -d backend/storage ] && [ "$(ls -A backend/storage 2>/dev/null)" ]; then
  cp -a backend/storage/. storage/ 2>/dev/null || true
fi
if [ ! -f .env ]; then cp .env.example .env; fi
grep -q '^APP_ENV=' .env && sed -i 's/^APP_ENV=.*/APP_ENV=production/' .env || echo APP_ENV=production >> .env
grep -q '^DEBUG=' .env && sed -i 's/^DEBUG=.*/DEBUG=false/' .env || echo DEBUG=false >> .env
sed -i 's|^DATABASE_URL=.*|DATABASE_URL=postgresql+asyncpg://zhixue:zhixue_password@postgres:5432/zhixue|' .env
sed -i 's|^REDIS_URL=.*|REDIS_URL=redis://redis:6379/0|' .env
sed -i 's|^NEXT_PUBLIC_API_BASE_URL=.*|NEXT_PUBLIC_API_BASE_URL=http://{HOST}/api/v1|' .env
sed -i 's|^BACKEND_CORS_ORIGINS=.*|BACKEND_CORS_ORIGINS=http://{HOST},http://127.0.0.1,http://localhost|' .env
grep -q '^output:' frontend/next.config.mjs || sed -i '/reactStrictMode/i\\  output: "standalone",' frontend/next.config.mjs
echo READY
"""
        code, out, err = run_script(client, setup, timeout=300)
        print(out)
        if code != 0:
            print(err, file=sys.stderr)
            client.close()
            return code

        if not args.skip_db and db_dump.is_file():
            print("==> 导入本地数据库到服务器 postgres ...")
            restore = f"""
set -euo pipefail
cd {REMOTE_DIR}
docker compose -f docker-compose.prod.yml stop backend worker frontend nginx postgres 2>/dev/null || true
docker compose -f docker-compose.prod.yml rm -f postgres 2>/dev/null || true
VOL_PG=$(docker volume ls -q | grep postgres_data | head -1 || true)
if [ -n "$VOL_PG" ]; then docker volume rm "$VOL_PG"; fi
docker compose -f docker-compose.prod.yml up -d postgres redis
for i in $(seq 1 30); do
  docker exec zhixue-postgres pg_isready -U zhixue -d postgres && break
  sleep 2
done
docker cp {remote_db} zhixue-postgres:/tmp/zhixue.dump
docker exec zhixue-postgres psql -U zhixue -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='zhixue' AND pid <> pg_backend_pid();" || true
docker exec zhixue-postgres psql -U zhixue -d postgres -c "DROP DATABASE IF EXISTS zhixue;"
docker exec zhixue-postgres psql -U zhixue -d postgres -c "CREATE DATABASE zhixue OWNER zhixue;"
docker exec zhixue-postgres psql -U zhixue -d zhixue -c "CREATE EXTENSION IF NOT EXISTS vector;"
docker exec zhixue-postgres pg_restore -U zhixue -d zhixue --no-owner --no-acl /tmp/zhixue.dump || test $? -le 1
docker exec zhixue-postgres rm -f /tmp/zhixue.dump
rm -f {remote_db}
echo DB_RESTORED
"""
            code, out, err = run_script(client, restore, sudo=True, timeout=1800)
            print(out)
            if err.strip():
                print(err)
            if code != 0:
                print("[FAIL] 数据库导入失败", file=sys.stderr)
                client.close()
                return code

        if not args.skip_models and hf_tar.is_file():
            print("==> 同步 BGE 模型缓存到 model_cache 卷 ...")
            model_folder = f"models--{DEFAULT_EMBEDDING_MODEL.replace('/', '--')}"
            sync_hf = f"""
set -euo pipefail
cd {REMOTE_DIR}
docker compose -f docker-compose.prod.yml up -d postgres redis >/dev/null 2>&1 || true
VOL=$(docker volume ls -q | grep model_cache | head -1 || true)
if [ -z "$VOL" ]; then
  docker volume create zhixue_model_cache
  VOL=zhixue_model_cache
fi
docker run --rm -v "$VOL":/cache -v {remote_hf}:/host/hf.tar alpine sh -c "
  mkdir -p /cache/hub/{model_folder}
  tar -xf /host/hf.tar -C /cache/hub
  echo HF_CACHE_OK
"
rm -f {remote_hf}
"""
            code, out, err = run_script(client, sync_hf, sudo=True, timeout=1800)
            print(out or err)
            if code != 0:
                print("[WARN] 模型缓存同步失败，首次 embedding 时会重新下载", file=sys.stderr)

        if args.skip_build:
            print("==> 重启 backend / worker / frontend / nginx ...")
            up = f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d backend worker frontend nginx"
        else:
            print("==> 启动全部服务（镜像已有则跳过 rebuild，避免 SSH 卡死）...")
            up = (
                f"cd {REMOTE_DIR} && "
                "export COMPOSE_DOCKER_CLI_BUILD=1 NODE_OPTIONS=--max-old-space-size=1536; "
                "docker compose -f docker-compose.prod.yml up -d postgres redis && sleep 5 && "
                "docker compose -f docker-compose.prod.yml up -d backend worker frontend nginx 2>&1 | tail -n 20"
            )

        code, out, err = run_script(client, up, sudo=True, timeout=3600)
        print(out)
        if err.strip():
            print(err)

        _, ps, _ = run(client, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml ps", sudo=True, timeout=60)
        print("==> 容器状态 ...")
        print(ps)

        time.sleep(10)
        _, health, _ = run(client, "curl -sf http://127.0.0.1/health || curl -sf http://127.0.0.1/api/v1/health || echo HEALTH_PENDING")
        print(health.strip())

        client.close()
        if code != 0:
            print(f"\n[FAIL] 见服务器日志: cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml logs -f backend")
            return code

        print(f"\n[OK] 部署完成: http://{HOST}/")
        if not args.skip_db:
            print("     已导入本地 PostgreSQL 数据")
        if not args.skip_models:
            print(f"     已同步 {DEFAULT_EMBEDDING_MODEL} 模型缓存")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
