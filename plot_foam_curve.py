"""Plot the MAT_075 EPS foam stress-strain curve from run02."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from lasso.dyna import D3plot, ArrayType

ROOT = Path(__file__).parent
RUN = ROOT / "run02"

d3 = D3plot(str(RUN / "d3plot"))
times = d3.arrays[ArrayType.global_timesteps]
stress = d3.arrays[ArrayType.element_solid_stress]  # (n_states, 1, 1, 6)
nodes = d3.arrays.get(ArrayType.node_displacement)  # (n_states, n_nodes, 3)

# Stress sig_zz on element 1, ipt 1
szz = stress[:, 0, 0, 2]

# Engineering strain: top-face avg z displacement / initial height (1 mm)
# Top face nodes are 4..7 in 0-indexed (LS-DYNA nodes 5-8)
top_uz = nodes[:, 4:8, 2].mean(axis=1)
eng_strain = -top_uz / 1.0  # compression positive

fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

axes[0].plot(times, -szz, "o-", color="#c0392b", lw=2, ms=4)
axes[0].set_xlabel("Time (ms)")
axes[0].set_ylabel(r"$-\sigma_{zz}$ (MPa)")
axes[0].set_title("Stress vs time")
axes[0].grid(alpha=0.3)

axes[1].plot(eng_strain * 100, -szz, "o-", color="#2980b9", lw=2, ms=4)
axes[1].set_xlabel("Engineering compressive strain (%)")
axes[1].set_ylabel(r"$-\sigma_{zz}$ (MPa)")
axes[1].set_title("MAT_075 EPS22 — single-element compression")
axes[1].grid(alpha=0.3)
axes[1].axvline(50, color="gray", ls="--", lw=1, alpha=0.5)
axes[1].text(51, axes[1].get_ylim()[1]*0.7, "densification onset\n(prescribed)", fontsize=8, color="gray")

fig.suptitle("Claude → LS-DYNA round trip: MAT_075 BILKHU/DUBOIS_FOAM", fontsize=11)
fig.tight_layout()

out = ROOT / "mat075_compression.png"
fig.savefig(out, dpi=130, bbox_inches="tight")
print(f"Wrote {out}")
print(f"Final state: strain={eng_strain[-1]*100:.1f}%, stress={-szz[-1]:.3f} MPa")
