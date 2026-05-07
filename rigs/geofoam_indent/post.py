"""Post-process the geofoam ball-indent run.

Outputs:
  - load_deflection.png — force vs indentation depth (push + lift)
  - time_history.png — ball z, contact force, and energy vs time
  - metrics.json — summary numbers

Reads:
  rcforc — contact force history (SURFA=slave/ball, SURFB=master/foam)
  glstat — global energy/timestep history
  d3plot — full state (via lasso) for residual indent depth
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

# Parameters from generate_deck.py — keep in sync if you change the rig
BALL_RADIUS = 0.84      # in
INITIAL_GAP = 0.05      # in
FOAM_TOP_Z = 2.0        # in (block height)
INDENT_DEPTH = 0.3      # in (max prescribed) — keep in sync with generate_deck.py
PUSH_TIME = 1.0         # s
ENDTIME = 2.0           # s

BALL_BOTTOM_T0 = FOAM_TOP_Z + INITIAL_GAP   # 2.05 in


def parse_rcforc(path: Path):
    """Return arrays (time, fz_slave, fz_master). The contact normal force on
    the foam top equals -fz of SURFB (master, foam) = fz of SURFA (slave, ball)."""
    line_re = re.compile(
        r"SURF([AB])\s+\d+\s+time\s+(\S+)\s+x\s+(\S+)\s+y\s+(\S+)\s+z\s+(\S+)"
    )
    times = []
    fz_a = []   # slave (ball)
    fz_b = []   # master (foam)
    for line in path.read_text().splitlines():
        m = line_re.search(line)
        if not m:
            continue
        which, t, x, y, z = m.groups()
        t = float(t)
        z = float(z)
        if which == "A":
            times.append(t)
            fz_a.append(z)
        else:
            fz_b.append(z)
    n = min(len(times), len(fz_a), len(fz_b))
    return np.array(times[:n]), np.array(fz_a[:n]), np.array(fz_b[:n])


def parse_glstat(path: Path):
    """Return arrays (time, total_energy, internal_energy, kinetic_energy, dt)."""
    txt = path.read_text()
    blocks = re.split(r"^\s*time\s*\.+\s*", txt, flags=re.MULTILINE)
    times, ie, ke, te, dt = [], [], [], [], []
    for b in blocks[1:]:
        # The first token of each block (after the regex strip) is the time
        # then we want internal energy, kinetic energy, total energy, time step
        m_time = re.match(r"\s*([\dEe.+\-]+)", b)
        if not m_time:
            continue
        t = float(m_time.group(1))
        m_int = re.search(r"internal energy\s*\.+\s*([\dEe.+\-]+)", b)
        m_kin = re.search(r"kinetic energy\s*\.+\s*([\dEe.+\-]+)", b)
        m_tot = re.search(r"total energy\s*\.+\s*([\dEe.+\-]+)", b)
        m_dt  = re.search(r"time step\s*\.+\s*([\dEe.+\-]+)", b)
        if m_int and m_kin:
            times.append(t)
            ie.append(float(m_int.group(1)))
            ke.append(float(m_kin.group(1)))
            te.append(float(m_tot.group(1)) if m_tot else 0.0)
            dt.append(float(m_dt.group(1)) if m_dt else 0.0)
    return np.array(times), np.array(ie), np.array(ke), np.array(te), np.array(dt)


def prescribed_ball_displacement(t):
    """Triangular: 0 -> -INDENT_DEPTH at PUSH_TIME -> 0 at ENDTIME."""
    out = np.zeros_like(t)
    push = t <= PUSH_TIME
    lift = ~push
    out[push] = -INDENT_DEPTH * (t[push] / PUSH_TIME)
    out[lift] = -INDENT_DEPTH * (1.0 - (t[lift] - PUSH_TIME) / (ENDTIME - PUSH_TIME))
    return out


def main():
    here = Path(__file__).resolve().parent
    # Most recent run dir (preferred) or fallback
    candidates = sorted(
        (here.parent.parent / "verify" / "reports").glob("geofoam_indent*"),
        key=lambda p: p.stat().st_mtime
    )
    if not candidates:
        raise SystemExit("No geofoam_indent_* run dirs found in verify/reports/")
    run_dir = candidates[-1]
    print(f"[post] run_dir: {run_dir}")

    # 1. rcforc -> contact normal force history
    rcforc = run_dir / "rcforc"
    times, fz_slave, fz_master = parse_rcforc(rcforc)
    # Contact force on the foam (push DOWN is positive convention here)
    F_contact = -fz_master   # foam reaction; positive = upward push on ball, equal-opposite downward on foam
    # Use slave (ball) magnitude: ball pushes foam down with -fz_slave
    F_ball_on_foam = -fz_slave
    print(f"[post] rcforc: {len(times)} time samples, t={times[0]:.4f} -> {times[-1]:.4f}")

    # 2. Ball indentation depth (analytical from prescribed motion)
    ball_disp = prescribed_ball_displacement(times)
    ball_bottom = BALL_BOTTOM_T0 + ball_disp
    indent_depth = FOAM_TOP_Z - ball_bottom    # positive when ball is below foam top
    indent_depth = np.maximum(indent_depth, 0.0)

    # 3. Read d3plot for actual final ball position + foam residual
    foam_top_history = None
    try:
        from lasso.dyna import D3plot, ArrayType
        d3 = D3plot(str(run_dir / "d3plot"))
        nodes_pos = np.asarray(d3.arrays[ArrayType.node_displacement])  # (n_states, n_nodes, 3) - actually positions
        d3_times = np.asarray(d3.arrays[ArrayType.global_timesteps])
        # Foam top nodes: those with initial z = FOAM_TOP_Z
        z0 = nodes_pos[0, :, 2]
        foam_top_idx = np.where(np.abs(z0 - FOAM_TOP_Z) < 1e-3)[0]
        # Among foam top nodes, pick the one closest to (0, 0) — the indented one
        xy_dist = np.sqrt(nodes_pos[0, foam_top_idx, 0]**2 + nodes_pos[0, foam_top_idx, 1]**2)
        center_node = foam_top_idx[np.argmin(xy_dist)]
        foam_center_z = nodes_pos[:, center_node, 2]
        residual_indent = FOAM_TOP_Z - foam_center_z[-1]
        peak_indent = FOAM_TOP_Z - foam_center_z.min()
        print(f"[post] foam center node {center_node}: peak indent {peak_indent:.4f} in, residual {residual_indent:.4f} in")
        # Also: ball z (any ball node — they all move together)
        # Find a node that started above z=2 (ball nodes)
        ball_mask = z0 > FOAM_TOP_Z + 0.1
        ball_idx0 = int(np.where(ball_mask)[0][0])
        ball_z = nodes_pos[:, ball_idx0, 2]
        foam_top_history = (d3_times, foam_center_z, ball_z)
    except Exception as e:
        print(f"[post] d3plot read failed: {e}")
        residual_indent = float('nan')
        peak_indent = float('nan')

    # 4. glstat
    try:
        gt, ie, ke, te, dt = parse_glstat(run_dir / "glstat")
        print(f"[post] glstat: {len(gt)} samples, internal energy peaked at {ie.max():.4f}")
    except Exception as e:
        print(f"[post] glstat parse failed: {e}")
        gt = np.array([])
        ie = ke = te = dt = np.array([])

    # 5. Plots
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # Plot 1: load-deflection curve (force vs indent depth, with push/lift colored)
    push_mask = times <= PUSH_TIME
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    ax = axes[0]
    ax.plot(indent_depth[push_mask], F_contact[push_mask], "-", color="#c0392b", lw=1.6, label="push")
    ax.plot(indent_depth[~push_mask], F_contact[~push_mask], "-", color="#2980b9", lw=1.6, label="lift")
    ax.set_xlabel("Ball indentation depth (in)")
    ax.set_ylabel("Contact force (lbf)")
    ax.set_title("Load-deflection curve (push -> lift)")
    ax.grid(alpha=0.3); ax.legend()
    ax.axhline(0, color="gray", lw=0.5, ls=":")

    # Plot 2: time history of force + ball z
    ax2 = axes[1]
    ax2.plot(times, F_contact, "-", color="#c0392b", lw=1.4, label="contact force (lbf)")
    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel("Force (lbf)", color="#c0392b")
    ax2.tick_params(axis="y", labelcolor="#c0392b")
    ax2.axvline(PUSH_TIME, color="gray", lw=0.5, ls="--")
    ax2.text(PUSH_TIME, ax2.get_ylim()[1]*0.9, " end of push", fontsize=8, color="gray")
    ax2b = ax2.twinx()
    ax2b.plot(times, indent_depth, "-", color="#2980b9", lw=1.4, label="indent depth (in)")
    ax2b.set_ylabel("Indent depth (in)", color="#2980b9")
    ax2b.tick_params(axis="y", labelcolor="#2980b9")
    ax2.set_title("Time history")
    ax2.grid(alpha=0.3)

    fig.suptitle(f"Geofoam ball-indent ({run_dir.name}) — MAT_075 EPS-12, 1.68\" rigid steel ball", fontsize=11)
    fig.tight_layout()
    out_png = run_dir / "load_deflection.png"
    fig.savefig(out_png, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"[post] wrote {out_png}")

    # Plot 3: foam center node z vs time (show the indent + recovery)
    if foam_top_history is not None:
        d3_times, foam_center_z, ball_z = foam_top_history
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.plot(d3_times, foam_center_z, "-o", color="#16a085", lw=1.5, ms=4, label="foam top center node")
        ax.plot(d3_times, ball_z - BALL_RADIUS, "-s", color="#8e44ad", lw=1.0, ms=3, label="ball bottom")
        ax.axhline(FOAM_TOP_Z, color="gray", lw=0.5, ls=":", label="foam top (initial)")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Z position (in)")
        ax.set_title("Foam center node + ball bottom over time")
        ax.grid(alpha=0.3); ax.legend()
        fig.tight_layout()
        out_png2 = run_dir / "foam_recovery.png"
        fig.savefig(out_png2, dpi=140, bbox_inches="tight")
        plt.close(fig)
        print(f"[post] wrote {out_png2}")

    # 6. metrics.json
    metrics = {
        "n_rcforc_samples": len(times),
        "peak_contact_force_lbf": float(F_contact.max()),
        "force_at_peak_indent_lbf": float(F_contact[push_mask].max()) if push_mask.any() else float("nan"),
        "peak_indent_depth_in_prescribed": float(indent_depth.max()),
        "peak_indent_depth_in_actual": float(peak_indent) if not np.isnan(peak_indent) else None,
        "residual_indent_depth_in": float(residual_indent) if not np.isnan(residual_indent) else None,
        "internal_energy_peak": float(ie.max()) if len(ie) else None,
    }
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(f"[post] metrics: {json.dumps(metrics, indent=2)}")


if __name__ == "__main__":
    main()
