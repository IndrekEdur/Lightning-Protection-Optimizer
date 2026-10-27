# Windows development and IFC test workflow

This repository was configured and executed on Linux/Python 3.12 in the current session. The PowerShell scripts are provided for Windows; they have not been executed on a Windows machine here. No real client IFC file was supplied. Synthetic STEP IFC fixtures exercise the real IfcOpenShell parser/geometry kernel; they are not real-building validation.

## Install

Use 64-bit Python 3.11, 3.12 or 3.13 and Node 20.19+ or 22.12+. Open PowerShell in the repository root:

```powershell
.\scripts\setup-windows.ps1 -PythonVersion 3.12
```

Equivalent commands if running scripts is restricted:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-ifc.txt
New-Item -ItemType Directory -Force test_models
npm --prefix frontend ci
```

Run in separate terminals:

```powershell
.\scripts\start-backend.ps1
```

```powershell
.\scripts\start-frontend.ps1
```

Or start directly:

```powershell
$env:PYTHONPATH = "$PWD\backend"
.\.venv\Scripts\python.exe -m uvicorn lpo.api:app --host 127.0.0.1 --port 8000
# In another terminal:
npm --prefix frontend run dev -- --host 127.0.0.1
```

Open http://127.0.0.1:5173 and API documentation at http://127.0.0.1:8000/docs. Both startup scripts bind to loopback. IFC uploads go to this backend, not a third-party BIM service. Temporary upload files are closed before parsing (Windows compatible) and deleted after import, including on error. Source files are read without rewriting.

## Private model storage

Put actual IFC files and derived JSON/PDF/XLSX outputs in `test_models/`. The entire directory is ignored by Git; raw IFC/IFCZIP/IFCXML files are additionally ignored outside it. Imported geometry is not persisted into browser local storage; save project JSON explicitly if needed. Saved JSON contains client geometry and identifiers and must be treated as private BIM data. Never force-add client models.

```powershell
git check-ignore test_models\client-building.ifc
```

## Import and engineering review

1. Choose an uncompressed `.ifc` with **Import IFC2x3 / IFC4**. Review schema, source unit scale, element/triangle counts and timing.
2. Review required surfaces and equipment. IfcRoof, ROOF slabs, roof aggregate children, distribution elements and proxies are initially protected; other represented elements are obstacles. These are preliminary classifications. Use the IFC element search/role selector to correct them. Missing classifications do not automatically prove protection.
3. Read the import diagnostics. Failed/omitted elements block calculation until individually and explicitly excluded. Non-watertight, duplicate, degenerate or incorrectly oriented meshes remain visible but invalidate calculation while included. Repair them upstream or deliberately exclude them after reviewing the engineering implications.
4. Confirm **ground/reference elevation**. The loader proposes minimum imported z only as an initial value; a roof-only model does not identify real ground. Confirm the reference and classification review checkboxes before accepting a Protected result. Preliminary exposure checks remain available without confirmation.
5. Select actual mounting surfaces; candidates are projected onto their real triangles at their actual elevation. Add a manual rod using an imported mounting. Edit its world x/y/base z if needed; floating bases/intersections are rejected.
6. Run Rolling Sphere. Smooth faces, physical edges/corners and rooftop equipment participate. An unresolved numerical/proof budget returns Undetermined. No dummy rectangular roof is included in IFC mode. The angle demo rejects IFC input rather than flattening it.

All engine/project coordinates are in metres at the original IFC placement origin. IfcOpenShell `USE_WORLD_COORDS` resolves nested placements and rotations; geometry already arrives in SI metres and is **not scaled a second time**. Original unit assignments, source unit scale, GUIDs/names/classes, file SHA256 and map conversion/CRS are retained. Map conversion is **not** additionally applied to geometry: the calculation frame is the IFC placement frame, with conversion metadata available for external survey alignment.

The viewer uses a display-only floating origin; vertex subtraction happens before float32 buffers are built. Engine coordinates, saved projects, rod schedules and source metadata remain world coordinates. Do not interpret the display origin as a coordinate transformation of the project.

Certificates refer to the tessellated mesh, not exact native BRep curvature. Import diagnostics record linear/angular meshing deflection. Complex mesh self-intersections are not comprehensively validated. Electrical/structural IEC/EN compliance remains unverified.

## Diagnostics and tests

```powershell
.\scripts\test-windows.ps1
# Or:
$env:PYTHONPATH = "$PWD\backend"
.\.venv\Scripts\python.exe -m pytest backend/tests -q
npm --prefix frontend run build

.\.venv\Scripts\python.exe scripts\inspect-ifc.py test_models\client-building.ifc
.\.venv\Scripts\python.exe scripts\inspect-ifc.py test_models\client-building.ifc --verify
.\.venv\Scripts\python.exe scripts\inspect-ifc.py test_models\client-building.ifc --save-project test_models\client-building.project.json
```

The CLI reports schema/units/world bounds, source integrity, per-element failures, tessellation limits, slowest elements, import duration, scene-build duration, geometry counts and manual/no-rod calculation status. `--verify` does not optimize rod placement. Errors have clear messages and a nonzero exit status for input failures.

Optional browser tests require `requirements-dev.txt` and Chromium (or `python -m playwright install chromium`). Start both servers first:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe frontend\tests\ifc_browser_workflow.py
```

Synthetic fixture coverage: IFC2x3/IFC4, metre/millimetre/foot units, large offsets, nested rotated placements, slopes, equipment, map conversion retention, corrupt/missing-unit input, omitted geometry and invalid meshes. Browser workflow tests upload, SI metadata, floating-origin rendering, real-mesh rolling-sphere contact and manual mounting.

## Performance and remaining work

Preview: 512 MiB uncompressed file, 1000 elements, 250000 triangles; per element 100000 vertices/200000 faces. Engine: 30000 included triangles, bounded certificate nodes/time, 3000 independent targets and 1500 candidate/type combinations. Large files may preview successfully but be unsuitable for engineering verification at these limits. Select/export a relevant source subset; excluded objects no longer participate in collisions. Never call a subset a whole-building check.

Native tessellation executes synchronously in a worker thread; job cancellation/background progress and large-model persistent caching remain future work. No general topological repair, automatic roof inference for every exporter, comprehensive self-intersection proof, terrain inference, IFC placement export or exhaustive general exterior-connectivity solver is included. Unrepresented elements and large-model independent verification limits must be resolved before accepting protection.

Real-building validation is still pending: run actual client files from `test_models/`, check source dimensions/elevations against the authoring tool and compare rod/reference cases with an independent engineering calculation. Windows dependency/startup verification must also be performed on the target Windows machine.


## Import only a height range

Before choosing an IFC file, enter **Minimum import height · m** and/or **Maximum import height · m** in the IFC panel. Empty fields mean no lower/upper bound. Heights are absolute IFC placement/world Z coordinates in SI metres, even when the source file uses millimetres or feet. They are not storey-relative values or elevations after map conversion.

An element is included when its tessellated world Z bounds intersect the requested band (inclusive). The **entire element** is retained, preserving closed solids, sloping roofs and tall equipment crossing the band. This is not geometric clipping: a tall wall can remain even if most of it is below the selected range. Entering only a minimum is useful for upper roof regions, but can include all higher objects too.

After changing the bounds, click **Import selected file with height range** to re-import without browsing again. The loaded range is recorded beside the loaded model; editing input bounds alone does not change the existing model. Failed imports explicitly keep the prior model. An empty match returns an error rather than replacing the model with an empty or unrelated scene.

Only retained geometry counts toward preview element/triangle limits. Exact selection currently tessellates each represented element before testing its bounds, so this reduces retained geometry and validation work but does not eliminate whole-file parsing/native tessellation time. Elements with unreadable/missing geometry remain failures because their heights cannot safely be inferred. No placement-only shortcut discards rotated/sloping elements.

Uploads now default to 512 MiB. To choose a different local limit, set this environment variable in the backend terminal **before starting the server**:

```powershell
$env:LPO_IFC_MAX_UPLOAD_MIB = '1024'
```

Larger IFC files still need sufficient RAM, and selected meshes remain subject to the existing preview/calculation limits. SHA256 hashing now streams the file instead of allocating a second full-file byte buffer.

A height-filtered subset can omit nearby obstacles and lower building geometry relevant to side approaches. Confirm the subset's engineering scope and ground reference explicitly; no height filter establishes whole-building compliance.

CLI equivalent:

```powershell
.\.venv\Scripts\python.exe scripts\inspect-ifc.py test_models\building.ifc --height-min 18 --height-max 26 --save-project test_models\roof.project.json
```

Validation of this addition: 75 backend tests pass; frontend production build passes. Tests cover metre/millimetre units, open/equal/inverted bounds, empty selection, sloped world geometry and filtering before retained-mesh budgets. Chromium tests exercise same-file reimport and preservation of the previous model after a failed height selection.
