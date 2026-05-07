"""LS-PrePost helpers — visualize d3plot results from headless solver runs.

LSPP is the canonical Ansys/LSTC tool for d3plot visualization. For Ansys
Student users, it's also the only reliable post-processor (Mechanical's
result-evaluator wipes the WorkingDir on saved-project mode — see
mech/README.md). This module wraps the launch with a clean Python API.
"""
from .visualize import open_in_lspp, render_png_headless, find_d3plot

__all__ = ["open_in_lspp", "render_png_headless", "find_d3plot"]
