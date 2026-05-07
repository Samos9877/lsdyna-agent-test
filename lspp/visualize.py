"""Open a LS-DYNA run's d3plot in LS-PrePost (the native LSTC visualizer).

For Ansys Student users, LSPP is the right tool for d3plot inspection —
purpose-built for LS-DYNA results, animation controls, contour plots,
contact force visualization, foam-specific quantities. Mechanical's result
viewer fights us on saved-project mode (see mech/README.md), so for
post-processing of headless solver runs LSPP is the canonical path.

Usage:
    # Open a run directory (auto-finds d3plot)
    python -m lspp.visualize verify/reports/geofoam_indent_v11_SFO_fixed/

    # Or point directly at a d3plot file
    python -m lspp.visualize verify/reports/.../d3plot

    # With a startup cfile that sets a useful initial view
    python -m lspp.visualize <run> --cfile mycommands.cfile

    # Headless image render (writes a PNG, exits)
    python -m lspp.visualize <run> --render mycontour.png

    # Library use:
    from lspp.visualize import open_in_lspp
    proc = open_in_lspp(run_dir)
    print(proc.pid)
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import textwrap
from pathlib import Path

LSPP_DEFAULT = Path(
    r"C:\Program Files\LS-DYNA Suite R16.1 Student\lspp\lsprepost4.12.exe"
)


def find_d3plot(target: Path) -> Path:
    """Resolve `target` to a d3plot path.

    Accepts either a directory (which must contain a `d3plot` file) or
    a direct path to a d3plot file. Returns the absolute path.
    """
    target = target.resolve()
    if target.is_file():
        return target
    if target.is_dir():
        d3 = target / "d3plot"
        if d3.is_file():
            return d3
        raise FileNotFoundError(f"No `d3plot` file in {target}")
    raise FileNotFoundError(f"Path doesn't exist: {target}")


def open_in_lspp(
    target: Path | str,
    cfile: Path | str | None = None,
    keep_after_cfile: bool = True,
    lspp_exe: Path | str = LSPP_DEFAULT,
    detach: bool = True,
) -> subprocess.Popen:
    """Launch LS-PrePost with the given run loaded.

    Parameters
    ----------
    target : Path | str
        A run directory (we'll find `d3plot` inside) or a direct d3plot path.
    cfile : Path | str | None
        Optional command file (.cfile) to run at startup. Useful for
        pre-setting the view, picking contours, saving images, etc.
    keep_after_cfile : bool
        If a cfile is given, append `keep=1` so the GUI stays open after
        the cfile finishes. Ignored if cfile is None.
    lspp_exe : Path | str
        Path to lsprepost4.12.exe.
    detach : bool
        If True (default), spawn LSPP detached from this Python process so
        it survives this script's exit.

    Returns
    -------
    subprocess.Popen
        The LSPP process handle. PID is `proc.pid`.
    """
    d3plot = find_d3plot(Path(target))
    lspp_exe = Path(lspp_exe).resolve()
    if not lspp_exe.is_file():
        raise FileNotFoundError(f"LS-PrePost exe not found: {lspp_exe}")

    cmd = [str(lspp_exe), str(d3plot)]
    if cfile is not None:
        cfile_path = Path(cfile).resolve()
        if not cfile_path.is_file():
            raise FileNotFoundError(f"cfile not found: {cfile_path}")
        cmd.append(f"c={cfile_path}")
        if keep_after_cfile:
            cmd.append("keep=1")

    # Run LSPP from the run directory so any relative paths in cfile resolve
    cwd = d3plot.parent

    print(f"[lspp] launching: {' '.join(repr(c) if ' ' in c else c for c in cmd)}")
    print(f"[lspp] cwd: {cwd}")

    creationflags = 0
    if detach and os.name == "nt":
        # CREATE_NEW_PROCESS_GROUP so this Python's exit doesn't take LSPP with it
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=creationflags,
    )
    print(f"[lspp] launched, PID={proc.pid}")
    return proc


# Pre-canned cfile snippets for common views ──────────────────────────────────

CFILE_CONTOUR_VONMISES = """\
$ Set page 2 (Fcomp), select von Mises stress contour, animate to last state
fcomp 11
state -1
animate
"""


CFILE_HEADLESS_RENDER_PNG = """\
$ Headless image render — set view, contour, save PNG, exit
fcomp 11
state -1
genimg png 1 100 800 600 "{out_png}"
exit
"""


def render_png_headless(target: Path | str, out_png: Path | str,
                        lspp_exe: Path | str = LSPP_DEFAULT) -> Path:
    """Render a contour PNG without opening the GUI.

    Generates a temporary cfile, runs LSPP with -nographics, returns the
    PNG path on success.
    """
    d3plot = find_d3plot(Path(target))
    out_png = Path(out_png).resolve()
    out_png.parent.mkdir(parents=True, exist_ok=True)

    cfile_path = d3plot.parent / "_lspp_render.cfile"
    cfile_path.write_text(CFILE_HEADLESS_RENDER_PNG.format(out_png=str(out_png)))

    cmd = [str(lspp_exe), str(d3plot), f"c={cfile_path}", "-nographics"]
    print(f"[lspp] headless render: {' '.join(cmd)}")
    result = subprocess.run(
        cmd, cwd=str(d3plot.parent),
        capture_output=True, text=True, timeout=120,
    )
    cfile_path.unlink(missing_ok=True)
    if result.returncode != 0:
        raise RuntimeError(f"LSPP headless render failed: {result.stderr[:300]}")
    if not out_png.is_file():
        raise RuntimeError(f"PNG not produced at {out_png}")
    return out_png


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("target", help="Run directory or path to a d3plot file")
    ap.add_argument("--cfile", default=None,
                    help="Optional startup cfile to run after loading")
    ap.add_argument("--render", default=None,
                    help="Headless: render a PNG to this path and exit")
    ap.add_argument("--lspp", default=str(LSPP_DEFAULT),
                    help=f"LS-PrePost executable (default: {LSPP_DEFAULT})")
    args = ap.parse_args()

    if args.render:
        out = render_png_headless(args.target, args.render, lspp_exe=args.lspp)
        print(f"[lspp] rendered: {out}")
    else:
        proc = open_in_lspp(args.target, cfile=args.cfile, lspp_exe=args.lspp)
        print(f"[lspp] window open. Close it manually when done. PID={proc.pid}")


if __name__ == "__main__":
    main()
