"""Parse LS-DYNA results from a run directory.

Two paths:
1. ASCII parsing of `elout` for element stress history (LLM-friendly, no deps)
2. Binary parsing of `d3plot` via lasso-python (full state data)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def parse_elout_stress(elout_path: Path, eid: int = 1, ipt: int = 1):
    """Extract (time, sig_xx, sig_yy, sig_zz) history for one element/integration point.

    Returns list of (time, sxx, syy, szz) tuples.
    """
    text = elout_path.read_text()
    # Each block starts with "for time step <n> ( at time <T> )"
    # Then has lines like " {ipt} elastic   {sxx} {syy} {szz} ..."
    # LS-DYNA uses letter-spacing on "f o r   t i m e   s t e p" but NOT inside "(at time ...)"
    time_re = re.compile(r"\(\s*at\s+time\s+([0-9eE+\-.]+)\s*\)")
    blocks = re.split(r"e l e m e n t   s t r e s s", text)
    results = []
    for block in blocks[1:]:
        m_time = time_re.search(block)
        if not m_time:
            continue
        t = float(m_time.group(1))
        # Find the line for this element + ipt
        # Format: "       1-      1" then lines of stress data
        # We want the line starting with the ipt number after "{eid}-{matid}"
        lines = block.splitlines()
        in_target_element = False
        for line in lines:
            stripped = line.strip()
            if re.match(rf"^{eid}-\s*\d+\s*$", stripped):
                in_target_element = True
                continue
            if in_target_element:
                # Stress line: "<ipt> [<state>] <sxx> <syy> <szz> <sxy> <syz> <szx> <effsg> <yield>"
                # State column is present for MAT_001 ("elastic") but blank for MAT_075.
                # Parse all floats and take the last 8 as the stress block.
                tokens = stripped.split()
                if not tokens or tokens[0] != str(ipt):
                    continue
                floats = []
                for tok in tokens[1:]:
                    try:
                        floats.append(float(tok))
                    except ValueError:
                        pass
                if len(floats) >= 8:
                    sxx, syy, szz = floats[-8], floats[-7], floats[-6]
                    results.append((t, sxx, syy, szz))
                    in_target_element = False
                    break
    return results


def parse_d3plot_with_lasso(d3plot_path: Path):
    """Read d3plot via lasso-python and return basic state info."""
    from lasso.dyna import D3plot, ArrayType
    d3 = D3plot(str(d3plot_path))
    arrays = d3.arrays
    times = arrays.get(ArrayType.global_timesteps)
    n_states = len(times) if times is not None else 0
    info = {
        "n_states": n_states,
        "time_range": (float(times[0]), float(times[-1])) if n_states else None,
        "available_arrays": sorted(arrays.keys()),
    }
    # Element stress, if present
    if ArrayType.element_solid_stress in arrays:
        stress = arrays[ArrayType.element_solid_stress]
        # shape: (n_states, n_elements, n_int_points, 6)
        info["stress_shape"] = stress.shape
        # Element 1 (index 0), int point 1 (index 0), all components, all states
        info["e1_szz_history"] = [
            (float(times[i]), float(stress[i, 0, 0, 2])) for i in range(n_states)
        ]
    return info


def main():
    if len(sys.argv) < 2:
        print("Usage: parse_results.py <run_dir>")
        sys.exit(1)
    run_dir = Path(sys.argv[1])
    elout = run_dir / "elout"
    d3plot = run_dir / "d3plot"

    print(f"Parsing run: {run_dir}\n")

    if elout.exists():
        print("=== ASCII (elout) ===")
        hist = parse_elout_stress(elout, eid=1, ipt=1)
        print(f"  {len(hist)} state(s) found for element 1")
        if hist:
            print(f"  {'time':>10} {'sig_xx':>12} {'sig_yy':>12} {'sig_zz':>12}")
            for t, sxx, syy, szz in hist[::max(1, len(hist) // 10)]:
                print(f"  {t:10.4e} {sxx:12.4e} {syy:12.4e} {szz:12.4e}")
            t_last, _, _, szz_last = hist[-1]
            print(f"  Final sig_zz at t={t_last:.4e}: {szz_last:.4f} MPa")
    else:
        print("(no elout)")

    print()

    if d3plot.exists():
        print("=== Binary (d3plot via lasso-python) ===")
        try:
            info = parse_d3plot_with_lasso(d3plot)
            print(f"  states: {info['n_states']}, time range: {info['time_range']}")
            print(f"  stress array shape: {info.get('stress_shape')}")
            hist = info.get("e1_szz_history", [])
            if hist:
                print(f"  Element 1 sig_zz history (every Nth state):")
                for t, szz in hist[::max(1, len(hist) // 10)]:
                    print(f"    t={t:.4e}  sig_zz={szz:12.4e} MPa")
        except Exception as e:
            print(f"  ERROR: {e}")
    else:
        print("(no d3plot)")


if __name__ == "__main__":
    main()
