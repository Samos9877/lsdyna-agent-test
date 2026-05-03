$ ============================================================
$ MAT_075 — *MAT_BILKHU/DUBOIS_FOAM
$ EPS22 (22 kg/m^3 EPS geofoam) — placeholder calibration
$ Real LCPY/LCUYS curves should come from eps001-014 digitized data
$ Units: mm, ms, tonne, N, MPa
$ ============================================================
*MAT_BILKHU/DUBOIS_FOAM
$#     mid        ro         e      lcpy     lcuys        vc        pc       vpc
        99 2.200E-11       6.0        91        92      0.05       0.0       0.0
$#     tsc      vtsc    lcrate        pr      kcon     isflg    ncycle
      0.05       0.0         0      0.05       0.0         0         0
$
$ Pressure-yield curve: pressure yield vs logarithmic volumetric strain
*DEFINE_CURVE
$#    lcid      sidr       sfa       sfo
        91         0       1.0       1.0
$#               a1                  o1
                0.0                0.06
                0.02               0.08
                0.10               0.09
                0.30               0.10
                0.50               0.13
                0.70               0.30
                0.85               1.50
                1.20               5.00
$
$ Uniaxial yield curve: uniaxial yield stress vs vol strain
*DEFINE_CURVE
$#    lcid      sidr       sfa       sfo
        92         0       1.0       1.0
$#               a1                  o1
                0.0                0.10
                0.02               0.12
                0.10               0.13
                0.30               0.15
                0.50               0.20
                0.70               0.50
                0.85               2.00
                1.20               6.00
