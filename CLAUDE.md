# CLAUDE.md — lsdyna-agent-test

Sam's working repo for **driving LS-DYNA from Claude end-to-end**: build/edit `.k` decks, invoke the solver, parse results, swap materials in a verification loop, and (where licensing permits) drive Ansys Mechanical visually.

The project sits between three sibling LS-DYNA-related directories in the workspace:

| | role |
|---|---|
| `../lsdyna/` | Reference library — keyword manual PDFs, no code, no git |
| `../lsdyna-jsx-guide/` | Skill — interactive material-model JSX guides |
| `../lsdyna-data-flow-diagram/` | Skill — value lineage diagrams for LS-DYNA decks |
| **`./` (this project)** | **Tooling — hands-on solver automation, headless and Mechanical-bridged** |
| `../eps-geofoam/` | Downstream consumer — uses this stack for MAT_075 calibration |

## Environment requirements

- **Windows 11**, Git Bash, Anaconda Python at `/c/ProgramData/anaconda3/python.exe` (not on PATH — invoke by full path)
- **LS-DYNA Suite R16.1 Student** at `C:\Program Files\LS-DYNA Suite R16.1 Student\` — provides the standalone solver, LS-PrePost, LS-Run
- **Ansys 2026 R1 Student** at `C:\Program Files\ANSYS Inc\ANSYS Student\v261\` — provides Workbench + Mechanical
- **The two installs are deliberately wired together** via these env vars (set by the LSTC Student installer):
  ```
  ANSYS_LSW_DOC      = ...\LS-DYNA Suite R16.1 Student\documentation
  ANSYS_LSW_LSDYNA   = ...\LS-DYNA Suite R16.1 Student\lsdyna\ls-dyna_smp_d_R16.1_180-...exe
  ANSYS_LSW_LSPP     = ...\LS-DYNA Suite R16.1 Student\lspp\lsprepost4.12.exe
  LSTC_LICENSE       = Ansys
  ```
  These make the LS-DYNA Analysis System show up in Workbench's Toolbox and tell the LSTC license daemon to defer to the Ansys license. **Do NOT delete either install** — they are a system, not redundant.

## Python dependencies

Installed in the user's Anaconda env (already present):
- `ansys-dyna-core` 0.11 — PyDYNA (mostly unused — see License-path findings below)
- `ansys-dpf-core` 0.16 — Ansys Data Processing Framework
- `lasso-python` 2.0.4 — d3plot/binout binary reader
- `ansys-mechanical-core` 0.12.7 — PyMechanical
- `ansys-workbench-core` 0.13 — PyWorkbench
- `ansys-tools-path` 0.8 — installation discovery
- `numpy`, `scipy`, `matplotlib`, `pandas`, `h5py` — standard scientific stack

## Architecture

Two operational stacks, both proven working as of 2026-05-03:

### Stack A — Headless solver loop (workhorse)

```
.k deck (hand-authored or Mechanical-exported)
   │
   ▼
lsdyna_runner.py  ──►  ls-dyna_smp_d_R16.1_...exe  ──►  d3plot, elout, glstat, ...
                                                            │
                                                            ▼
                                                   parse_results.py
                                                   (lasso-python + custom regex)
                                                            │
                                                            ▼
                                                   stress-strain history,
                                                   verification metrics
```

`lsdyna_runner.run_dyna(deck, working_directory=run_dir, ncpu=1, memory_mb=20)` is a thin subprocess shim. **It exists because PyDYNA's `WindowsRunner` is hard-wired for Ansys-Unified install layouts** (looks for `lsprepost*/LS-Run/lsdynamsvar.bat` next to the solver), which the LSTC standalone Student install does not provide. Working around that took ~50 lines.

### Stack B — Mechanical-via-Workbench bridge (visual model construction)

```
Sam: open Workbench, build LS-DYNA system in Toolbox,
     create geometry, open scripting console, type StartServer()
        │
        ▼
   wb_port (e.g. 56112)
        │
        ▼
PyWorkbench: connect_workbench(port=wb_port, security='insecure')
        │
        ▼
wb.start_mechanical_server(system_name='SYS')   ──►   mech_port (e.g. 56386)
        │
        ▼
PyMechanical: connect_to_mechanical(ip='localhost', port=mech_port)
        │
        ▼
mech.run_python_script("Model.AddNamedSelection() ...")
        │  every command updates the GUI live; Sam watches
        ▼
Solution.WriteInputFile()  ──►  .k deck  ──►  fed back into Stack A
```

**Critical license-path finding**: PyMechanical's `pymech.launch_mechanical(batch=False)` triggers a Mechanical-internal license check that **blocks `Model.AddLSDynaAnalysis()` on Ansys Student**. Workbench-launched Mechanical does NOT have this restriction — it inherits the LS-DYNA license through the env-var bridge above, which Workbench owns. The bridge is therefore the only way to drive a Mechanical-with-LS-DYNA session from Python on Student licensing.

See `mech/README.md` for the exact bootstrap recipe.

## Layout

```
lsdyna-agent-test/
├── CLAUDE.md, README.md
├── lsdyna_runner.py        Stack A — subprocess shim around the standalone solver
├── parse_results.py        ASCII (elout) + binary (d3plot via lasso) parsers
├── plot_foam_curve.py      Demo: stress-strain plot from a run
├── mat075_compression.png  Proof artifact (run02 result)
├── run03_pydyna.py         Failed PyDYNA attempt — kept as evidence of the runner gap
├── mech/                   Stack B — Workbench-bridge + Mechanical client
│   ├── README.md           Bootstrap recipe (StartServer → connect_workbench → ...)
│   ├── session.py          Persistent Mechanical session helpers
│   └── client.py           run() with tidy gRPC error stripping
├── rigs/                   Reusable test rigs (geometry + BCs + outputs, NO material)
│   └── uniaxial_unconfined/
│       ├── rig_template.k  Single hex, *INCLUDE material.k
│       └── README.md       What this rig exercises and what it doesn't
├── materials/              Material cards as swappable .k files (MID=99 convention)
│   ├── mat_001_steel.k     ✅ Ready
│   ├── mat_075_eps22.k     ✅ Ready (EPS22-like crushable foam)
│   ├── mat_063_crushable.k 🟡 Skeleton
│   └── mat_077_ogden_foam.k 🟡 Skeleton
├── verify/                 Verification-loop runner (planned)
├── lspp/                   LS-PrePost helpers (planned)
├── run01/, run02/, run03/  Past run outputs (gitignored — regenerate by running the rig)
└── docs/                   Findings, recipes, decision log
```

## Conventions

- **Units in `.k` files**: mm, ms, tonne, N, MPa (consistent SI subset). All decks header-comment this.
- **MID=99** in material files — the rig template references MID=99 in its `*PART` card. Material files MUST define their `*MAT_xxx` with MID=99 so they slot in.
- **LCID 90+** for material-internal `*DEFINE_CURVE` — keeps the rig's LCID 1 (loading curve) clear.
- **Run dirs** (`run01/`, `runNN/`) are throwaway — gitignored, regenerate by running the rig with a chosen material.
- **Workbench unit system on this machine is U.S. Customary** — `Volume.Value` etc. report in `ft³`, not `m³`. Watch for unit confusion when reading Mechanical state via Python.

## Quick recipes

```bash
# Run a deck via Stack A (headless)
PY=/c/ProgramData/anaconda3/python.exe
$PY -c "from lsdyna_runner import run_dyna; run_dyna('rigs/uniaxial_unconfined/rig_template.k', working_directory='runNN/')"

# Parse results
$PY parse_results.py runNN/

# Connect to a running Mechanical session (Stack B)
# 1. In Workbench: File → Scripting → Open Command Window, then type:  StartServer()
# 2. Note the port it returns
# 3. From Python:
$PY -c "
from ansys.workbench.core import connect_workbench
import ansys.mechanical.core as pymech
wb = connect_workbench(port=<wb_port>, security='insecure')
mech_port = wb.start_mechanical_server(system_name='SYS')
mech = pymech.connect_to_mechanical(ip='localhost', port=mech_port, cleanup_on_exit=False)
mech.run_python_script('Model.AddNamedSelection()')   # visible in Sam's tree immediately
"
```

## Open threads

- `verify/verify_materials.py` — the loop runner not yet built
- `lspp/visualize.py` — LS-PrePost launcher for a chosen run
- `materials/mat_079_hysteretic.k`, `mat_145_schwer.k` — not yet authored
- Real EPS001-014 digitized curves not yet plumbed into `mat_075_eps22.k` (still placeholder)
- LS-DYNA MCP server (would wrap `lsdyna_runner` + `parse_results` + rig templates) — see workspace `tracking_curiosity.md`

## Status

**Proven working (2026-05-02 evening + 2026-05-03):**
- Stack A: MAT_001 elastic + MAT_075 EPS22-like, both normal termination, results parsed
- Stack B: live Mechanical-via-Workbench session, Named Selection added remotely, body/material state queried

**Not yet attempted:**
- `Solution.WriteInputFile()` to export Mechanical-built model as `.k`
- Solving from Mechanical (vs. headless)
- Material verification loop end-to-end
