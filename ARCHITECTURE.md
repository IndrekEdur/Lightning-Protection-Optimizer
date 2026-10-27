# Architecture

The independent Python engine lives in `backend/lpo`; HTTP and React are adapters.

- `models.py`: finite metre-based project schema, role-separated solids, mounting surfaces, catalogue and manual rods.
- `geometry.py`: parametric roof, grids and installation masks.
- `calculation.py`: existing synthetic angle demo and explicit normative-data gate.
- `sphere_collision.py`: KD-tree triangle broad phase, signed closest-surface distance, exact segment distance and upward ray/triangle/segment swept-sphere distance.
- `rolling_sphere.py`: solid validation, cached scene collision geometry, mounting checks, interactive inspection, adaptive point/direction verification and analytical sagitta.
- `surface_certificate.py`: continuous triangle-patch proof, convex feature normal cones, analytical spherical support bounds and joint spatial/angular subdivision. Static sphere-center exclusion suffices without computing general exterior connectivity. A no-contact sample is never evidence of surface-wide protection. Convex feature directions use local outward normal cones; nonconvex features fall back to the complete sphere.
- `mounting.py`: candidate base elevations on selected upward-facing surfaces; plane projections preserve slope/height. Installation rectangles apply in world XY.
- `sphere_optimizer.py`: regular seed search, necessary static-contact MILP cuts, continuous configuration certification, verified incumbent retention, bounded candidate refinement and final independent point/direction cross-check. Limits and objective lower bounds are reported; no global optimality claim.
- `reports.py`: server-signed calculation/result pairing; real XLSX and PDF reports with geometry proof metadata and explicit outstanding checks.
- `api.py`: validation, calculation, contact inspection and signed downloads.

`frontend/src/main.tsx` owns project editing/persistence, asynchronous calculation revision guards and saved objective comparisons. `Sphere.tsx` renders real geometry, sphere and contacts; `Results.tsx` renders continuously classified surface patches and comparison tables. Three.js coordinates are x,z,y; backend coordinates are x,y,z. Model or price changes clear comparisons and invalidate pending calculation responses. Reports reject changed projects/results.

## Proof boundary

At a smooth solid face interior, only the outward-normal tangent center can make contact without penetrating the solid locally. The maximum distance to a rod segment over an affine triangle is at a vertex. Subdivision handles multiple rods without assuming independent circular protection as the system model.

For a physical convex edge/vertex, local admissible directions form the cone of incident outward face normals. Edge arcs and spherical triangle fans cover the full cone; analytical support enumerates vertices, edge stationary points and interior stationary points. For each spatial/direction product patch, upper bounds establish penetration by a rod, solid or ground. Nonconvex features use the whole sphere. Every target patch must be blocked before model status becomes Protected.

Unprotected witnesses additionally have a certified upward exterior path using exact swept ray distances. A blocked upward path is not a claim of inaccessibility; unresolved cases remain Undetermined. Static exclusion is deliberately conservative around enclosed cavities. Self-intersecting input meshes must be rejected by the upstream model-validation workflow; the current checker does not comprehensively detect all self-intersections. Zero-radius rods and ideal solids are geometric assumptions. Geometric verification is distinct from full IEC/EN electrical/structural compliance.

Future IFC adapters must preserve source bytes, GUIDs, units and world transforms and export to a separate file. No IFC importer existed before this extension.
