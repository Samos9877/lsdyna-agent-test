"""Ingest LS-DYNA results from a headless run dir into a Mechanical session.

Use this when you've solved a deck via lsdyna_runner.py and want to view the
results in Mechanical's 3D viewer. The pattern is:
    1. Mechanical built the model and exported input.k via WriteInputFile()
    2. lsdyna_runner ran input.k headless and produced d3plot, elout, glstat...
    3. This script copies the outputs into Mechanical's WorkingDir and adds
       Result objects to the Solution tree, then evaluates them.

Why this matters: Mechanical's own Solve infrastructure on Ansys Student
licensing fails ("demanded solver was not found" or "general SOLVER error")
because the LSTC standalone Student install doesn't fit Mechanical's
expected solver-launch protocol. But Mechanical's RESULT-EVALUATION layer
just reads d3plot files from the WorkingDir — it doesn't care whether
Mechanical itself ran the solver.

Usage from a Python script:
    from mech.ingest_results import ingest
    ingest(headless_run_dir="path/to/run/", system_name="SYS", wb_port=56112)

CLI:
    python -m mech.ingest_results <headless_run_dir> [--wb-port 56112] [--system SYS]
"""
from __future__ import annotations

import argparse
import shutil
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

# Files that Mechanical expects to find in its WorkingDir for result evaluation
RESULT_FILES = [
    "d3plot",  # required — main binary results
    "d3plot01", "d3plot02", "d3plot03", "d3plot04", "d3plot05",  # additional time states
    "d3hsp",   # hsp report (optional)
    "glstat", "elout", "nodout", "spcforc", "rcforc", "bndout", "matsum",
    "messag",  # solver messages (optional)
]


# Result objects to add — (method_name, friendly_label, optional_orientation)
DEFAULT_RESULTS = [
    ("AddTotalDeformation", "TotalDeformation", None),
    ("AddDirectionalDeformation", "DirZ_Displacement", "ZAxis"),
    ("AddEquivalentStress", "EqvStress", None),
    ("AddNormalStress", "NormalStress_Z", "ZAxis"),
    ("AddEquivalentElasticStrain", "EqvElasticStrain", None),
]


def attach(wb_port: int, system_name: str = "SYS"):
    from ansys.workbench.core import connect_workbench
    import ansys.mechanical.core as pymech
    wb = connect_workbench(port=wb_port, security="insecure")
    mech_port = wb.start_mechanical_server(system_name=system_name)
    mech = pymech.connect_to_mechanical(
        ip="localhost", port=mech_port, cleanup_on_exit=False
    )
    return wb, mech


def ingest(headless_run_dir: str | Path, wb_port: int = 56112,
           system_name: str = "SYS", clear_old: bool = True):
    """Copy result files from headless_run_dir into Mechanical's WorkingDir,
    then add result objects and evaluate.

    Returns dict of {result_name: (min_str, max_str)} for the evaluated probes.
    """
    src = Path(headless_run_dir).resolve()
    if not src.is_dir():
        raise FileNotFoundError(f"Headless run dir not found: {src}")

    wb, mech = attach(wb_port, system_name)
    workdir = mech.run_python_script("Model.Analyses[0].Solution.WorkingDir")
    workdir = Path(workdir.strip().strip("'\""))
    print(f"[ingest] Mechanical WorkingDir: {workdir}")
    print(f"[ingest] copying results from: {src}")

    copied = []
    for fname in RESULT_FILES:
        s = src / fname
        if s.is_file():
            shutil.copy2(s, workdir / fname)
            copied.append(f"{fname} ({s.stat().st_size} B)")
    print(f"[ingest] copied {len(copied)} files: {', '.join(copied)}")

    if clear_old:
        cleanup = '''
sol = Model.Analyses[0].Solution
to_delete = [c for c in sol.Children if c.Name.startswith("claude_")]
for c in to_delete:
    c.Delete()
"removed " + str(len(to_delete)) + " stale claude_* results"
'''
        print(f"[ingest] {mech.run_python_script(cleanup)}")

    # Build a script to add all the result objects + evaluate
    add_script_lines = ["sol = Model.Analyses[0].Solution", "added = []"]
    for method, label, orient in DEFAULT_RESULTS:
        add_script_lines.append(f"""
try:
    r = sol.{method}()
    r.Name = "claude_{label}"
""")
        if orient:
            add_script_lines.append(
                f"    r.NormalOrientation = NormalOrientationType.{orient}\n"
            )
        add_script_lines.append(f"""    added.append("{label}")
except Exception as e:
    added.append("{label}_ERR:" + str(e)[:80])
""")
    add_script_lines.append("""
try:
    sol.EvaluateAllResults()
    added.append("EvaluateAllResults_OK")
except Exception as e:
    added.append("Evaluate_ERR:" + str(e)[:120])

out_lines = ["added: " + str(added), ""]
for c in sol.Children:
    if c.Name.startswith("claude_"):
        try:
            out_lines.append("  " + c.Name + ": " + str(c.Minimum) + " .. " + str(c.Maximum))
        except Exception as e:
            out_lines.append("  " + c.Name + " (min/max err: " + str(e)[:60] + ")")
chr(10).join(out_lines)
""")
    add_script = "".join(add_script_lines)
    print(f"[ingest] adding result objects + evaluating...")
    print(mech.run_python_script(add_script))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("headless_run_dir", type=Path,
                    help="Directory containing d3plot from a headless lsdyna run")
    ap.add_argument("--wb-port", type=int, default=56112,
                    help="Workbench gRPC port (default 56112)")
    ap.add_argument("--system", default="SYS",
                    help="LS-DYNA system name in Workbench (default 'SYS')")
    ap.add_argument("--keep-old", action="store_true",
                    help="Don't delete pre-existing claude_* result objects")
    args = ap.parse_args()
    ingest(args.headless_run_dir, wb_port=args.wb_port,
           system_name=args.system, clear_old=not args.keep_old)


if __name__ == "__main__":
    main()
