"""Persistent Mechanical session — start, connect, stop.

Pattern: Mechanical runs as a long-lived gRPC server (`AnsysWBU.exe`) with
its GUI visible. Short-lived client scripts (and Claude tool calls) attach to
it via `connect()`, issue commands, and detach without killing the server.

Usage from another Python script:

    from mech.session import connect
    mech = connect()
    mech.run_python_script("Model.AddLSDynaAnalysis()")

Lifecycle from CLI:

    python mech/session.py start    # launches Mechanical, GUI visible
    python mech/session.py status   # report whether server is reachable
    python mech/session.py stop     # cleanly shut down the server
"""
from __future__ import annotations

import socket
import sys
import time
from pathlib import Path

PORT = 10000          # fixed port so multiple client scripts can find the server
HOST = "127.0.0.1"
PIDFILE = Path(__file__).with_name("mechanical.pid")


def _is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        try:
            s.connect((host, port))
            return True
        except (ConnectionRefusedError, OSError):
            return False


def connect():
    """Attach to the running Mechanical server. Raises if not reachable."""
    import ansys.mechanical.core as pymech
    if not _is_port_open(HOST, PORT):
        raise RuntimeError(
            f"No Mechanical server listening on {HOST}:{PORT}. "
            f"Run `python mech/session.py start` first."
        )
    mech = pymech.connect_to_mechanical(ip=HOST, port=PORT, cleanup_on_exit=False)
    return mech


def start(batch: bool = False, timeout: int = 180):
    """Launch Mechanical with GUI visible (batch=False) and leave it running.

    This call BLOCKS until Mechanical is reachable on PORT, then writes the PID
    and returns. The Mechanical process keeps running after this script exits
    because we set cleanup_on_exit=False.
    """
    import ansys.mechanical.core as pymech

    if _is_port_open(HOST, PORT):
        print(f"[session] Mechanical already running on {HOST}:{PORT}")
        return

    print(f"[session] Launching Mechanical (batch={batch}, port={PORT})...")
    print(f"[session] First launch can take 30-90s — Workbench Unified is heavy.")

    mech = pymech.launch_mechanical(
        batch=batch,
        port=PORT,
        cleanup_on_exit=False,    # ← critical: server survives this script's exit
        verbose_mechanical=False,
    )

    # Wait for it to actually accept connections
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _is_port_open(HOST, PORT):
            break
        time.sleep(2)
    else:
        raise RuntimeError(f"Mechanical did not become reachable within {timeout}s")

    # Sanity ping
    version = mech.run_python_script("ExtAPI.Application.VersionInfo")
    print(f"[session] Mechanical reachable. Version: {version}")
    print(f"[session] Connect from any other script via mech.session.connect()")


def status():
    if _is_port_open(HOST, PORT):
        print(f"[session] Mechanical responding on {HOST}:{PORT}")
        try:
            mech = connect()
            v = mech.run_python_script("ExtAPI.Application.VersionInfo")
            print(f"[session] Version: {v}")
        except Exception as e:
            print(f"[session] (couldn't fetch version: {e})")
    else:
        print(f"[session] No Mechanical server on {HOST}:{PORT}")


def stop():
    if not _is_port_open(HOST, PORT):
        print(f"[session] Nothing to stop — no server on {HOST}:{PORT}")
        return
    try:
        mech = connect()
        mech.exit()
        print("[session] Sent exit() to Mechanical")
    except Exception as e:
        print(f"[session] WARNING: clean exit failed ({e}). Kill AnsysWBU.exe manually if needed.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "start":
        start(batch=False)
    elif cmd == "start-headless":
        start(batch=True)
    elif cmd == "stop":
        stop()
    elif cmd == "status":
        status()
    else:
        print(f"Unknown command: {cmd}. Use start | start-headless | stop | status")
        sys.exit(1)
