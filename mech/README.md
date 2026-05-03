# mech/ — Workbench-bridged Mechanical session

Helpers for driving an Ansys Mechanical session from Python while a user watches the GUI live. **The PyMechanical-only path does NOT work on Ansys Student licensing** for LS-DYNA analyses — see "License-path divergence" below.

## The bootstrap recipe (the only path that works on Student)

### 1. Sam — open Workbench manually

Launch Ansys Workbench, drag an **LS-DYNA** Analysis System from the Toolbox into the Project Schematic. Optionally start building geometry in DesignModeler / SpaceClaim.

### 2. Sam — open the scripting console and start the gRPC server

In Workbench:
```
File → Scripting → Open Command Window
```
(Older builds may have it under **View → Windows → Command Window** or the **Tools** menu.)

In the command window, type and run:
```python
StartServer()
```
Workbench prints a port number, e.g. `56112`. Note it.

### 3. Claude / Python — attach and spin up Mechanical

```python
from ansys.workbench.core import connect_workbench
import ansys.mechanical.core as pymech

WB_PORT = 56112    # the port StartServer() reported

# A. Attach to the running Workbench
wb = connect_workbench(port=WB_PORT, security="insecure")

# B. Enumerate systems (optional but useful)
systems_json = wb.run_script_string('''
import json
wb_script_result = json.dumps([{"Name": s.Name, "DisplayText": s.DisplayText}
                                for s in GetAllSystems()])
''')
print(systems_json)
# Typically: [{"Name": "SYS", "DisplayText": "LS-DYNA"}]

# C. Tell Workbench to start a Mechanical gRPC server attached to the LS-DYNA system
mech_port = wb.start_mechanical_server(system_name="SYS")

# D. Connect to that Mechanical
mech = pymech.connect_to_mechanical(
    ip="localhost",
    port=mech_port,
    cleanup_on_exit=False,    # keep Mechanical alive when this Python process exits
)

# E. Sanity check — add a Named Selection visible in Sam's Outline tree
result = mech.run_python_script('''
ns = Model.AddNamedSelection()
ns.Name = "claude_was_here"
str(ns.Name)
''')
print("Mechanical reports:", result)
```

`mech.run_python_script(...)` sends a multi-line script to Mechanical's IronPython interpreter. Every command updates the Mechanical GUI in real time — Sam sees the model populate as Claude works.

### 4. Use it

Claude can now drive Mechanical for the duration of Sam's Workbench session. Each Claude tool call is a fresh Python process that:

1. `connect_workbench(port=WB_PORT, security='insecure')`
2. `wb.start_mechanical_server(system_name='SYS')` (returns the same `mech_port` for the same system)
3. `pymech.connect_to_mechanical(...)`
4. Issues commands

The `mech/session.py` and `mech/client.py` helpers wrap (1)–(3) so each tool call is one line.

### 5. Tear down

When Sam closes Workbench, the bridge dies cleanly. To shut down the Mechanical server only (without closing Workbench):

```python
wb.stop_mechanical_server(system_name="SYS")
```

## License-path divergence (the why)

There are two ways for Python to launch Mechanical:

| | Method | License-check path | LS-DYNA on Ansys Student? |
|---|---|---|---|
| **Standalone** | `pymech.launch_mechanical(batch=False)` | Mechanical-internal license token | ❌ `Adding LS-DYNA analysis is not allowed` |
| **Workbench-bridge** | `wb.start_mechanical_server(...)` | Workbench-owned, env-var bridge (`ANSYS_LSW_*`) | ✅ Works |

The Mechanical-internal check (used by `launch_mechanical`) does not honor the env-var bridge that the LSTC Student installer creates. The Workbench-owned path does. So on Ansys Student licensing, the Workbench bridge is the **only** way to drive a Mechanical session that has the LS-DYNA Analysis System enabled.

This is presumably not a problem for users with paid Ansys licenses that include LS-DYNA at the Mechanical-internal tier — `launch_mechanical(batch=False)` would Just Work for them. For Student users (likely the majority of LS-DYNA experimenters), the workaround above is required.

## Other gotchas captured during the bootstrap dance

- **Default `security='mtls'`** in `connect_workbench()` — wants certs from `certs/ca.crt`. For a local dev session, pass `security='insecure'`. (`'wnua'` works too on Windows but adds nothing for localhost.)
- **`run_script_string` doesn't return values directly** — assign to `wb_script_result` (a magic global) and JSON-encode it; the function returns whatever string you assigned.
- **`returnValue(...)` is not a Workbench scripting builtin** despite looking like one. Use `wb_script_result = json.dumps(...)`.
- **Mechanical reports `Volume.Value` in the Workbench unit system**, not SI. On a US Customary project, that's `ft³`. Watch for unit confusion.
- **gRPC errors are noisy** — Mechanical's IronPython tracebacks come back wrapped in gRPC framing. `client.run()` strips the framing for readability; raw errors live in `repr(exc)`.
