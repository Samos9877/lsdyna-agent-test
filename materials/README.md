# materials/

Each file is a self-contained `*MAT_xxx` definition + any supporting `*DEFINE_CURVE` / `*EOS_*` / `*HOURGLASS` cards. Files are designed to be `*INCLUDE`-d by a rig template (see `../rigs/`).

## Conventions

- **MID = 99**: the rig template's `*PART` card references material ID 99. Every material file MUST define its `*MAT_xxx` with MID=99 so it slots in.
- **LCID 90+**: any `*DEFINE_CURVE` inside a material file should use load-curve IDs ≥ 90 to avoid colliding with the rig's LCID 1 (loading curve).
- **Units**: mm, ms, tonne, N, MPa (must match the rig's units). Document at the top of every file.
- **Status header**: each file marks itself ✅ Ready, 🟡 Skeleton, or ⚪ Stub. CI/runner should refuse to queue a non-ready material.

## Queue (target verification set per Sam, 2026-05-03)

| File | Material | LSTC type | Status | Notes |
|---|---|---|---|---|
| `mat_001_steel.k` | MAT_001 | `*MAT_ELASTIC` | ✅ Ready | Reference baseline (linear elastic, steel-like) |
| `mat_063_crushable.k` | MAT_063 | `*MAT_CRUSHABLE_FOAM` | 🟡 Skeleton | Simpler foam baseline (no pressure-yield surface) |
| `mat_075_eps22.k` | MAT_075 | `*MAT_BILKHU/DUBOIS_FOAM` | ✅ Ready (placeholder curves) | EPS22 geofoam — real LCPY/LCUYS from eps001-014 still TODO |
| `mat_077_ogden_foam.k` | MAT_077 | `*MAT_OGDEN_RUBBER` (or _H/_M variants) | 🟡 Skeleton | Pick variant before authoring |
| `mat_079_hysteretic.k` | MAT_079 | `*MAT_HYSTERETIC_SOIL` | ⚪ Not yet stubbed | |
| `mat_145_schwer.k` | MAT_145 | `*MAT_SCHWER_MURRAY_CAP_MODEL` | ⚪ Not yet stubbed | |

## Authoring a new material card

1. Look up the card layout in `../../lsdyna/mat_NNN.pdf`
2. Create `materials/mat_NNN_<descriptor>.k`
3. Header comment block (purpose, units, source paper if any)
4. `*MAT_<name>` card with **MID=99**
5. Any required `*DEFINE_CURVE` with LCID ≥ 90, referenced by the MAT card
6. Status mark in the file header
7. Add row to the queue table above
8. Smoke-test against `rigs/uniaxial_unconfined/rig_template.k` via the verify runner (or `lsdyna_runner.run_dyna()` directly)

## Why one-file-per-material

- **Diffs are small**: changing one parameter touches one file
- **Swappable**: the verify loop just `cp materials/mat_NNN_*.k <run>/material.k` and runs
- **Comparable**: the same rig drives every material → comparison plots align by construction
- **Versionable**: when a calibration shifts (e.g. a new EPS22 paper revises plateau stress), git history shows what changed when
