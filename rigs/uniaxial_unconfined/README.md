# Uniaxial unconfined compression rig

**Geometry:** 1 mm × 1 mm × 1 mm hex element (single solid)
**Loading:** prescribed compressive z-displacement on top face, ramped 0 → -0.7 mm linearly over 10 ms (70% engineering strain at end of run)
**BCs:** bottom face z-fixed; corner nodes constrained in x/y to remove rigid-body modes; lateral expansion otherwise free (unconfined)
**Output:** d3plot @ 0.25 ms, glstat/elout/nodout @ 0.10 ms
**Element formulation:** ELFORM=1 (constant stress one-point quadrature)

## Material slot
The rig references **MID=99**, which must be defined in the included `material.k`.
The included file may also contain `*DEFINE_CURVE`, `*EOS_*`, `*HOURGLASS` and any
other supporting cards the material needs. The rig itself contains no material data.

## What this rig exercises
- Yield onset (uniaxial)
- Plateau / strain-hardening behaviour
- Densification (for foams)
- Unloading/reloading is NOT exercised — for that, use a different rig with a
  triangular load curve.

## What this rig does NOT exercise
- Pressure-yield surface (no hydrostatic loading)
- Rate dependence (single strain rate ~7%/ms = 70 1/s)
- Tensile behaviour
- Deviatoric vs hydrostatic interaction

For those, additional rigs in `rigs/` are needed. This is the simplest possible
material check — does the material respond plausibly under a single straightforward
compression history.

## Conventions for material files
A material file targeted at this rig should look like:

```
*KEYWORD
*MAT_<name>
$#     mid        ro        ...
        99 ...

*DEFINE_CURVE
$    lcid       ...
       <local>  ...
$#       a1                  o1
         ...

*END
```

The `*KEYWORD` and `*END` are optional inside an `*INCLUDE`d file — LS-DYNA tolerates
either. Local LCIDs in the material file should be in the 90+ range to avoid
clashing with the rig's LCID 1 (loading curve).
