"""Rebuild backend with sentence-transformers and download BGE."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import paramiko

HOST = os.environ.get("ZHIXUE_DEPLOY_HOST", "49.235.190.234")
PASSWORD = os.environ.get("ZHIXUE_SSH_PASSWORD", "")
REMOTE_DIR = "/home/ubuntu/zhixue"
ROOT = Path(__file__).resolve().parents[1]


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

UPLOADS = [
    (ROOT / "backend" / "requirements.prod.txt", f"{REMOTE_DIR}/backend/requirements.prod.txt"),
    (ROOT / "backend" / "Dockerfile.cloudrun", f"{REMOTE_DIR}/backend/Dockerfile.cloudrun"),
]


def run(c: paramiko.SSHClient, cmd: str, timeout: int = 3600) -> tuple[int, str]:
    full = f"echo '{PASSWORD}' | sudo -S bash -lc {repr(cmd)}"
    _, o, e = c.exec_command(full, timeout=timeout)
    out = (o.read() + e.read()).decode("utf-8", errors="replace")
    return o.channel.recv_exit_status(), out


def run_script(c: paramiko.SSHClient, script: str, timeout: int = 600) -> tuple[int, str]:
    remote = f"/tmp/zhixue_ops_{int(time.time())}.sh"
    sftp = c.open_sftp()
    with sftp.file(remote, "w") as f:
        f.write("#!/bin/bash\nset -euo pipefail\n")
        f.write(script)
    sftp.chmod(remote, 0o755)
    sftp.close()
    code, out = run(c, f"bash {remote}", timeout=timeout)
    run(c, f"rm -f {remote}", timeout=30)
    return code, out


def main() -> int:
    _configure_stdout()
    if not PASSWORD:
        print("Set ZHIXUE_SSH_PASSWORD", file=sys.stderr)
        return 1

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="ubuntu", password=PASSWORD, timeout=30)

    sftp = c.open_sftp()
    for local, remote in UPLOADS:
        sftp.put(str(local), remote)
        print(f"uploaded {local.name}")
    sftp.close()

    print("==> 重建 backend/worker（含 sentence-transformers，后台构建）...")
    build_script = f"""
cd {REMOTE_DIR}
nohup docker compose -f docker-compose.prod.yml build backend worker > /tmp/backend-rebuild.log 2>&1 &
sleep 1
echo BUILD_STARTED
tail -n 3 /tmp/backend-rebuild.log 2>/dev/null || true
"""
    _, out = run_script(c, build_script, timeout=60)
    print(out.strip())

    for i in range(120):
        time.sleep(15)
        _, tail = run(c, "tail -n 8 /tmp/backend-rebuild.log 2>/dev/null || true", timeout=30)
        _, proc = run(c, "pgrep -af 'docker compose.*build' || true", timeout=30)
        print(f"\n--- poll #{i+1} ---")
        print(tail.strip())
        building = "docker compose" in proc and "build" in proc
        if not building:
            _, tail2 = run(c, "tail -n 20 /tmp/backend-rebuild.log", timeout=30)
            if "Built" in tail2 or "exporting to image" in tail2 or "naming to docker.io" in tail2:
                print(tail2)
                break
            if i >= 3 and "ERROR" in tail2:
                print(tail2)
                break
            if i >= 3:
                print(tail2)
                break

    print("==> 重启 backend/worker ...")
    _, out = run(
        c,
        f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d backend worker",
        timeout=300,
    )
    print(out)

    for i in range(20):
        code, out = run(c, "docker exec zhixue-backend pip show sentence-transformers 2>/dev/null | head -2", timeout=30)
        if code == 0 and "sentence-transformers" in out:
            print("sentence_transformers 已安装")
            break
        time.sleep(5)
    else:
        print("[FAIL] sentence_transformers 仍未安装，构建可能未完成")
        c.close()
        return 1

    print("==> 下载 BGE 模型 ...")
    bge = """#!/bin/bash
set -euo pipefail
export HF_ENDPOINT=https://hf-mirror.com HF_HUB_ENDPOINT=https://hf-mirror.com
python -c "from sentence_transformers import SentenceTransformer; m=SentenceTransformer('BAAI/bge-large-zh-v1.5'); print('model_ok', m.get_sentence_embedding_dimension())"
"""
    remote = "/tmp/download_bge.sh"
    with c.open_sftp().file(remote, "w") as f:
        f.write(bge)
    c.open_sftp().chmod(remote, 0o755)
    run(c, f"docker cp {remote} zhixue-backend:/tmp/download_bge.sh", timeout=60)
    code, out = run(c, "docker exec zhixue-backend bash /tmp/download_bge.sh", timeout=1800)
    print(out)

    _, out = run(c, "curl -sf http://127.0.0.1/health && echo && curl -sf -o /dev/null -w '%{http_code}' http://127.0.0.1/", timeout=30)
    print("verify:", out)
    c.close()
    print(f"\nhttp://{HOST}/")
    return 0 if code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
