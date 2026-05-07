"""Generate a geofoam ball-indent test deck.

Test rig per Sam (2026-05-06):
  - Foam block: 3 x 3 x 2 inch, hex mesh at 1/4 inch
  - Indenter: golf-ball-sized rigid sphere (1.68 inch diameter), modeled as a
    coarse cubed-sphere shell mesh (rigid material)
  - Loading: ball pushed down INDENT_DEPTH inches into the foam over PUSH_TIME,
    then lifted back to start over LIFT_TIME. Total runtime = PUSH + LIFT seconds.
  - Foam material: *MAT_BILKHU/DUBOIS_FOAM (MAT_075) supplied via *INCLUDE
    of Sam's mat_075_eps_12.k card (MID=4)
  - Steel: *MAT_RIGID with steel-like elastic constants

Units (consistent in-lbf-s — matches Sam's MAT_075 card):
  length  = inches
  time    = seconds
  mass    = lbf·s^2/in (a.k.a. "slinch" or "blob")
  force   = lbf
  stress  = psi
  density = lbf·s^2/in^4

Output:
  rig.k  — the assembled deck. material.k must be present alongside (we
           copy the included *MAT_075 card into the run dir as material.k).
"""
from __future__ import annotations

import math
from pathlib import Path

# ─── Geometry parameters ────────────────────────────────────────────────────────
BLOCK_X = 3.0
BLOCK_Y = 3.0
BLOCK_Z = 2.0
ELEM_SIZE = 0.25

BALL_DIAMETER = 1.68
BALL_INITIAL_GAP = 0.05     # space between ball bottom & foam top at t=0
                            #  (must exceed half the shell thickness to avoid initial penetration)
INDENT_DEPTH = 0.3          # how far the ball's bottom plunges below foam top
SPHERE_FACE_DIVISIONS = 4   # cubed-sphere subdivision (4 -> 6×16 = 96 quads)

# ─── Material parameters ────────────────────────────────────────────────────────
# Foam: comes from *INCLUDE of Sam's mat_075_eps_12.k (MID=4)
# Steel ball (rigid):
STEEL_RHO = 7.33e-4         # lbf·s²/in⁴
STEEL_E   = 30e6            # psi
STEEL_NU  = 0.30
RIGID_MID = 100             # steer clear of MAT_075's MID=4

# ─── Loading parameters (time in seconds) ───────────────────────────────────────
PUSH_TIME = 1.0
LIFT_TIME = 1.0
ENDTIME   = PUSH_TIME + LIFT_TIME

# ─── Output cadence ─────────────────────────────────────────────────────────────
D3PLOT_DT  = 0.02       # 50 frames over 1 s
ASCII_DT   = 0.005      # finer resolution for force-disp curve

# ─── IDs ────────────────────────────────────────────────────────────────────────
PART_FOAM   = 1
PART_BALL   = 2
SECT_FOAM   = 1
SECT_BALL   = 2
LCID_PUSH   = 1


# ════════════════════════════════════════════════════════════════════════════════
# Geometry generators
# ════════════════════════════════════════════════════════════════════════════════

def gen_block_nodes_elements(nx, ny, nz, dx, dy, dz, x0=0.0, y0=0.0, z0=0.0,
                              start_nid=1, start_eid=1, pid=PART_FOAM):
    """Hex8 brick mesh, returning ([nid, x, y, z], [eid, pid, n1..n8])."""
    nodes = []
    nid = start_nid
    # node[i,j,k] = nid_grid[i,j,k]
    nid_grid = {}
    for k in range(nz + 1):
        for j in range(ny + 1):
            for i in range(nx + 1):
                nodes.append((nid, x0 + i*dx, y0 + j*dy, z0 + k*dz))
                nid_grid[(i, j, k)] = nid
                nid += 1
    elements = []
    eid = start_eid
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                # 8 nodes of a hex (LS-DYNA convention: bottom face CCW, then top)
                n1 = nid_grid[(i,   j,   k)]
                n2 = nid_grid[(i+1, j,   k)]
                n3 = nid_grid[(i+1, j+1, k)]
                n4 = nid_grid[(i,   j+1, k)]
                n5 = nid_grid[(i,   j,   k+1)]
                n6 = nid_grid[(i+1, j,   k+1)]
                n7 = nid_grid[(i+1, j+1, k+1)]
                n8 = nid_grid[(i,   j+1, k+1)]
                elements.append((eid, pid, n1, n2, n3, n4, n5, n6, n7, n8))
                eid += 1
    return nodes, elements, nid_grid


def gen_cubed_sphere_shell(radius, center, n, start_nid=1, start_eid=1, pid=PART_BALL):
    """Cubed-sphere quad-shell mesh.

    n = number of subdivisions per cube face edge -> 6*n*n quads total.
    Returns ([nid, x, y, z], [eid, pid, n1, n2, n3, n4]).
    """
    cx, cy, cz = center
    # Build the 6 cube faces, parameterized in (u, v) ∈ [-1, +1]².
    # Each face has its own (u, v) -> cube_xyz mapping. Then we project onto sphere.
    faces = [
        # name,  fn(u,v) -> (x, y, z) on the unit cube
        ("+x", lambda u, v: ( 1.0,  u,    v   )),
        ("-x", lambda u, v: (-1.0,  v,    u   )),
        ("+y", lambda u, v: ( v,    1.0,  u   )),
        ("-y", lambda u, v: ( u,   -1.0,  v   )),
        ("+z", lambda u, v: ( u,    v,    1.0 )),
        ("-z", lambda u, v: ( v,    u,   -1.0 )),
    ]

    # Dedup nodes that fall on shared cube edges/corners by hashing (rounded) xyz
    nodes_by_key = {}   # (rx, ry, rz) -> nid
    nodes = []
    nid = start_nid

    def get_or_add(x, y, z):
        nonlocal nid
        # Project to sphere, then translate to center
        norm = math.sqrt(x*x + y*y + z*z)
        sx = cx + x / norm * radius
        sy = cy + y / norm * radius
        sz = cz + z / norm * radius
        key = (round(sx, 6), round(sy, 6), round(sz, 6))
        if key not in nodes_by_key:
            nodes_by_key[key] = nid
            nodes.append((nid, sx, sy, sz))
            nid += 1
        return nodes_by_key[key]

    # Build per-face grid of nodes + quads
    elements = []
    eid = start_eid
    for face_name, fn in faces:
        # node grid (n+1) × (n+1) over u,v ∈ [-1, +1]
        grid = {}
        for j in range(n + 1):
            for i in range(n + 1):
                u = -1.0 + 2.0 * i / n
                v = -1.0 + 2.0 * j / n
                cx_u, cy_u, cz_u = fn(u, v)
                grid[(i, j)] = get_or_add(cx_u, cy_u, cz_u)
        # Quads on this face
        for j in range(n):
            for i in range(n):
                n1 = grid[(i,   j)]
                n2 = grid[(i+1, j)]
                n3 = grid[(i+1, j+1)]
                n4 = grid[(i,   j+1)]
                elements.append((eid, pid, n1, n2, n3, n4))
                eid += 1
    return nodes, elements


# ════════════════════════════════════════════════════════════════════════════════
# Deck assembly (writes rig.k)
# ════════════════════════════════════════════════════════════════════════════════

def fmt_node(nid, x, y, z):
    return f"{nid:8d}{x:16.6f}{y:16.6f}{z:16.6f}\n"


def fmt_solid(eid, pid, n1, n2, n3, n4, n5, n6, n7, n8):
    return f"{eid:8d}{pid:8d}{n1:8d}{n2:8d}{n3:8d}{n4:8d}{n5:8d}{n6:8d}{n7:8d}{n8:8d}\n"


def fmt_shell(eid, pid, n1, n2, n3, n4):
    return f"{eid:8d}{pid:8d}{n1:8d}{n2:8d}{n3:8d}{n4:8d}\n"


def main():
    here = Path(__file__).resolve().parent
    out_path = here / "rig.k"

    # ── Foam block (3 × 3 × 2 inches) ───────────────────────────────────────────
    nx = round(BLOCK_X / ELEM_SIZE)   # 12
    ny = round(BLOCK_Y / ELEM_SIZE)   # 12
    nz = round(BLOCK_Z / ELEM_SIZE)   #  8
    block_nodes, block_elems, block_grid = gen_block_nodes_elements(
        nx, ny, nz, ELEM_SIZE, ELEM_SIZE, ELEM_SIZE,
        x0=-BLOCK_X/2, y0=-BLOCK_Y/2, z0=0.0,
        start_nid=1, start_eid=1, pid=PART_FOAM
    )

    # ── Ball (cubed-sphere shell) ───────────────────────────────────────────────
    ball_radius = BALL_DIAMETER / 2.0
    ball_center_z_initial = BLOCK_Z + ball_radius + BALL_INITIAL_GAP   # bottom of ball at z = BLOCK_Z + gap
    ball_center = (0.0, 0.0, ball_center_z_initial)
    ball_nodes, ball_elems = gen_cubed_sphere_shell(
        radius=ball_radius, center=ball_center, n=SPHERE_FACE_DIVISIONS,
        start_nid=len(block_nodes) + 1,
        start_eid=len(block_elems) + 1,
        pid=PART_BALL,
    )

    # ── Sets: foam bottom face (z = 0), foam top face (z = BLOCK_Z) ───────────────
    foam_bottom_nodes = [block_grid[(i, j, 0)]  for i in range(nx+1) for j in range(ny+1)]
    foam_top_nodes    = [block_grid[(i, j, nz)] for i in range(nx+1) for j in range(ny+1)]

    # foam top elements (segment set for contact slave) — top z-face of top-row elements
    # In gen_block_nodes_elements, the element's top face is nodes 5..8 (n5,n6,n7,n8).
    foam_top_seg = []   # list of (n5,n6,n7,n8)
    eid = 1
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                if k == nz - 1:
                    n5 = block_grid[(i,   j,   nz)]
                    n6 = block_grid[(i+1, j,   nz)]
                    n7 = block_grid[(i+1, j+1, nz)]
                    n8 = block_grid[(i,   j+1, nz)]
                    foam_top_seg.append((n5, n6, n7, n8))
                eid += 1

    # ── Compose the deck ────────────────────────────────────────────────────────
    L = []
    L.append("*KEYWORD\n")
    L.append("*TITLE\n")
    L.append("Geofoam ball-indent test (3x3x2 in block, 1.68 in ball, MAT_075 EPS-12)\n")

    # Solver controls
    L.append("$ Units: in - lbf - s consistent (psi, lbf*s^2/in^4)\n")
    L.append("*CONTROL_TERMINATION\n")
    L.append(f"$#  endtim    endcyc     dtmin    endeng    endmas\n")
    L.append(f"  {ENDTIME:8.4f}         0       0.0       0.0       0.0\n")
    L.append("*CONTROL_TIMESTEP\n")
    L.append(f"$#  dtinit    tssfac      isdo    tslimt     dt2ms      lctm     erode     ms1st\n")
    L.append(f"       0.0       0.9         0       0.0  -1.0E-05         0         0         0\n")
    # *CONTROL_CONTACT omitted — defaults are fine for our simple 1-pair contact
    L.append("*CONTROL_OUTPUT\n")
    L.append("$#   npopt    neecho    nrefup    iaccop     opifs    ipnint    ikedit    iflush\n")
    L.append("         1         3         0         1         0         0       100         0\n")

    # Output requests
    L.append("*DATABASE_BINARY_D3PLOT\n")
    L.append(f"$#      dt\n")
    L.append(f"  {D3PLOT_DT:8.4f}\n")
    L.append("*DATABASE_GLSTAT\n")
    L.append(f"  {ASCII_DT:8.4f}\n")
    L.append("*DATABASE_RCFORC\n")
    L.append(f"  {ASCII_DT:8.4f}\n")
    L.append("*DATABASE_NODOUT\n")
    L.append(f"  {ASCII_DT:8.4f}\n")
    L.append("*DATABASE_MATSUM\n")
    L.append(f"  {ASCII_DT:8.4f}\n")

    # Material — INCLUDE Sam's MAT_075 EPS-12 card
    L.append("$ Foam material from Sam's mat_075_eps_12.k (MID=4)\n")
    L.append("*INCLUDE\n")
    L.append("material.k\n")

    # Rigid steel ball material — 3 cards per *MAT_RIGID format
    L.append("$ Steel ball: MAT_RIGID, free in z only (rotations + x,y translations locked)\n")
    L.append("*MAT_RIGID\n")
    L.append("$#     mid        ro         e        pr         n    couple         m     alias\n")
    L.append(f"  {RIGID_MID:8d}{STEEL_RHO:10.4E}{STEEL_E:10.4E}{STEEL_NU:10.4f}       0.0       0.0       0.0\n")
    L.append("$#     cmo      con1      con2\n")
    L.append("       0.0       0.0       0.0\n")
    L.append("$ CMO=0 -> NO constraints from MAT_RIGID. CON1, CON2 ignored.\n")
    L.append("$ The rigid body is fully free; prescribed motion (below) controls z. x,y stay 0 by symmetry of contact.\n")
    L.append("$#  lco_a1        a2        a3        v1        v2        v3\n")
    L.append("       0.0       0.0       0.0       0.0       0.0       0.0\n")

    # Sections
    L.append("*SECTION_SOLID\n")
    L.append(f"$#   secid    elform       aet\n")
    L.append(f"  {SECT_FOAM:8d}         1         0\n")
    L.append("$ ELFORM=1 (constant-stress hex) — fastest; SOFT=2 contact handles the large-strain stability\n")
    L.append("*SECTION_SHELL\n")
    L.append("$#   secid    elform      shrf       nip     propt    qr/irid     icomp     setyp\n")
    L.append(f"  {SECT_BALL:8d}        16       0.0       2.0       1.0       0.0         0         1\n")
    L.append("$#      t1        t2        t3        t4      nloc     marea      idof    edgset\n")
    L.append("      0.05      0.05      0.05      0.05       0.0       0.0       0.0         0\n")

    # Parts
    L.append("*PART\n")
    L.append("foam_block\n")
    L.append(f"$#     pid     secid       mid     eosid      hgid      grav    adpopt      tmid\n")
    L.append(f"  {PART_FOAM:8d}  {SECT_FOAM:8d}         4         0         0         0         0         0\n")
    L.append("*PART\n")
    L.append("steel_ball\n")
    L.append(f"  {PART_BALL:8d}  {SECT_BALL:8d}  {RIGID_MID:8d}         0         0         0         0         0\n")

    # Nodes
    L.append("*NODE\n")
    for nid, x, y, z in block_nodes:
        L.append(fmt_node(nid, x, y, z))
    for nid, x, y, z in ball_nodes:
        L.append(fmt_node(nid, x, y, z))

    # Solid elements (foam)
    L.append("*ELEMENT_SOLID\n")
    L.append("$#   eid     pid      n1      n2      n3      n4      n5      n6      n7      n8\n")
    for elem in block_elems:
        L.append(fmt_solid(*elem))

    # Shell elements (ball)
    L.append("*ELEMENT_SHELL\n")
    L.append("$#   eid     pid      n1      n2      n3      n4\n")
    for elem in ball_elems:
        L.append(fmt_shell(*elem))

    # Boundary conditions
    L.append("$ Foam bottom (z=0) — all 3 translations fixed\n")
    L.append("*SET_NODE_LIST_TITLE\n")
    L.append("foam_bottom\n")
    L.append("       100\n")
    for chunk_start in range(0, len(foam_bottom_nodes), 8):
        chunk = foam_bottom_nodes[chunk_start:chunk_start + 8]
        L.append("".join(f"{n:10d}" for n in chunk).rstrip() + "\n")
    L.append("*BOUNDARY_SPC_SET\n")
    L.append("$#     nsid       cid      dofx      dofy      dofz     dofrx     dofry     dofrz\n")
    L.append("       100         0         1         1         1         0         0         0\n")

    # Prescribed motion of the rigid ball (z-direction, push then lift)
    # Curve: triangular displacement from 0 -> -INDENT_DEPTH at PUSH_TIME -> 0 at ENDTIME
    L.append("$ Ball z-displacement: triangular (push then lift)\n")
    L.append("*BOUNDARY_PRESCRIBED_MOTION_RIGID\n")
    L.append("$#     pid       dof       vad      lcid        sf       vid     death     birth\n")
    L.append(f"  {PART_BALL:8d}         3         2  {LCID_PUSH:8d}       1.0         0  1.000E20       0.0\n")
    L.append("*DEFINE_CURVE\n")
    L.append(f"$#    lcid      sidr       sfa       sfo\n")
    L.append(f"  {LCID_PUSH:8d}         0       1.0       1.0\n")
    L.append("$#               a1                  o1\n")
    L.append(f"               0.0               0.0\n")
    L.append(f"  {PUSH_TIME:16.6f}  {-INDENT_DEPTH:16.6f}\n")
    L.append(f"  {ENDTIME:16.6f}               0.0\n")

    # Contact: ball (slave shells) vs foam (master, top face)
    # SOFT=2 (segment-based) — much gentler penalty for soft materials like foam
    L.append("$ Contact: ball vs foam — SOFT=2 (segment-based, gentle penalty for soft foam)\n")
    L.append("*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE\n")
    L.append("$#    ssid      msid     sstyp     mstyp    sboxid    mboxid       spr       mpr\n")
    L.append(f"  {PART_BALL:8d}  {PART_FOAM:8d}         3         3         0         0         0         0\n")
    L.append("$#      fs        fd        dc        vc       vdc    penchk        bt        dt\n")
    L.append("       0.3       0.2       0.0       0.0       0.0         0       0.0  1.000E20\n")
    L.append("$#     sfs       sfm       sst       mst      sfst      sfmt       fsf       vsf\n")
    L.append("       1.0       1.0       0.0       0.0       1.0       1.0       1.0       1.0\n")
    L.append("$#    soft    sofscl    lcidab    maxpar     sbopt     depth     bsort    frcfrq\n")
    L.append("         2       0.1         0     1.025         2         2         0         1\n")
    L.append("$ SOFT=2: segment-based penalty (works well for hard ball / soft foam)\n")

    L.append("*END\n")

    out_path.write_text("".join(L), encoding="ascii", errors="replace")
    print(f"Wrote {out_path}  ({out_path.stat().st_size} bytes)")
    print(f"  foam: {len(block_nodes)} nodes, {len(block_elems)} hex elements ({nx}x{ny}x{nz})")
    print(f"  ball: {len(ball_nodes)} nodes, {len(ball_elems)} shell elements (radius={ball_radius:.3f} in)")
    print(f"  endtime={ENDTIME}s, push depth={INDENT_DEPTH:.2f} in (push {PUSH_TIME}s, lift {LIFT_TIME}s)")


if __name__ == "__main__":
    main()
