"""Helper for talking to a running Mechanical session.

Wraps the verbose gRPC errors into something readable, and provides a single
`run()` entry point that streams a multi-line script to Mechanical's IronPython
console.
"""
from __future__ import annotations

import re
import textwrap
from typing import Any

from .session import connect


_GRPC_NOISE = re.compile(r'(debug_error_string|grpc_status|grpc_message)')


def _tidy(error_text: str) -> str:
    """Strip gRPC framing from an IronPython traceback."""
    # Find the original 'System.<TypeError>: ...' message
    m = re.search(r"System\.[A-Za-z]+(?:Exception|Error)[^']+", error_text)
    if m:
        return m.group(0).replace("\\r\\n", "\n").replace("\\\\", "\\")
    # Fallback: drop pure gRPC lines
    return "\n".join(l for l in error_text.splitlines() if not _GRPC_NOISE.search(l))


def run(script: str, mech=None, dedent: bool = True) -> Any:
    """Send a (multi-line) Python script to Mechanical and return the result.

    Parameters
    ----------
    script : str
        Python code to execute inside Mechanical's IronPython interpreter.
    mech : optional
        An existing Mechanical connection. If None, a new one is opened.
    dedent : bool
        If True, run textwrap.dedent on the script first.
    """
    if dedent:
        script = textwrap.dedent(script).strip()
    if mech is None:
        mech = connect()
    try:
        return mech.run_python_script(script)
    except Exception as exc:
        msg = _tidy(str(exc))
        raise RuntimeError(f"Mechanical script failed:\n{msg}\n\n--- script ---\n{script}") from None


def run_silent(script: str, mech=None) -> None:
    """Run a script for side effects only; print 'ok' or raise."""
    run(script, mech=mech)
    print("ok")
