"""Soil/foam unit-element post-processing.

For a single-element rig under prescribed displacement, extract the standard
soil-mechanics signals from the LS-DYNA d3plot:

  - Stress invariants:
      mean (effective) stress  p  = -(σ_xx + σ_yy + σ_zz) / 3
      deviatoric stress        q  = sqrt(3 J2)
                                  = sqrt(0.5 * [(σ_xx-σ_yy)² + (σ_yy-σ_zz)² + (σ_zz-σ_xx)²
                                                + 6(σ_xy² + σ_yz² + σ_zx²)])
  - Strain invariants (computed from nodal displacements):
      volumetric strain  ε_v = ε_xx + ε_yy + ε_zz   (small-strain proxy from face displacement)
      axial strain       ε_a = -u_top_z / L   (compression positive, single hex)
  - Stress paths in q-p space (the standard triaxial signature)
  - Histories of all of the above

This is rig-aware: it assumes a single hex element (eid=1, ipt=1) and a top-face
displacement BC. Will need to generalize when multi-element rigs come online.

Sign convention (geotech): compression positive for both stress and strain.
LS-DYNA convention: compression negative. We flip on read.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def _load_d3plot(run_dir: Path):
    """Return (times, sxx, syy, szz, sxy, syz, szx, displacement) arrays.

    sxx etc. are 1-D arrays of length n_states (single-element assumption).

    NOTE on lasso naming: `ArrayType.node_displacement` actually returns
    *node positions* in the deformed configuration, NOT displacements.
    We subtract the t=0 frame to get true displacement.
    """
    from lasso.dyna import D3plot, ArrayType

    d3 = D3plot(str(run_dir / "d3plot"))
    arrays = d3.arrays
    times = np.asarray(arrays[ArrayType.global_timesteps])
    stress = np.asarray(arrays[ArrayType.element_solid_stress])
    # shape: (n_states, n_elements, n_int_points, 6)  components: xx yy zz xy yz zx
    s = stress[:, 0, 0, :]
    sxx, syy, szz, sxy, syz, szx = (s[:, i] for i in range(6))
    positions = np.asarray(arrays[ArrayType.node_displacement])     # (n_states, n_nodes, 3)
    disp = positions - positions[0:1, :, :]                         # actual displacement
    return times, sxx, syy, szz, sxy, syz, szx, disp, positions


def stress_invariants(sxx, syy, szz, sxy, syz, szx):
    """Return (p, q) per state. Geotech sign convention: p>0 in compression.

    Mean stress       p = -(σ_xx + σ_yy + σ_zz) / 3
    Von Mises stress  q = sqrt( 0.5*[(σ_xx-σ_yy)² + (σ_yy-σ_zz)² + (σ_zz-σ_xx)²]
                                + 3*(σ_xy² + σ_yz² + σ_zx²) )
    The form above gives q directly — no additional sqrt(3) factor.
    """
    p = -(sxx + syy + szz) / 3.0
    q = np.sqrt(
        0.5 * ((sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2)
        + 3.0 * (sxy ** 2 + syz ** 2 + szx ** 2)
    )
    return p, q


def _identify_axis_faces(positions_t0):
    """Group the 8 cube corner-node indices by which axis-face they belong to.

    Returns dict mapping {'xmin','xmax','ymin','ymax','zmin','zmax'} -> list[int]
    using the t=0 reference positions of the nodes.
    """
    p0 = positions_t0
    return {
        "xmin": np.where(p0[:, 0] < p0[:, 0].mean())[0].tolist(),
        "xmax": np.where(p0[:, 0] > p0[:, 0].mean())[0].tolist(),
        "ymin": np.where(p0[:, 1] < p0[:, 1].mean())[0].tolist(),
        "ymax": np.where(p0[:, 1] > p0[:, 1].mean())[0].tolist(),
        "zmin": np.where(p0[:, 2] < p0[:, 2].mean())[0].tolist(),
        "zmax": np.where(p0[:, 2] > p0[:, 2].mean())[0].tolist(),
    }


def strains_from_displacement(disp, positions_t0):
    """Compute (eps_a, eps_v, eps_xx, eps_yy, eps_zz, top_idx) histories.

    Strains are engineering, COMPRESSION POSITIVE (geotech convention).
    Computed as Δ(face-mean position) / initial side length per axis.
    """
    faces = _identify_axis_faces(positions_t0)
    L_x = positions_t0[faces["xmax"], 0].mean() - positions_t0[faces["xmin"], 0].mean()
    L_y = positions_t0[faces["ymax"], 1].mean() - positions_t0[faces["ymin"], 1].mean()
    L_z = positions_t0[faces["zmax"], 2].mean() - positions_t0[faces["zmin"], 2].mean()

    # Stretch (current/initial), strain = -(stretch - 1) for compression-positive
    def axis_strain(disp_axis_max, disp_axis_min, L):
        return -((disp_axis_max - disp_axis_min)) / L

    eps_xx = axis_strain(disp[:, faces["xmax"], 0].mean(axis=1),
                         disp[:, faces["xmin"], 0].mean(axis=1), L_x)
    eps_yy = axis_strain(disp[:, faces["ymax"], 1].mean(axis=1),
                         disp[:, faces["ymin"], 1].mean(axis=1), L_y)
    eps_zz = axis_strain(disp[:, faces["zmax"], 2].mean(axis=1),
                         disp[:, faces["zmin"], 2].mean(axis=1), L_z)
    eps_v = eps_xx + eps_yy + eps_zz
    eps_a = eps_zz   # axial = z by convention for this rig
    top_idx = faces["zmax"]
    return eps_a, eps_v, eps_xx, eps_yy, eps_zz, top_idx


def compute_soil_metrics(run_dir: Path, init_height_mm: float = 25.4) -> dict:
    """Return a dict of summary metrics + write per-state CSV + plots.

    Metrics returned (intended for the verify summary table):
      - n_states, t_start, t_end
      - p_max, q_max
      - eps_a_max, eps_v_at_eps_a_max
      - q_over_p_at_max_q  (stress ratio at peak)
      - elastic_modulus_apparent  (initial slope, from first 3 states)

    Side effects:
      - Writes <run_dir>/post/history.csv
      - Writes <run_dir>/post/qp_path.png
      - Writes <run_dir>/post/strain_stress.png
    """
    times, sxx, syy, szz, sxy, syz, szx, disp, positions = _load_d3plot(run_dir)
    p, q = stress_invariants(sxx, syy, szz, sxy, syz, szx)
    eps_a, eps_v, eps_xx, eps_yy, eps_zz, top_idx = strains_from_displacement(disp, positions[0])

    # Apparent modulus from initial elastic slope (states 0..2)
    if len(eps_a) >= 3 and abs(eps_a[2] - eps_a[0]) > 1e-12:
        e_apparent = float((-szz[2] + szz[0]) / (eps_a[2] - eps_a[0]))
    else:
        e_apparent = float("nan")

    iqmax = int(np.argmax(q))

    metrics = {
        "n_states": int(len(times)),
        "t_start": float(times[0]),
        "t_end": float(times[-1]),
        "p_max": float(np.max(p)),
        "q_max": float(np.max(q)),
        "eps_a_max": float(np.max(eps_a)),
        "eps_v_at_eps_a_max": float(eps_v[int(np.argmax(eps_a))]),
        "q_over_p_at_qmax": float(q[iqmax] / p[iqmax]) if p[iqmax] != 0 else float("inf"),
        "E_apparent_initial": e_apparent,
    }

    # CSV + plots
    post_dir = run_dir / "post"
    post_dir.mkdir(exist_ok=True)
    csv_path = post_dir / "history.csv"
    with csv_path.open("w") as f:
        f.write("t,sxx,syy,szz,sxy,syz,szx,p,q,eps_a,eps_v,eps_xx,eps_yy,eps_zz\n")
        for i in range(len(times)):
            f.write(
                f"{times[i]:.6e},{sxx[i]:.6e},{syy[i]:.6e},{szz[i]:.6e},"
                f"{sxy[i]:.6e},{syz[i]:.6e},{szx[i]:.6e},"
                f"{p[i]:.6e},{q[i]:.6e},{eps_a[i]:.6e},{eps_v[i]:.6e},"
                f"{eps_xx[i]:.6e},{eps_yy[i]:.6e},{eps_zz[i]:.6e}\n"
            )

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # Plot 1: q-p stress path
        fig, ax = plt.subplots(figsize=(5.5, 5))
        ax.plot(p, q, "-o", color="#2980b9", lw=1.5, ms=3)
        ax.scatter([p[0]], [q[0]], color="green", s=40, zorder=5, label="t=0")
        ax.scatter([p[-1]], [q[-1]], color="red", s=40, zorder=5, label="t=end")
        ax.set_xlabel("Mean stress p (MPa)")
        ax.set_ylabel("Deviatoric stress q (MPa)")
        ax.set_title(f"q-p stress path — {run_dir.name}")
        ax.grid(alpha=0.3)
        ax.legend()
        ax.set_aspect("equal", adjustable="datalim")
        fig.tight_layout()
        fig.savefig(post_dir / "qp_path.png", dpi=120)
        plt.close(fig)

        # Plot 2: stress vs strain (axial) and volumetric vs axial strain
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
        axes[0].plot(eps_a * 100, -szz, "-o", color="#c0392b", lw=1.5, ms=3)
        axes[0].set_xlabel("Axial strain (%)")
        axes[0].set_ylabel("-σ_zz (MPa)")
        axes[0].set_title("Axial stress vs axial strain")
        axes[0].grid(alpha=0.3)
        axes[1].plot(eps_a * 100, eps_v * 100, "-o", color="#16a085", lw=1.5, ms=3)
        axes[1].set_xlabel("Axial strain (%)")
        axes[1].set_ylabel("Volumetric strain (%)")
        axes[1].set_title("Dilatancy: ε_v vs ε_a")
        axes[1].axhline(0, color="gray", ls=":", lw=0.5)
        axes[1].grid(alpha=0.3)
        fig.suptitle(run_dir.name, fontsize=10)
        fig.tight_layout()
        fig.savefig(post_dir / "strain_stress.png", dpi=120)
        plt.close(fig)
    except Exception as e:
        metrics["plot_error"] = str(e)[:200]

    # Drop a metrics.json for downstream tools
    (post_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    return metrics


if __name__ == "__main__":
    import sys
    run_dir = Path(sys.argv[1])
    print(json.dumps(compute_soil_metrics(run_dir), indent=2))
