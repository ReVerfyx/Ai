#!/usr/bin/env python3
"""Run a downloaded public repository inside a disposable root sandbox.

The sandbox has no network namespace, no host /etc, no SSH keys, no systemd,
no Docker socket and no access to the main ReVerfyx checkout. The process sees
itself as uid 0 only inside the isolated user namespace.
"""
import json
import os
import resource
import shutil
import subprocess
import sys
import time
from pathlib import Path

def pick_command(repo: Path):
    # Prefer harmless self-describing entry points. We intentionally do not run
    # install scripts or package managers here.
    candidates = [
        (repo / "main.py", ["/usr/bin/python3", "main.py"]),
        (repo / "app.py", ["/usr/bin/python3", "app.py"]),
        (repo / "cli.py", ["/usr/bin/python3", "cli.py", "--help"]),
    ]
    for path, cmd in candidates:
        if path.is_file() and path.stat().st_size <= 2_000_000:
            return cmd

    py = sorted(
        p for p in repo.glob("*.py")
        if p.is_file() and p.stat().st_size <= 1_000_000
        and p.name not in {"setup.py", "conftest.py"}
    )
    if py:
        return ["/usr/bin/python3", py[0].name, "--help"]
    return None

def limits():
    # Inherited by bwrap and its child.
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024 * 1024, 32 * 1024 * 1024))
    try:
        resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
    except Exception:
        pass

def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: sandbox_exec.py REPO_DIR")

    repo = Path(sys.argv[1]).resolve()
    if not repo.is_dir():
        raise SystemExit("repo dir missing")

    bwrap = shutil.which("bwrap")
    if not bwrap:
        print(json.dumps({"status":"skipped","reason":"bubblewrap_missing"}))
        return

    command = pick_command(repo)
    if not command:
        print(json.dumps({"status":"skipped","reason":"no_supported_entrypoint"}))
        return

    args = [
        bwrap,
        "--unshare-all",
        "--die-with-parent",
        "--new-session",
        "--uid", "0",
        "--gid", "0",
        "--ro-bind", "/usr", "/usr",
        "--ro-bind", "/bin", "/bin",
        "--ro-bind", "/lib", "/lib",
        "--ro-bind-try", "/lib64", "/lib64",
        "--proc", "/proc",
        "--dev", "/dev",
        "--tmpfs", "/tmp",
        "--tmpfs", "/run",
        "--tmpfs", "/var",
        "--dir", "/etc",
        "--bind", str(repo), "/work",
        "--chdir", "/work",
        "--setenv", "HOME", "/tmp",
        "--setenv", "PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "--",
        *command,
    ]

    started = time.time()
    try:
        p = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            timeout=20,
            preexec_fn=limits,
            env={"PATH": os.environ.get("PATH","/usr/bin:/bin")},
        )
        out = (p.stdout or "")[-12000:]
        result = {
            "status":"ran",
            "exit_code":p.returncode,
            "seconds":round(time.time()-started,3),
            "command":command,
            "output":out,
        }
    except subprocess.TimeoutExpired as e:
        result = {
            "status":"timeout",
            "seconds":round(time.time()-started,3),
            "command":command,
            "output":((e.stdout or "") if isinstance(e.stdout,str) else "")[-12000:],
        }
    except Exception as e:
        result = {"status":"error","reason":str(e),"command":command}

    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
