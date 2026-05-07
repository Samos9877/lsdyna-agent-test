"""First-principles physical sanity checks for FEA simulation results.

Established 2026-05-06 after a contact-leak in the geofoam ball-indent run
went unflagged: the foam-top center node moved 0.029 in while the ball moved
0.25 in (8.6× mismatch impossible for a confined incompressible foam without
mass loss), and the post-processor reported metrics as if everything was
fine. The lesson: **physics checks gate the narrative.** A failed check
kills the report header. A passed one earns the right to interpret.

Layered design:
  - This module provides **generic, rig-agnostic primitives** (energy
    balance, node-set fixed, surfaces coincident, value in range, symmetry).
  - Each rig's `post.py` defines its **rig-specific expected physics**
    (e.g. uniaxial cube: q/p=3 with ν=0; geofoam_indent: foam_z_at_ball_origin
    ≈ ball_bottom_z) and composes the right primitives.
  - `verify_materials.py` orchestrates and leads its report with the check
    summary, not the metrics.

Usage:

    from verify.sanity import (
        SanityCheck, SanityReport,
        check_node_set_fixed, check_z_coincidence,
        check_value_in_range, check_displacement_follows_curve,
        check_energy_balance,
    )

    report = SanityReport(run_label="geofoam_indent_v12")
    report.add(check_node_set_fixed(positions, foam_bottom_idx, "foam bottom (z=0) BC"))
    report.add(check_z_coincidence(positions, ball_bottom_idx, foam_top_idx,
                                    tolerance=0.0125, name="contact: ball<->foam"))
    print(report)
    if not report.all_passed():
        ...  # don't trust metrics
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Literal, Sequence

import numpy as np


# ─── Result types ───────────────────────────────────────────────────────────────

Status = Literal["PASS", "FAIL", "WARN"]


@dataclass
class SanityCheck:
    """One physical sanity check result."""
    name: str
    status: Status
    message: str
    value: float | None = None
    expected: float | None = None
    tolerance: float | None = None

    def is_pass(self) -> bool:
        return self.status == "PASS"

    def is_fail(self) -> bool:
        return self.status == "FAIL"

    def line(self) -> str:
        glyph = {"PASS": "[PASS]", "FAIL": "[FAIL]", "WARN": "[WARN]"}[self.status]
        head = f"{glyph} {self.name}"
        if self.value is not None and self.tolerance is not None:
            head += f"  ({self.value:.4g} vs tol {self.tolerance:.4g})"
        if self.message:
            return f"{head}\n        {self.message}"
        return head


@dataclass
class SanityReport:
    """Collection of checks for a single run, with a clean summary."""
    run_label: str = ""
    checks: list[SanityCheck] = field(default_factory=list)

    def add(self, check: SanityCheck) -> None:
        self.checks.append(check)

    def all_passed(self) -> bool:
        return all(c.is_pass() for c in self.checks)

    def fail_count(self) -> int:
        return sum(1 for c in self.checks if c.is_fail())

    def warn_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "WARN")

    def pass_count(self) -> int:
        return sum(1 for c in self.checks if c.is_pass())

    def summary_line(self) -> str:
        n = len(self.checks)
        if n == 0:
            return "(no checks defined)"
        parts = []
        if self.fail_count():
            parts.append(f"{self.fail_count()} FAIL")
        if self.warn_count():
            parts.append(f"{self.warn_count()} WARN")
        parts.append(f"{self.pass_count()} pass")
        return " | ".join(parts) + f" of {n}"

    def __str__(self) -> str:
        out = []
        header = f"=== Sanity checks: {self.run_label} ===" if self.run_label else "=== Sanity checks ==="
        out.append(header)
        out.append(f"  Summary: {self.summary_line()}")
        out.append("")
        # FAILs first, then WARNs, then PASSes — most actionable on top
        for c in self.checks:
            if c.is_fail():
                out.append(c.line())
        for c in self.checks:
            if c.status == "WARN":
                out.append(c.line())
        for c in self.checks:
            if c.is_pass():
                out.append(c.line())
        return "\n".join(out)


# ─── Generic primitives ────────────────────────────────────────────────────────


def check_node_set_fixed(
    positions: np.ndarray,
    node_indices: Sequence[int],
    name: str = "node set fixed",
    tolerance: float = 1e-4,
) -> SanityCheck:
    """Verify a set of nodes (e.g. fixed-support face) didn't move from their initial positions.

    `positions` is the lasso `node_displacement` array (n_states, n_nodes, 3) which
    actually holds positions. We compute max |delta| over time vs t=0 over the given indices.
    """
    if not len(node_indices):
        return SanityCheck(name, "WARN", "no nodes in set", 0.0, 0.0, tolerance)
    p0 = positions[0, node_indices, :]
    delta = positions[:, node_indices, :] - p0[None, :, :]
    max_displacement = float(np.max(np.linalg.norm(delta, axis=-1)))
    status: Status = "PASS" if max_displacement <= tolerance else "FAIL"
    msg = f"max |delta| = {max_displacement:.4g} in over {len(node_indices)} nodes"
    if status == "FAIL":
        msg += f" — fixed BC not enforced"
    return SanityCheck(name, status, msg, max_displacement, 0.0, tolerance)


def check_z_coincidence(
    positions: np.ndarray,
    node_indices_a: Sequence[int],
    node_indices_b: Sequence[int],
    tolerance: float,
    name: str = "z-coincidence",
    use_min_a: str = "min_z",
    use_max_b: str = "max_z",
    states: slice | None = None,
) -> SanityCheck:
    """Check that the lowest-z point of set A meets the highest-z point of set B
    (or matches a chosen aggregation) within tolerance over all states.

    For ball-on-foam: A = ball nodes (we want min z = ball bottom),
                      B = foam top nodes near origin (we want max z = foam top).
    The expected behavior is min(z_A) ≈ max(z_B) at every time when in contact.
    Gap > tolerance = contact leak.
    """
    if states is None:
        states = slice(None)

    def _agg(arr: np.ndarray, mode: str, axis: int) -> np.ndarray:
        if mode == "min_z":
            return arr[..., 2].min(axis=axis)
        if mode == "max_z":
            return arr[..., 2].max(axis=axis)
        if mode == "mean_z":
            return arr[..., 2].mean(axis=axis)
        raise ValueError(f"unknown agg mode: {mode}")

    z_a = _agg(positions[states][:, node_indices_a, :], use_min_a, axis=-1)
    z_b = _agg(positions[states][:, node_indices_b, :], use_max_b, axis=-1)
    gap = z_a - z_b   # positive if A is above B (no penetration); negative if A penetrates B

    # We allow A ≥ B (no-contact gap), but penalize A << B (penetration into B)
    max_penetration = float(max(0.0, -gap.min()))
    status: Status = "PASS" if max_penetration <= tolerance else "FAIL"
    msg = (
        f"max penetration of A into B over time = {max_penetration:.4g} in "
        f"(set A: {len(node_indices_a)} nodes, set B: {len(node_indices_b)} nodes)"
    )
    if status == "FAIL":
        msg += " — contact is leaking"
    return SanityCheck(name, status, msg, max_penetration, 0.0, tolerance)


def check_displacement_follows_curve(
    positions: np.ndarray,
    times: np.ndarray,
    node_indices: Sequence[int],
    component: int,                         # 0=x, 1=y, 2=z
    expected_curve: Callable[[np.ndarray], np.ndarray],
    name: str = "prescribed motion enforced",
    tolerance: float = 1e-3,
    aggregation: str = "mean",              # 'mean'|'min'|'max'
) -> SanityCheck:
    """Check that the chosen component of the chosen nodes follows expected_curve(t)
    (within tolerance) — i.e. that a *BOUNDARY_PRESCRIBED_MOTION_* actually got enforced.
    """
    if not len(node_indices):
        return SanityCheck(name, "WARN", "no nodes in set", tolerance=tolerance)

    init = positions[0, node_indices, component]
    track = positions[:, node_indices, component] - init[None, :]   # displacement vs t=0
    if aggregation == "mean":
        actual = track.mean(axis=-1)
    elif aggregation == "min":
        actual = track.min(axis=-1)
    elif aggregation == "max":
        actual = track.max(axis=-1)
    else:
        raise ValueError(f"unknown aggregation: {aggregation}")

    expected = expected_curve(times)
    err = np.abs(actual - expected)
    max_err = float(err.max())
    status: Status = "PASS" if max_err <= tolerance else "FAIL"
    msg = f"max |actual - prescribed| = {max_err:.4g} in over {len(times)} states"
    if status == "FAIL":
        msg += " — prescribed motion BC not honored"
    return SanityCheck(name, status, msg, max_err, 0.0, tolerance)


def check_value_in_range(
    value: float,
    min_val: float,
    max_val: float,
    name: str,
    units: str = "",
    fail_outside: bool = True,
) -> SanityCheck:
    """Check a scalar lies in [min_val, max_val]. WARN by default if outside;
    FAIL if `fail_outside`."""
    inside = min_val <= value <= max_val
    if inside:
        return SanityCheck(
            name, "PASS",
            f"value = {value:.4g}{units} in [{min_val:.4g}, {max_val:.4g}]",
            value=value, expected=(min_val + max_val) / 2.0,
            tolerance=(max_val - min_val) / 2.0,
        )
    status: Status = "FAIL" if fail_outside else "WARN"
    return SanityCheck(
        name, status,
        f"value = {value:.4g}{units} OUTSIDE [{min_val:.4g}, {max_val:.4g}]",
        value=value, expected=(min_val + max_val) / 2.0,
        tolerance=(max_val - min_val) / 2.0,
    )


def check_symmetry_xy(
    positions: np.ndarray,
    name: str = "x-y symmetry",
    tolerance: float = 1e-3,
    state: int = -1,
) -> SanityCheck:
    """For models with x and y symmetry (mirror through origin), the position
    at +x should mirror -x. We check by pairing each node with its closest
    mirror partner and comparing.

    Useful for detecting asymmetric contact engagement, asymmetric mesh,
    or asymmetric BCs that snuck in.
    """
    p = positions[state]   # (n_nodes, 3)
    # For each node, find its mirror partner under x-reflection (same |x|, same y, same z, opposite x sign)
    n = p.shape[0]
    p_mirror_x = p.copy()
    p_mirror_x[:, 0] *= -1
    # KD-tree-free O(N²) is fine for <2000 nodes
    from scipy.spatial import cKDTree
    tree = cKDTree(p)
    dists, _ = tree.query(p_mirror_x, k=1)
    max_asym = float(dists.max())
    status: Status = "PASS" if max_asym <= tolerance else "WARN"
    msg = f"max |Δ to mirror partner| at state {state} = {max_asym:.4g} in"
    return SanityCheck(name, status, msg, max_asym, 0.0, tolerance)


def check_energy_balance(
    times: np.ndarray,
    internal_energy: np.ndarray,
    kinetic_energy: np.ndarray,
    external_work: np.ndarray | None = None,
    sliding_energy: np.ndarray | None = None,
    name: str = "energy balance",
    tolerance: float = 0.05,           # 5% mismatch warns
) -> SanityCheck:
    """For an explicit dynamics run, total energy should be approximately
    conserved (modulo damping, hourglass, contact friction). We check the
    relative error of (KE + IE) vs the work done by external loads if available,
    or check that the energies are bounded if not.
    """
    if external_work is not None and len(external_work) == len(times):
        residual = (internal_energy + kinetic_energy) - external_work
        rel = np.abs(residual) / (np.abs(external_work) + 1e-12)
        max_rel = float(rel.max())
        status: Status = "PASS" if max_rel <= tolerance else "WARN"
        msg = f"max |IE+KE - W_ext|/|W_ext| = {max_rel:.4g}"
        return SanityCheck(name, status, msg, max_rel, 0.0, tolerance)
    # No external-work history: just sanity-check magnitudes
    ie_max = float(np.max(np.abs(internal_energy)))
    ke_max = float(np.max(np.abs(kinetic_energy)))
    status = "PASS" if (np.isfinite(ie_max) and np.isfinite(ke_max)) else "FAIL"
    msg = f"IE_max = {ie_max:.4g}, KE_max = {ke_max:.4g} (no external-work history available)"
    return SanityCheck(name, status, msg, max(ie_max, ke_max), tolerance=tolerance)


def check_kinetic_energy_quasistatic(
    times: np.ndarray,
    internal_energy: np.ndarray,
    kinetic_energy: np.ndarray,
    name: str = "quasi-static (KE/IE small)",
    threshold: float = 0.05,           # KE should be <5% of IE for quasi-static
) -> SanityCheck:
    """Check that kinetic energy stays small relative to internal energy
    over the run — confirms the simulation is quasi-static rather than
    dynamic-impact."""
    # Only compare where IE is nontrivial
    mask = internal_energy > internal_energy.max() * 1e-3
    if not mask.any():
        return SanityCheck(name, "WARN", "internal energy never grew large enough to evaluate ratio", tolerance=threshold)
    ratio = kinetic_energy[mask] / internal_energy[mask]
    max_ratio = float(np.max(np.abs(ratio)))
    status: Status = "PASS" if max_ratio <= threshold else "WARN"
    msg = f"max KE/IE = {max_ratio:.4g} (quasi-static if < {threshold})"
    return SanityCheck(name, status, msg, max_ratio, 0.0, threshold)


# ─── Helpers for indexing nodes from positions ─────────────────────────────────


def nodes_at_z(positions: np.ndarray, z_target: float, tol: float = 1e-3) -> np.ndarray:
    """Return indices of nodes whose initial z (state 0) is within `tol` of `z_target`."""
    z0 = positions[0, :, 2]
    return np.where(np.abs(z0 - z_target) < tol)[0]


def nodes_in_z_band(positions: np.ndarray, z_min: float, z_max: float) -> np.ndarray:
    z0 = positions[0, :, 2]
    return np.where((z0 >= z_min) & (z0 <= z_max))[0]


def nodes_near_xy(positions: np.ndarray, x: float, y: float, radius: float,
                   in_set: Iterable[int] | None = None) -> np.ndarray:
    """Return indices of nodes whose initial (x, y) is within `radius` of (x, y).
    Optionally restrict to `in_set` (e.g. only the foam top face)."""
    p0 = positions[0]
    dist = np.sqrt((p0[:, 0] - x) ** 2 + (p0[:, 1] - y) ** 2)
    candidates = np.where(dist < radius)[0]
    if in_set is not None:
        in_set_arr = np.asarray(list(in_set))
        candidates = np.intersect1d(candidates, in_set_arr)
    return candidates
