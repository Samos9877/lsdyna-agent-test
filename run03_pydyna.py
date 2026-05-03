"""Drive an LS-DYNA run via PyDYNA's run_dyna() rather than the raw CLI.

Reuses the MAT_075 EPS deck from run02. PyDYNA should locate the Ansys
LS-DYNA Student R16.1 install (v261) automatically from the registry.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from ansys.dyna.core.run import run_dyna, MemoryUnit, MpiOption, Precision

ROOT = Path(r"C:\Users\samos\OneDrive\Documents\projects\lsdyna-agent-test")
SRC_DECK = ROOT / "run02" / "eps_mat075_unit_cube.k"
RUN_DIR = ROOT / "run03"

RUN_DIR.mkdir(exist_ok=True)
deck = RUN_DIR / SRC_DECK.name
shutil.copy2(SRC_DECK, deck)

print(f"Working dir: {RUN_DIR}")
print(f"Input: {deck.name}")
print()

# PyDYNA's auto-detect looks inside Ansys Unified for an embedded LS-DYNA exe;
# the standalone Suite R16.1 Student lives elsewhere. Pass the executable explicitly.
SOLVER_EXE = (
    r"C:\Program Files\LS-DYNA Suite R16.1 Student\lsdyna"
    r"\ls-dyna_smp_d_R16.1_180-gd50332dbe5_winx64_ifort190_sse2_studentversion.exe"
)

result = run_dyna(
    str(deck),
    executable=SOLVER_EXE,
    ncpu=1,
    memory=20,
    memory_unit=MemoryUnit.MB,
    mpi_option=MpiOption.SMP,
    precision=Precision.DOUBLE,
    working_directory=str(RUN_DIR),
)
print(f"\nrun_dyna returned: {result!r}")
print(f"\nFiles in {RUN_DIR}:")
for f in sorted(RUN_DIR.iterdir()):
    print(f"  {f.name:35s} {f.stat().st_size:>10d} bytes")
