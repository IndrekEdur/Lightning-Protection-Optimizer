# Roadmap

## Delivered — Rolling Sphere extension

LPS I-IV; 3D sphere/solid/rod collision; multi-rod and equipment interactions; ground and explicitly included neighbouring solids; multiple elevations/slopes; physical edge/corner checks; continuous adaptive surface certificates; Protected/Unprotected/Undetermined/Invalid-model states; exterior-contact witnesses; automatically generated mountings on chosen surfaces; cost/count/manual optimization with certified incumbent retention; candidate refinement; independent final cross-check; interactive sphere/object/rod inspection; classified surface visualization; configuration comparisons; coordinate schedules; signed Excel/PDF/JSON outputs; analytical and integration tests.

The recorded 30 x 40 m LPS III example has a verified 9 x 2.5 m configuration costing 900 at catalogue prices 100/180. It is the best verified configuration found by the bounded search, not a claimed global optimum.

## Engineering limits and next improvements

General free-space connectivity can reduce conservatism in cavities: currently upward rays prove detected exposure and stronger static exclusion proves protection. Budget-exhausted cases correctly remain Undetermined. Improve independent engineering dataset validation, comprehensive mesh self-intersection validation, rod finite-radius/wire modeling, structural/electrical checks and standard-edition applicability review. Existing normative Protection Angle still needs authorized verified height-dependent tables.

## IFC stage

IfcOpenShell IFC2x3/IFC4 import, original coordinate/unit/GUID preservation, manual classification and original-file-safe IFC export. IFC loading/export did not exist before this task and is not silently represented by the JSON mesh adapter.

## Production and cost extensions

Labor, bases, ballast and cabling; background jobs, cancellation and access control; certified search bounds and larger-model performance improvements. Excel/PDF reporting and continuous modeled-surface certification are now implemented.

## IFC local-testing integration

Implemented IfcOpenShell STEP import for IFC2x3/IFC4, unit/placement/CRS provenance, geometry/role review, equipment retention, imported world-coordinate viewer and Rolling Sphere connection, mounting projection, private test_models storage, Windows scripts, diagnostics and real-parser synthetic tests. This replaces the earlier statement that IFC loading was absent. IFC export remains unimplemented.

Still pending: validation with actual client IFC building models (none supplied in the execution workspace), execution on the target Windows machine, exporter-specific classification tuning, robust mesh self-intersection validation/repair, large-model asynchronous jobs and performance beyond documented limits. Preserve engineering unknowns rather than certifying incomplete geometry.


Delivered height-range import: SI world-Z minimum/maximum, inclusive whole-element selection, same-file reimport, excluded-element diagnostics, failed-import preservation, camera/origin reset, streaming source hash and configurable larger uploads. Future performance work: provably conservative pre-tessellation bounds, background jobs/progress and cancellation. Current filtering still tessellates each represented element before deciding inclusion.


Delivered federated IFC import: multiple-file or incremental additions; source-specific units, height filters and diagnostics; explicit source replacement/removal; source-scoped GUIDs and omission acknowledgments; combined geometry calculations; atomic import batches; per-file reports and project persistence. Survey/CRS alignment remains explicit upstream work, not automatic federation. Combined model/calculation limits remain unchanged.


Sphere inspection supports fixed-XY vertical descent to first contact with rod segments, building triangles or reference ground. The monotone upward swept-sphere distance predicate is bisected to at most min(tolerance/4, 1e-6 m). Choose a rod pair to inspect at its horizontal midpoint; other geometry can intercept first, and unequal tip heights need not give simultaneous contact. The sphere is hidden initially. Inspection is separate from whole-model protection verification.
