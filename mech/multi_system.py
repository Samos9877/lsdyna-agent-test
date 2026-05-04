"""Multi-system orchestration for LS-DYNA unit tests inside one Workbench.

Baseline workflow for simple element unit tests (per Sam, 2026-05-03):
  - Set up N LS-DYNA Analysis Systems in Workbench (one per material/test variant)
  - For each, drive Mechanical to: WriteInputFile -> headless solve in
    that system's WorkingDir -> add result objects -> EvaluateAllResults
  - View results in each system's Mechanical instance

Why headless solve instead of `analysis.Solution.Solve()`:
  Mechanical's own Solve infrastructure is broken on Ansys Student
  (general SOLVER error — Mechanical wraps the SMP exe with an MPI
  launcher that the standalone Suite Student can't satisfy). The
  result-evaluation layer reads d3plot from WorkingDir and works fine
  regardless of who put the d3plot there.

CLI usage:
    python -m mech.multi_system list
    python -m mech.multi_system duplicate --from SYS --display test_steel
    python -m mech.multi_system solve SYS
    python -m mech.multi_system solve-all
    python -m mech.multi_system delete --name "SYS 2"

Library usage:
    from mech.multi_system import attach, duplicate_system, solve_in_place
    wb, _ = attach()
    new_name = duplicate_system(wb, source="SYS", display="test_eps22")
    solve_in_place(wb, new_name)
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

# Path bootstrap so this works whether invoked as a module or a script
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_WB_PORT = 56112


# Result objects added to every solved system — Total Deformation + the
# stress / strain / displacement set Sam needs for soil unit tests.
DEFAULT_RESULT_OBJECTS = [
    ("AddTotalDeformation", "TotalDeformation", None),
    ("AddDirectionalDeformation", "DirZ_Displacement", "ZAxis"),
    ("AddEquivalentStress", "EqvStress", None),
    ("AddNormalStress", "NormalStress_Z", "ZAxis"),
    ("AddEquivalentElasticStrain", "EqvElasticStrain", None),
]


# --------------------------------------------------------------------- attach

def attach(wb_port: int = DEFAULT_WB_PORT):
    """Connect to a running Workbench server. Returns (wb, mech_factory).

    `mech_factory(system_name)` returns a connected Mechanical client for
    the given system, lazy-launching Mechanical if not already running.
    """
    from ansys.workbench.core import connect_workbench
    import ansys.mechanical.core as pymech

    wb = connect_workbench(port=wb_port, security="insecure")

    def mech_factory(system_name: str):
        mech_port = wb.start_mechanical_server(system_name=system_name)
        return pymech.connect_to_mechanical(
            ip="localhost", port=mech_port, cleanup_on_exit=False
        )

    return wb, mech_factory


# ------------------------------------------------------------- system catalog

def _wb_call(wb, script: str):
    """Run a journal script that sets wb_script_result via json.dumps;
    PyWorkbench parses the JSON for us so we get a Python object back.
    Returns whatever the script set in wb_script_result."""
    return wb.run_script_string(script)


def list_systems(wb) -> list[dict]:
    return _wb_call(wb, """
import json
wb_script_result = json.dumps([
    {"Name": s.Name, "DisplayText": s.DisplayText, "Solver": str(s.Solver)}
    for s in GetAllSystems()
])
""") or []


def duplicate_system(wb, source: str = "SYS", display: str | None = None) -> str:
    """Duplicate an existing LS-DYNA system. Returns the new system's Name.

    The duplicate inherits geometry, mesh, BCs from the source. To make
    it a different test case, modify the duplicate's material / loading
    via Mechanical after duplication.
    """
    set_display = ""
    if display is not None:
        set_display = f"new_sys.DisplayText = '{display}'\n"
    info = _wb_call(wb, f"""
import json
src = GetSystem(Name='{source}')
new_sys = src.Duplicate()
{set_display}wb_script_result = json.dumps({{
    "Name": new_sys.Name,
    "DisplayText": new_sys.DisplayText,
}})
""")
    return info["Name"]


def delete_system(wb, name: str) -> None:
    wb.run_script_string(f"""
sys = GetSystem(Name='{name}')
sys.Delete()
""")


def rename_system(wb, name: str, new_display: str) -> None:
    wb.run_script_string(f"""
sys = GetSystem(Name='{name}')
sys.DisplayText = '{new_display}'
""")


# -------------------------------------------------------------------- solving

def _read_workdir(mech) -> Path:
    raw = mech.run_python_script("Model.Analyses[0].Solution.WorkingDir")
    return Path(str(raw).strip().strip("'\""))


def _ensure_input_k(mech, workdir: Path) -> Path:
    """Generate input.k via Mechanical's WriteInputFile if not already present
    or if it's stale. Returns the path."""
    target = workdir / "input.k"
    # Always re-export — material/BC changes since last WriteInputFile would
    # otherwise silently use stale .k.
    set_endtime = """
asettings = [c for c in Model.Analyses[0].Children if c.Name == 'Analysis Settings'][0]
ep = asettings.PropertyByName('Step Controls/Endtime')
if ep.InternalValue is None or ep.InternalValue == 0:
    ep.InternalValue = 1.0
"""
    mech.run_python_script(set_endtime)
    mech.run_python_script(f"Model.Analyses[0].WriteInputFile(r'{target}')")
    if not target.exists():
        raise RuntimeError(f"WriteInputFile did not produce {target}")
    return target


def _add_result_objects(mech) -> list[str]:
    """Add the default result probe set (idempotent — deletes claude_* first).

    Builds a single multi-line IronPython script and sends it to Mechanical.
    """
    parts = [
        "sol = Model.Analyses[0].Solution",
        "for c in list(sol.Children):",
        "    if c.Name.startswith('claude_'): c.Delete()",
        "added = []",
    ]
    for method, label, orient in DEFAULT_RESULT_OBJECTS:
        parts.append("try:")
        parts.append(f"    r = sol.{method}()")
        parts.append(f"    r.Name = 'claude_{label}'")
        if orient:
            parts.append(f"    r.NormalOrientation = NormalOrientationType.{orient}")
        parts.append(f"    added.append('{label}')")
        parts.append("except Exception as e:")
        parts.append(f"    added.append('{label}_ERR:' + str(e)[:60])")
    parts.append("try:")
    parts.append("    sol.EvaluateAllResults()")
    parts.append("    added.append('EvaluateAllResults_OK')")
    parts.append("except Exception as e:")
    parts.append("    added.append('Evaluate_ERR:' + str(e)[:120])")
    parts.append("chr(10).join(added)")
    script = "\n".join(parts)
    out = mech.run_python_script(script)
    return out.splitlines() if out else []


def _result_summary(mech) -> dict:
    out = mech.run_python_script("""
import json
sol = Model.Analyses[0].Solution
data = []
for c in sol.Children:
    if c.Name.startswith('claude_'):
        try:
            data.append({'name': c.Name, 'min': str(c.Minimum), 'max': str(c.Maximum)})
        except Exception as e:
            data.append({'name': c.Name, 'err': str(e)[:80]})
json.dumps(data)
""")
    return json.loads(out) if out else []


def solve_in_place(wb, system_name: str = "SYS",
                   ncpu: int = 1, memory_mb: int = 40) -> dict:
    """Solve one system end-to-end: WriteInputFile -> headless run in
    Mechanical's WorkingDir -> add result objects -> EvaluateAllResults.

    Returns dict with system name, workdir, normal_termination flag, and
    a list of {name, min, max} for the evaluated results.
    """
    from lsdyna_runner import run_dyna

    _wb, mech_factory = attach(DEFAULT_WB_PORT) if wb is None else (wb, None)
    if mech_factory is None:
        # If wb passed in directly, build the mech factory inline
        import ansys.mechanical.core as pymech
        def mech_factory(name):
            return pymech.connect_to_mechanical(
                ip="localhost",
                port=wb.start_mechanical_server(system_name=name),
                cleanup_on_exit=False,
            )

    print(f"\n[multi_system] === solve {system_name} ===")
    mech = mech_factory(system_name)
    workdir = _read_workdir(mech)
    print(f"[multi_system] workdir: {workdir}")

    input_k = _ensure_input_k(mech, workdir)
    print(f"[multi_system] input.k: {input_k.stat().st_size} bytes")

    print(f"[multi_system] running solver in WorkingDir (no copy)...")
    result = run_dyna(input_k, working_directory=workdir,
                      ncpu=ncpu, memory_mb=memory_mb)
    normal = "N o r m a l" in (result.stdout or "")[-3000:]
    print(f"[multi_system] {'NORMAL TERMINATION' if normal else 'FAILED'}")
    if not normal:
        return {"system": system_name, "workdir": str(workdir),
                "normal_termination": False, "results": []}

    print(f"[multi_system] adding result objects + evaluating...")
    added = _add_result_objects(mech)
    for line in added:
        print(f"  {line}")
    summary = _result_summary(mech)
    return {
        "system": system_name,
        "workdir": str(workdir),
        "normal_termination": True,
        "results": summary,
    }


def solve_all(wb, only_lsdyna: bool = True) -> list[dict]:
    """Solve every (LS-DYNA) system in the project, in order."""
    systems = list_systems(wb)
    if only_lsdyna:
        systems = [s for s in systems if s["DisplayText"].startswith("LS-DYNA")
                   or "lsdyna" in s["DisplayText"].lower()
                   or "claude_" in s["DisplayText"]]
    print(f"[multi_system] solving {len(systems)} system(s):")
    for s in systems:
        print(f"  - {s['Name']} ('{s['DisplayText']}')")

    results = []
    for s in systems:
        try:
            results.append(solve_in_place(wb, s["Name"]))
        except Exception as e:
            results.append({"system": s["Name"], "error": str(e)})
    return results


# ------------------------------------------------------------------------ CLI

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="List all systems in the project")

    p_dup = sub.add_parser("duplicate", help="Duplicate an existing system")
    p_dup.add_argument("--from", dest="src", default="SYS")
    p_dup.add_argument("--display", default=None,
                       help="Display name for the new system")

    p_solve = sub.add_parser("solve", help="Solve one system in-place")
    p_solve.add_argument("system")

    sub.add_parser("solve-all", help="Solve every LS-DYNA system")

    p_del = sub.add_parser("delete", help="Delete a system")
    p_del.add_argument("--name", required=True)

    p_rn = sub.add_parser("rename", help="Set a system's DisplayText")
    p_rn.add_argument("--name", required=True)
    p_rn.add_argument("--display", required=True)

    ap.add_argument("--wb-port", type=int, default=DEFAULT_WB_PORT)
    args = ap.parse_args()

    wb, _ = attach(args.wb_port)

    if args.cmd == "list":
        for s in list_systems(wb):
            print(f"  {s['Name']:8s}  '{s['DisplayText']}'  ({s['Solver']})")
    elif args.cmd == "duplicate":
        new_name = duplicate_system(wb, source=args.src, display=args.display)
        print(f"created: {new_name}  display='{args.display or '(default)'}'")
    elif args.cmd == "solve":
        out = solve_in_place(wb, args.system)
        print()
        print(json.dumps(out, indent=2))
    elif args.cmd == "solve-all":
        all_out = solve_all(wb)
        print()
        print(json.dumps(all_out, indent=2))
    elif args.cmd == "delete":
        delete_system(wb, args.name)
        print(f"deleted: {args.name}")
    elif args.cmd == "rename":
        rename_system(wb, args.name, args.display)
        print(f"renamed: {args.name} -> '{args.display}'")


if __name__ == "__main__":
    main()
