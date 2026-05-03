"""Thin Python wrapper around the standalone LS-DYNA Suite R16.1 Student solver.

PyDYNA's WindowsRunner assumes an Ansys-Unified install layout (looks for
lsprepost*/LS-Run/lsdynamsvar.bat next to the solver). The standalone LSTC
Student install has no such env script. This wrapper just shells out directly.

Usage:
    from lsdyna_runner import run_dyna
    result = run_dyna("path/to/deck.k", working_directory="run/", ncpu=1, memory_mb=20)
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

# Default solver — override per call if needed
DEFAULT_SOLVER = Path(
    r"C:\Program Files\LS-DYNA Suite R16.1 Student\lsdyna"
    r"\ls-dyna_smp_d_R16.1_180-gd50332dbe5_winx64_ifort190_sse2_studentversion.exe"
)


def run_dyna(
    input_file: str | Path,
    working_directory: str | Path | None = None,
    ncpu: int = 1,
    memory_mb: int = 20,
    solver: str | Path = DEFAULT_SOLVER,
    capture_output: bool = True,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess:
    """Run LS-DYNA on an input deck.

    Parameters
    ----------
    input_file : path to a .k file. Copied into working_directory if separate.
    working_directory : where the solver runs. Defaults to the deck's parent dir.
    ncpu : number of SMP threads. Student version typically capped at 1-2.
    memory_mb : solver memory pool size in MB.
    solver : path to the LS-DYNA executable.
    capture_output : tee stdout/stderr to the returned CompletedProcess.
    extra_args : additional `key=value` args appended to the command.
    """
    input_file = Path(input_file).resolve()
    if working_directory is None:
        working_directory = input_file.parent
    else:
        working_directory = Path(working_directory).resolve()
        working_directory.mkdir(parents=True, exist_ok=True)
        if input_file.parent != working_directory:
            dest = working_directory / input_file.name
            shutil.copy2(input_file, dest)
            input_file = dest

    cmd = [
        str(solver),
        f"i={input_file.name}",
        f"ncpu={ncpu}",
        f"memory={memory_mb}m",
    ]
    if extra_args:
        cmd.extend(extra_args)

    print(f"[lsdyna_runner] cwd: {working_directory}")
    print(f"[lsdyna_runner] cmd: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        cwd=str(working_directory),
        capture_output=capture_output,
        text=True,
        check=False,
    )
    if capture_output:
        # Write the solver log alongside outputs for later inspection
        (working_directory / "solver_stdout.log").write_text(result.stdout or "")
        (working_directory / "solver_stderr.log").write_text(result.stderr or "")

    if result.returncode != 0:
        print(f"[lsdyna_runner] WARNING: exit code {result.returncode}")
    else:
        # Look for "N o r m a l    t e r m i n a t i o n" in the tail
        tail = (result.stdout or "").splitlines()[-30:]
        normal = any("N o r m a l" in line for line in tail)
        print(f"[lsdyna_runner] {'normal termination' if normal else 'completed (no normal-termination marker)'}")
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    deck = Path(sys.argv[1])
    workdir = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    run_dyna(deck, working_directory=workdir)
