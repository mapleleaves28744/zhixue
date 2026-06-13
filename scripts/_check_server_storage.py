#!/usr/bin/env python3
import os
import paramiko

PASSWORD = os.environ.get("ZHIXUE_SSH_PASSWORD", "")
if not PASSWORD:
    raise SystemExit("set ZHIXUE_SSH_PASSWORD")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("49.235.190.234", username="ubuntu", password=PASSWORD, timeout=30)

cmds = [
    "find /home/ubuntu/zhixue/storage -type f 2>/dev/null | wc -l",
    "du -sh /home/ubuntu/zhixue/storage 2>/dev/null || echo no_storage",
    "du -sh /home/ubuntu/zhixue/data/seed_knowledge 2>/dev/null || echo no_seed",
    "docker exec zhixue-backend test -f data/seed_knowledge/data_structure/normalized/authoritative/mit-ocw-6006/ch02-mit-6-006-course-overview.md && echo IN_CONTAINER || echo NOT_IN_CONTAINER",
    "docker exec zhixue-postgres psql -U zhixue -d zhixue -t -c \"SELECT count(*) FROM course_materials;\"",
    "docker exec zhixue-postgres psql -U zhixue -d zhixue -t -c \"SELECT count(*) FROM course_materials WHERE extra_meta->>'parsed_text_path' LIKE '%.parsed.txt';\"",
    "docker exec zhixue-postgres psql -U zhixue -d zhixue -t -c \"SELECT file_name, left(storage_path,100) FROM course_materials WHERE file_name LIKE '11_%' LIMIT 1;\"",
    "docker exec zhixue-backend ls /app/data/seed_knowledge/data_structure/normalized/self_curated 2>&1 | wc -l",
    "docker exec zhixue-backend sh -c 'test -f data/seed_knowledge/data_structure/normalized/self_curated/11_*.md && echo HAS_11 || echo NO_11'",
]
for cmd in cmds:
    _, o, e = c.exec_command(cmd, timeout=60)
    out = o.read().decode().strip()
    err = e.read().decode().strip()
    print("===", cmd[:80])
    print(out or err or "(empty)")
c.close()
