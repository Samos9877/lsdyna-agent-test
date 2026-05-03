"""Material verification loop runner.

For each material card in a queue:
  1. Set up a per-material run dir
  2. Copy the rig template + material card into it
  3. Run the headless solver (lsdyna_runner)
  4. Parse results (parse_results + soil_post)
  5. Aggregate metrics into a comparison DataFrame
  6. Save plots + summary CSV

Usage:
    python -m verify.verify_materials \
        --rig rigs/mat79_soil_unit/rig_template.k \
        --materials materials/mat_001_steel.k \
        --out-dir verify/reports/<run_label>

For a queue of materials, repeat --materials.

Designed for Sam's MAT_079 soil unit-test workflow but rig-agnostic — point
it at any rig with an *INCLUDE material.k slot and any compatible material.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

# Path bootstrap so this works whether invoked as a module or a script
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lsdyna_runner import run_dyna  # noqa: E402
from verify.soil_post import compute_soil_metrics  # noqa: E402


def slug(material_path: Path) -> str:
    return material_path.stem  # 'mat_001_steel'


def setup_run_dir(rig: Path, material: Path, run_dir: Path) -> Path:
    """Create run_dir and copy rig + material into it as 'rig.k' + 'material.k'.

    Returns the path to the rig copy (which is what lsdyna_runner will execute).
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    rig_dst = run_dir / "rig.k"
    mat_dst = run_dir / "material.k"
    shutil.copy2(rig, rig_dst)
    shutil.copy2(material, mat_dst)
    return rig_dst


def run_one(rig: Path, material: Path, out_root: Path) -> dict:
    """Run one material against the rig, return a result record."""
    label = slug(material)
    run_dir = out_root / label
    print(f"\n[verify] === {label} ===")
    print(f"[verify]   rig:      {rig.name}")
    print(f"[verify]   material: {material.name}")
    print(f"[verify]   run_dir:  {run_dir}")

    rig_in_run = setup_run_dir(rig, material, run_dir)
    t0 = time.time()
    try:
        result = run_dyna(rig_in_run, working_directory=run_dir, ncpu=1, memory_mb=40)
        wall_seconds = time.time() - t0
        ok = result.returncode == 0
        normal_term = "N o r m a l" in (result.stdout or "")[-3000:]
    except Exception as e:
        return {
            "material": label,
            "ok": False,
            "normal_termination": False,
            "wall_seconds": time.time() - t0,
            "error": str(e),
            "metrics": {},
        }

    # Post-process if the run produced anything
    metrics = {}
    if normal_term and (run_dir / "d3plot").exists():
        try:
            metrics = compute_soil_metrics(run_dir)
        except Exception as e:
            metrics = {"post_error": str(e)[:200]}

    return {
        "material": label,
        "ok": ok,
        "normal_termination": normal_term,
        "wall_seconds": wall_seconds,
        "metrics": metrics,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rig", required=True, type=Path,
                    help="Path to a rig template .k file with *INCLUDE material.k")
    ap.add_argument("--materials", required=True, nargs="+", type=Path,
                    help="One or more material .k files to verify")
    ap.add_argument("--out-dir", type=Path, default=None,
                    help="Output root for per-material run dirs and the summary. "
                         "Default: verify/reports/<timestamp>")
    args = ap.parse_args()

    out_root = args.out_dir or (
        ROOT / "verify" / "reports" / datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    out_root.mkdir(parents=True, exist_ok=True)
    print(f"[verify] out_root: {out_root}")

    records = []
    for mat in args.materials:
        records.append(run_one(args.rig.resolve(), mat.resolve(), out_root))

    # Summary
    summary = {
        "rig": str(args.rig),
        "n_materials": len(args.materials),
        "n_normal_term": sum(1 for r in records if r["normal_termination"]),
        "results": records,
    }
    (out_root / "summary.json").write_text(json.dumps(summary, indent=2, default=str))

    print("\n[verify] === SUMMARY ===")
    print(f"  rig:                {args.rig.name}")
    print(f"  materials run:      {summary['n_materials']}")
    print(f"  normal terminations:{summary['n_normal_term']}")
    print(f"  out_root:           {out_root}")
    for r in records:
        status = "OK" if r["normal_termination"] else "FAIL"
        wall = r.get("wall_seconds", 0)
        print(f"   - {r['material']:30s} {status:4s} wall={wall:.1f}s")
        for k, v in (r.get("metrics") or {}).items():
            if isinstance(v, (int, float)):
                print(f"        {k:24s} = {v:.6g}")
            else:
                print(f"        {k:24s} = {v}")
    print(f"\n  summary.json: {out_root / 'summary.json'}")


if __name__ == "__main__":
    main()
