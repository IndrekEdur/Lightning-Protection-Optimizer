# Lightning Protection Optimizer

Working local prototype: Python calculation engine + FastAPI + React/Three.js workspace.

**Engineering status: continuous rolling-sphere geometry verification with documented bounds; synthetic angle demo. No edition-wide IEC/EN compliance claim.**
Verified edition-specific protection-angle data were unavailable. The UI offers a separate user-defined constant-angle demonstration; this is not the normative Protection Angle method. Normative Protection Angle requests fail explicitly; Rolling Sphere contact search is now available (see extension below). LPS selects the rolling-sphere radius; edition remains metadata pending engineering validation.

## Run locally
Requires Python 3.11+ and Node 20.19+ (or 22.12+).

```bash
cd /workspace/Lightning-Protection-Optimizer
python -m venv .venv
.venv/bin/pip install -r requirements.txt
PYTHONPATH=backend .venv/bin/uvicorn lpo.api:app --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
cd /workspace/Lightning-Protection-Optimizer/frontend
npm ci --cache /tmp/lpo-npm-cache
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to port 8000. API documentation: http://localhost:8000/docs. Use development servers locally; authentication/deployment hardening is not included.

Load `examples/flat-roof-30x40.json` with Open project, then Run optimization. Prices persist in browser local storage and exported project JSON. Export results writes the project, rods, solver status, costs and independently checked samples to JSON. Select a rod in 3D or the dropdown, change coordinates, select manual placement and recalculate. Rectangles control required protection, permitted locations and prohibited installation areas. All dimensions are metres; price units are the project's chosen currency.

## Verification

```bash
PYTHONPATH=backend .venv/bin/pytest backend/tests -q
cd frontend
npm run build
```

Tests include analytical cone boundaries, exhaustive enumeration versus MILP, infeasibility, manual geometry constraints, refined verification, API validation and explicit rejection of unverified methods. Independent references validate synthetic geometry only, not lightning physics.

## Limits

- The original demo uses a flat rectangular roof. Rolling Sphere supports additional solid meshes/equipment; IFC loading is available; no IFC export yet. Install IFC dependencies with requirements-ifc.txt.
- Cost optimization solves set cover with one rod per candidate location. A 15-second HiGHS limit is reported; optimal status applies only to the candidate and sample grids. A refined check can find gaps and does not silently certify a solution.
- Rolling Sphere certificates cover continuous modeled surfaces, including physical edges/corners. A budget-limited proof returns undetermined. Synthetic angle results remain point-sampled.
- Dense grids have explicit memory/work limits. Grid spacing is a maximum; boundaries are always included.
- No labor, ballast, accessories, separation-distance, structural, bonding or down-conductor calculations.
- Synthetic angle is measured from vertical and uses height above this single flat protection plane, independent of roof elevation. LPS class does not change demo geometry.

See ARCHITECTURE.md and ROADMAP.md. No GitHub repository was created; remote account/repository access was not configured.

## Rolling Sphere workflow

Select **Rolling Sphere Method**, LPS I/II/III/IV (20/30/45/60 m), then cost/count/manual objective. Add equipment boxes and assign protected/obstacle/air_terminal/excluded roles. Project JSON accepts closed triangulated `meshes`, so roof levels, slopes, parapets and explicitly included neighbouring solids participate in collisions. IFC loading is now implemented; see WINDOWS_IFC.md for its review workflow and limits.

Select mounting surfaces: upward-facing faces of chosen equipment/meshes generate candidates at actual base elevations. `min_mount_normal_z` defaults to 0.5 (maximum 60 degree mounting slope) and can be changed in project JSON. Permitted/prohibited rectangles apply in world XY within the project footprint. Floating rods or rods crossing solids are rejected. Manual rods use `base_z` for other elevations.

Green surface patches have a continuous geometry proof, amber patches remain unresolved, red patches contain a detected unprotected contact (red does not mean every point of that triangle is exposed). A certificate includes the physical roof edges and vertices, not only triangle interiors. Object status is available by clicking/selecting an object. Click a red point to inspect its actual witness sphere; edit the sphere center to inspect contacts with the model and rods. Manual inspection is not exhaustive verification.

Run different objectives to populate the comparison table; load a previous configuration by clicking its objective. Geometry or price changes clear comparisons. Move/add/remove rods and use manual recalculation. Coordinate and height schedules accompany results.

JSON, Excel and PDF exports include LPS, radius, standard edition, model/ground assumptions, tolerances, certificate depth, resolution, contacts, rod schedule, costs, solver status and outstanding checks. Excel/PDF downloads verify a server signature, so changing a calculation or restarting the backend requires recalculation.

### Calculation and optimization

1. KD-tree triangle broad phase, exact point/triangle and sphere/vertical-segment distances; winding-number solid-interior checks.
2. Contact search with adaptive direction refinement and exact upward swept-sphere escape checks. A detected unprotected witness is collision-free and connected to the exterior by a verified ray.
3. Continuous certificate: smooth triangle interiors have a unique outward normal tangent center. Convexity bounds all centers over each triangle patch. Adaptive subdivision resolves multi-rod shielding. Physical edges/vertices use their full convex normal cones; nonconvex features conservatively use the full sphere. Analytical spherical support functions bound entire direction patches, with ground/solid/rod collision bounds. Every patch must be eliminated to return Protected.
4. Static exclusion proves that **no** admissible contact center exists anywhere on required surfaces. This is stronger than excluding only exterior-connected centers, and can conservatively leave trapped-cavity cases Undetermined. No-contact samples alone never establish a certificate.
5. The optimizer searches regular seeds, necessary static-contact MILP cuts and verified incumbent reductions. Full configurations are certified; a separate scalar distance/direction check cross-checks successful certificates. Final geometry is rebuilt and verified. Return the best certified incumbent even when a cheaper candidate is unresolved. If needed, one bounded candidate-grid refinement is attempted.

Typical search bounds: 55-second optimization budget (checked between bounded operations), 16 cut rounds, 3 solver seconds per round, up to 1500 candidate/type combinations. Final verification has its own 20-second budget. Manual verification allows 30 seconds. Certificates have explicit node/depth limits and return Undetermined on exhaustion. Finite-grid/heuristic results are **best verified solutions found**, not globally optimal continuous placement.

### Status contract and API

- `protected`: continuous modeled surface geometry verified within stated tolerances; `geometry_verified=true`.
- `unprotected`: admissible exterior-accessible sphere contact detected.
- `undetermined`: geometric proof did not close within limits; never promoted to protection based on samples.
- `invalid_model`: missing/unreliable solid geometry or invalid rod mounting.

`engineering_verified` remains false: bonding, down conductors, separation distances, structural checks and standard-edition applicability are not evaluated.

`POST /api/optimize`: project calculation and signed report token.
`POST /api/sphere/inspect`: project plus `center: [x,y,z]`, z up, metres.
`POST /api/report/xlsx` or `/pdf`: `{project, result}` from the same unchanged calculation.
`POST /api/project/validate`: schema/default validation.

### Geometry limits

Input meshes must be closed, outward oriented, non-self-intersecting solid meshes in metres. Open/gapped, duplicate, degenerate and inconsistent meshes are rejected. General mesh self-intersection is not comprehensively diagnosed: externally validate complex imported meshes. Other unobstructed exterior paths can exist when the upward ray is blocked; such unresolved cases remain Undetermined unless the stronger static-exclusion proof succeeds. Rods are zero-radius vertical segments. No wires, labor, bases, ballast, cabling or structural calculations. The existing normative Protection Angle adapter remains unavailable until verified edition-specific tables are supplied.

## Validation and examples

47 automated tests pass, including analytical single/two-rod references, the 1.125178063 m sagitta, 3D edge approaches, equipment, sloped mounting, robustness, exact support bounds, continuous certification, budget exhaustion and signed Excel/PDF export. TypeScript/Vite build passes with a Three.js bundle-size warning. One upstream Starlette/httpx deprecation warning is present.

`examples/rolling-sphere.json`: manual equipment example.
`examples/rolling-sphere-30x40-result.json`: 30 x 40 m, LPS III, 5 m candidate grid, prices A=100/B=180: a continuously verified solution with **9 type-A 2.5 m rods, cost 900**, found in about 7 seconds in the recorded run. Search terminated on an unresolved cheaper candidate; this is not an optimality claim.

Optional browser verification (running backend/Vite plus system Chromium):

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python frontend/tests/browser_workflow.py
```

See ARCHITECTURE.md and ROADMAP.md for proof boundaries and future IFC work.

Browser workflow verified in Chromium: project import, cost/count comparison, continuous geometry status, sphere inspection, Excel and PDF downloads; zero JavaScript runtime errors. Screenshot: `artifacts/rolling-sphere-verified.png`.

## Windows / IFC testing

See [WINDOWS_IFC.md](WINDOWS_IFC.md) for setup/start/test PowerShell scripts, private `test_models/` storage and IFC geometry interpretation. Install `requirements-ifc.txt` for import support. Import IFC2x3/IFC4 from the left panel; review roles, omitted/invalid elements and ground/reference elevation before accepting protection. Original placement coordinates and source-unit/CRS metadata are retained; viewer recentering is display-only. IFC calculations use imported meshes and never the rectangular demonstration roof.

Current validation: 75 backend tests pass, frontend build succeeds and the synthetic IFC Chromium workflow passes. Tests exercise real IfcOpenShell geometry parsing but **no actual client BIM file or Windows host was available**. Real-building engineering validation and Windows execution remain pending.
