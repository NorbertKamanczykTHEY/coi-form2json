"""The container's own gunicorn command boots every worker on a fresh SQLite file (no create_all/seed race)."""
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]


def test_gunicorn_workers_boot_on_fresh_db(tmp_path):
    cmd = json.loads(re.search(r"^CMD (\[.*\])$", (BACKEND / "Dockerfile").read_text(), re.M)[1])
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    cmd[cmd.index("--bind") + 1] = f"127.0.0.1:{port}"
    cmd[cmd.index("--workers") + 1] = "3"
    env = os.environ | {"DATABASE_URL": f"sqlite:///{tmp_path / 'coi.sqlite'}", "JWT_SECRET": "x" * 40, "JWT_ALG": "HS256"}
    p = subprocess.Popen([str(Path(sys.executable).parent / cmd[0]), *cmd[1:]], cwd=BACKEND, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        for _ in range(120):
            try:
                assert urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1).status == 200
                break
            except OSError:
                assert p.poll() is None, p.stdout.read()
                time.sleep(0.25)
        time.sleep(1.5)  # let every worker finish booting
        assert p.poll() is None
    finally:
        p.send_signal(signal.SIGTERM)
        out = p.communicate(timeout=20)[0]
    assert "Worker failed to boot" not in out and "already exists" not in out, out
    assert out.count("Booting worker") == 3
