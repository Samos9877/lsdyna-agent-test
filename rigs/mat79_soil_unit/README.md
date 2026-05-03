# mat79_soil_unit/

Single-element rig **for material verification of `*MAT_HYSTERETIC_SOIL` (MAT_079)** and other soil/foam constitutive models. Authored visually in Ansys Mechanical (LS-DYNA Analysis System) on 2026-05-03 then refactored for `*INCLUDE`-based material swapping.

The actual MAT_079 unit-test specification is awaiting Sam's spec — this rig is the shared infrastructure that all material verification runs will use. The first runs use MAT_001 elastic as a pressure-test of the pipeline.

## Files

| File | What |
|---|---|
| `raw_mechanical_export.k` | Untouched output from `analysis.WriteInputFile()`. Reference for what Mechanical generated. Don't run this — it embeds `*MAT_ELASTIC` (Structural Steel) directly. |
| `rig_template.k` | The same deck with the `*MAT_*` block replaced by `*INCLUDE material.k`. This is what the verify runner actually feeds to the solver. |

## How the pieces fit

```
rig_template.k  +  materials/mat_NNN_*.k  →  copied into <run>/
                                              ├── rig.k  (renamed copy)
                                              ├── material.k  (copy of selected material)
                                              └── (run lsdyna_runner here)
```

The `*INCLUDE material.k` directive in `rig_template.k` is resolved by the LS-DYNA solver at parse time, so the per-run dir just needs `rig.k` + `material.k` next to each other.

## Geometry & loading

- **Geometry**: 1-inch hex (single linear hex8 element), centered at (0,0,12.7) mm. Nodes at ±12.7 mm in x/y, 0 to 25.4 mm in z.
- **BC**: bottom face (z=0) fully fixed (`*BOUNDARY_SPC_SET`, all 6 DOF on the 4 nodes).
- **Loading**: top face (z=25.4 mm) prescribed displacement, x=0, y=0, z ramps linearly from 0 to -0.254 mm over t=0 → t=1.0 s (= 1% engineering strain at endtime).
- **Endtime**: 1.0 s.

This is uniaxial unconfined compression — fine for elastic / yield smoke tests but **not sufficient to fully exercise MAT_079** (a hysteretic model needs cyclic loading + confining pressure). Once Sam specs the MAT_079 unit-test requirements, we'll either:
- Rewrite the loading curve (cyclic) and re-export, OR
- Add a confining-pressure variant rig in a sibling subdirectory

## Units

**N · mm · tonne · s · MPa** ("consistent NMM" per Mechanical's header).

⚠️ **Time is SECONDS here**, not milliseconds. The hand-authored rig in `rigs/uniaxial_unconfined/` uses N-mm-tonne-**ms**-MPa. The two rigs are otherwise unit-compatible (length, mass, stress identical). For materials with no time-rate parameters (MAT_001, MAT_063, MAT_075 with LCRATE=0), the same material file works in both rigs. For rate-dependent materials, time-curve abscissae must be authored to match the rig's time unit.

## Material slot

The `*PART` card references **MID=99**. Material files must define `*MAT_*` with MID=99 to slot in. Same convention as `rigs/uniaxial_unconfined/`.

## Output requests (from Mechanical defaults)

`*DATABASE_*` cards at dt=0.001 s (1000 frames over 1s):
- `GLSTAT` — global energy/timestep history
- `SPCFORC` — reaction forces at SPC nodes (bottom face → axial reaction)
- `RCFORC` — contact forces (none in this rig but card present)
- `BNDOUT` — boundary force history
- `NODOUT` — nodal displacement/velocity/acceleration
- `MATSUM` — per-material energy
- `ELOUT` — element stress/strain history
- `JNTFORC`, `DEFORC`, `TPRINT` — joint/discrete/thermal (unused here)
- `D3PLOT` binary @ dt=0.05 s (20 frames)
- `D3PROP` for material/section property echo

For soil verification specifically, the most useful are: `ELOUT` (full stress tensor → invariants p, q), `NODOUT` (displacement → strains), `SPCFORC` (axial reaction force), `GLSTAT` (energy balance check).

## Provenance

Built by Claude driving Sam's open Workbench session via:
- PyWorkbench `connect_workbench(port=56112, security='insecure')`
- `wb.start_mechanical_server(system_name='SYS')` → Mechanical port
- PyMechanical `mech.run_python_script(...)` for: face Named Selections, mesh cleanup (deleted orphan controls, MultiZone single hex), Fixed Support, Displacement, Endtime via property-bag, `analysis.WriteInputFile(...)`.

Full bootstrap recipe: `../../mech/README.md`.
