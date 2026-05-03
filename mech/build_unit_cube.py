"""Drive a Workbench-launched Mechanical session to build a single-element
unit cube uniaxial test rig and export it as a `.k` file.

Assumes:
  - Sam's Workbench is open with an LS-DYNA system named 'SYS'
  - Workbench scripting `StartServer()` has been called and Sam reported the port
  - There's a 1 in cube body (he built it manually)

Run: $PY -m mech.build_unit_cube <wb_port>

The script is written so each phase is a separate function — easy to call
piecewise from a REPL when debugging.
"""
from __future__ import annotations

import sys
import warnings

from ansys.workbench.core import connect_workbench
import ansys.mechanical.core as pymech

warnings.filterwarnings("ignore")


def attach(wb_port: int):
    wb = connect_workbench(port=wb_port, security="insecure")
    mech_port = wb.start_mechanical_server(system_name="SYS")
    mech = pymech.connect_to_mechanical(
        ip="localhost", port=mech_port, cleanup_on_exit=False
    )
    return wb, mech, mech_port


# --- IronPython scripts run inside Mechanical ---

INSPECT_FACES = """
body = Model.Geometry.Children[0].Children[0]  # the only solid
geo_body = body.GetGeoBody()
faces = list(geo_body.Faces)
out = []
for i, f in enumerate(faces):
    c = f.Centroid
    out.append('  face[%d]: id=%d centroid=(%.3f,%.3f,%.3f) area=%.4g' %
               (i, f.Id, c[0], c[1], c[2], f.Area))
str(len(faces)) + ' faces:' + chr(10) + chr(10).join(out)
"""

CREATE_NS_FACES = """
# Create Named Selections for the 6 faces, named by which axis-extreme they sit on
import math
body = Model.Geometry.Children[0].Children[0]
faces = list(body.GetGeoBody().Faces)
# Sort by centroid coordinate to identify min/max along each axis
def axis_extreme(faces, axis_idx, want_min):
    return sorted(faces, key=lambda f: f.Centroid[axis_idx])[0 if want_min else -1]

face_map = {
    'face_xmin': axis_extreme(faces, 0, True),
    'face_xmax': axis_extreme(faces, 0, False),
    'face_ymin': axis_extreme(faces, 1, True),
    'face_ymax': axis_extreme(faces, 1, False),
    'face_zmin': axis_extreme(faces, 2, True),  # bottom
    'face_zmax': axis_extreme(faces, 2, False), # top
}

# Remove any pre-existing NSs by these names so this is idempotent
existing = {ns.Name: ns for ns in Model.NamedSelections.Children}
for nm, face in face_map.items():
    if nm in existing:
        existing[nm].Delete()
    ns = Model.AddNamedSelection()
    ns.Name = nm
    sel_info = ExtAPI.SelectionManager.CreateSelectionInfo(
        Ansys.ACT.Interfaces.Common.SelectionTypeEnum.GeometryEntities)
    sel_info.Ids = [face.Id]
    ns.Location = sel_info

str([nm for nm in face_map.keys()])
"""

MESH_SINGLE_ELEMENT = """
# Force a single hex element by setting size = bounding-box diagonal of the body.
# For a 1-in cube in U.S. Customary, that's 1 in. Mechanical wants the value in
# the project's length unit (US Customary inches in this case).
mesh = Model.Mesh
mesh.ElementOrder = ElementOrder.Linear

# Use a body sizing of 1 in to force a single element
body = Model.Geometry.Children[0].Children[0]
sizing = mesh.AddSizing()
sel_info = ExtAPI.SelectionManager.CreateSelectionInfo(
    Ansys.ACT.Interfaces.Common.SelectionTypeEnum.GeometryEntities)
sel_info.Ids = [body.GetGeoBody().Id]
sizing.Location = sel_info
sizing.ElementSize = Quantity('1 [in]')

# Hex method — single linear hex
method = mesh.AddAutomaticMethod()
method.Location = sel_info
method.Method = MethodType.MultiZone

mesh.GenerateMesh()
'mesh nodes: ' + str(mesh.Nodes) + ', elements: ' + str(mesh.Elements)
"""


def inspect_faces(mech):
    return mech.run_python_script(INSPECT_FACES)


def create_face_named_selections(mech):
    return mech.run_python_script(CREATE_NS_FACES)


def mesh_single_element(mech):
    return mech.run_python_script(MESH_SINGLE_ELEMENT)


if __name__ == "__main__":
    wb_port = int(sys.argv[1]) if len(sys.argv) > 1 else 56112
    wb, mech, mech_port = attach(wb_port)
    print(f"[attached] mech_port={mech_port}")

    # phase 1: inspect
    print("[phase 1] face inspection")
    print(inspect_faces(mech))
    print()

    # phase 2: name the faces
    print("[phase 2] create face named selections")
    print(create_face_named_selections(mech))
    print()

    # phase 3: mesh
    print("[phase 3] mesh")
    print(mesh_single_element(mech))
