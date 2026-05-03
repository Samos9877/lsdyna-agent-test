*KEYWORD
*TITLE
Uniaxial unconfined compression rig (single hex) - material verification template
$ Units: mm, ms, tonne, N, MPa
$
$ This file defines geometry, loading, BCs, and output requests.
$ The material card is supplied via *INCLUDE — drop in any compatible
$ MAT card file as `material.k` in the run directory.
$
$ The included material file MUST define a *MAT_xxx with MID=99 and any
$ supporting *DEFINE_CURVE / *EOS cards it needs. If the material is
$ rate-sensitive (e.g. MAT_075/LCRATE, MAT_083, MAT_077) include the rate
$ curves there too.
$
*INCLUDE
material.k
$
$ ============================================================
$ Solution control
$ ============================================================
*CONTROL_TERMINATION
$#  endtim    endcyc     dtmin    endeng    endmas
      10.0         0       0.0       0.0       0.0
*CONTROL_TIMESTEP
$#  dtinit    tssfac
       0.0       0.9
$
$ Output requests — all on a 0.1 ms cadence
*DATABASE_BINARY_D3PLOT
$#      dt
      0.25
*DATABASE_GLSTAT
$#      dt    binary      lcur     ioopt
      0.10         0         0         1
*DATABASE_ELOUT
$#      dt    binary      lcur     ioopt
      0.10         0         0         1
*DATABASE_NODOUT
$#      dt    binary      lcur     ioopt
      0.10         0         0         1
*DATABASE_HISTORY_NODE
$#     id1       id2       id3       id4
         5         6         7         8
*DATABASE_HISTORY_SOLID
$#     id1
         1
$
$ ============================================================
$ Part / section — material is supplied via the included file with MID=99
$ ============================================================
*PART
unit_cube
$#     pid     secid       mid     eosid      hgid      grav    adpopt      tmid
         1         1        99         0         0         0         0         0
*SECTION_SOLID
$#   secid    elform       aet
         1         1         0
$
$ ============================================================
$ Geometry: 1 mm unit cube, 8 nodes, 1 hex
$ ============================================================
*NODE
$#   nid               x               y               z      tc      rc
       1             0.0             0.0             0.0       0       0
       2             1.0             0.0             0.0       0       0
       3             1.0             1.0             0.0       0       0
       4             0.0             1.0             0.0       0       0
       5             0.0             0.0             1.0       0       0
       6             1.0             0.0             1.0       0       0
       7             1.0             1.0             1.0       0       0
       8             0.0             1.0             1.0       0       0
*ELEMENT_SOLID
$#   eid     pid      n1      n2      n3      n4      n5      n6      n7      n8
       1       1       1       2       3       4       5       6       7       8
$
$ ============================================================
$ Boundary conditions
$ Bottom face fixed in z; corners constrained to remove rigid-body modes
$ Top face: prescribed compressive displacement
$ ============================================================
*BOUNDARY_SPC_NODE
$#     nid       cid      dofx      dofy      dofz     dofrx     dofry     dofrz
         1         0         1         1         1         0         0         0
         2         0         0         1         1         0         0         0
         3         0         0         0         1         0         0         0
         4         0         1         0         1         0         0         0
*BOUNDARY_PRESCRIBED_MOTION_SET
$#    nsid       dof       vad      lcid        sf       vid     death     birth
         1         3         2         1       1.0         0  1.000E20       0.0
*SET_NODE_LIST
$#     sid
         1
         5         6         7         8         0         0         0         0
$
$ Loading curve — compress 70% of cube height linearly over 10 ms
$ Per-material runs may want to override SF on the BPM card for shorter strokes
*DEFINE_CURVE
$#    lcid      sidr       sfa       sfo
         1         0       1.0       1.0
$#               a1                  o1
                0.0                 0.0
               10.0                -0.7
*END
