"""Explicit IFC source federation; shared SI placement frame, no automatic alignment."""
import hashlib
import json
from .models import Project,IfcSource,IfcMetadata


def initial_source(project):
    """Upgrade a single/legacy IFC project without losing raw GUID provenance."""
    if project.geometry_source!='ifc' or project.ifc_sources or not project.ifc_metadata:return project
    meta=project.ifc_metadata
    sid=hashlib.sha256((meta.filename+'\0'+meta.source_sha256).encode()).hexdigest()[:16]
    source=IfcSource(**meta.model_dump(),source_id=sid)
    names={mesh.name:f'{sid} / {mesh.name}' for mesh in project.meshes}
    return project.model_copy(update={'ifc_sources':[source],
        'meshes':[mesh.model_copy(update={'ifc_source_id':sid,'name':names[mesh.name]}) for mesh in project.meshes],
        'candidate_surfaces':[names.get(name,name) for name in project.candidate_surfaces],
        'acknowledged_ifc_omissions':[f'{sid}:{guid}' for guid in project.acknowledged_ifc_omissions],
        'ifc_metadata':summary([source],project.meshes)})


def summary(sources,meshes):
    if not sources:return None
    # Compute the joint bounds from preserved source bounds without moving them.
    bounds=[[min(s.bounds_m[0][axis] for s in sources) for axis in range(3)],
            [max(s.bounds_m[1][axis] for s in sources) for axis in range(3)]]
    failures=[{**failure,'source_guid':failure['guid'],'guid':f'{s.source_id}:{failure["guid"]}','source_id':s.source_id,'filename':s.filename} for s in sources for failure in s.failures]
    warnings=list(dict.fromkeys(warning for s in sources for warning in s.warnings))
    guids=[m.ifc_guid for m in meshes if m.ifc_guid]
    if len(guids)!=len(set(guids)):warnings.append('Repeated IFC GUIDs across source files are kept separately; review duplicate physical geometry. Reported surface area sums source surfaces and is not a union-area calculation.')
    warnings.append('Federated geometry uses original SI IFC placement coordinates; no automatic survey/CRS alignment is applied. Review model overlap and offsets.')
    if len(sources)==1:
        return IfcMetadata(**{**sources[0].model_dump(exclude={'source_id'}),'failures':failures,'warnings':warnings})
    fingerprints=[(s.source_id,s.source_sha256,s.height_min_m,s.height_max_m) for s in sources]
    signature=hashlib.sha256(json.dumps(fingerprints,sort_keys=True).encode()).hexdigest()
    # Summaries must not suggest that mixed source units are one source unit.
    warnings.append('Mixed source metadata: inspect each file for its own source units, height filter and CRS.')
    return IfcMetadata(filename=' + '.join(s.filename for s in sources),schema_name='Federated IFC',source_sha256=signature,
        length_unit_scale_to_m=1.,source_units=[{'source_id':s.source_id,'filename':s.filename,'units':s.source_units} for s in sources],
        coordinate_reference='Federated SI IFC placement coordinates; per-source map conversions retained, not applied',
        map_conversions=[{'source_id':s.source_id,'filename':s.filename,'conversions':s.map_conversions} for s in sources],
        bounds_m=bounds,failures=failures,warnings=warnings,diagnostics={
            'import_seconds':sum(s.diagnostics.get('import_seconds',0) for s in sources),'source_bytes':sum(s.diagnostics.get('source_bytes',0) for s in sources),
            'elements_loaded':len(meshes),'triangles':sum(len(m.faces) for m in meshes),'elements_failed':len(failures),
            'elements_filtered_by_height':sum(s.diagnostics.get('elements_filtered_by_height',0) for s in sources),
            'skipped':[{'source_id':s.source_id,**item} for s in sources for item in s.diagnostics.get('skipped',[])],
            'source_count':len(sources),'self_intersections_checked':False})


def merge(project,incoming,replace_source_id=None):
    current=initial_source(project);new=initial_source(incoming)
    if new.geometry_source!='ifc' or len(new.ifc_sources)!=1:raise ValueError('Add one imported IFC source at a time')
    source=new.ifc_sources[0]
    sources=list(current.ifc_sources);meshes=list(current.meshes) if current.geometry_source=='ifc' else []
    candidates=list(current.candidate_surfaces) if current.geometry_source=='ifc' else []
    acknowledgments=list(current.acknowledged_ifc_omissions) if current.geometry_source=='ifc' else []
    if replace_source_id is not None:
        if replace_source_id not in {s.source_id for s in sources}:raise ValueError('IFC source selected for replacement was not found')
        removed_names={m.name for m in meshes if m.ifc_source_id==replace_source_id}
        sources=[s for s in sources if s.source_id!=replace_source_id]
        meshes=[m for m in meshes if m.ifc_source_id!=replace_source_id]
        candidates=[name for name in candidates if name not in removed_names]
        acknowledgments=[a for a in acknowledgments if not a.startswith(replace_source_id+':')]
    if source.source_id in {s.source_id for s in sources}:raise ValueError('This IFC file is already loaded. Select Replace source to change its height range')
    sources.append(source);meshes.extend(new.meshes);candidates.extend(new.candidate_surfaces)
    if len(sources)>20:raise ValueError('At most 20 IFC sources per project')
    if len(meshes)>1000 or sum(len(m.faces) for m in meshes)>250000:raise ValueError('Combined IFC preview exceeds 1000 elements / 250000 triangles; narrow source height ranges')
    metadata=summary(sources,meshes)
    updates={'geometry_source':'ifc','ifc_metadata':metadata,'ifc_sources':sources,'meshes':meshes,'candidate_surfaces':list(dict.fromkeys(candidates)),
        'ifc_review_confirmed':False,'reference_surface_confirmed':False,'acknowledged_ifc_omissions':acknowledgments}
    if current.geometry_source!='ifc':updates.update(name=source.filename,rods=[],equipment=[],protected=[],permitted=[],prohibited=[],ground_z=new.ground_z,width=new.width,depth=new.depth,roof_height=new.roof_height,method='rolling_sphere',objective='manual')
    # Existing catalogue/prices, solver settings, rods and ground are preserved
    # when adding a discipline. Results/review flags must be recalculated.
    return Project.model_validate({**current.model_dump(),**updates})


def remove(project,source_id):
    current=initial_source(project)
    if source_id not in {s.source_id for s in current.ifc_sources}:raise ValueError('IFC source was not found')
    sources=[s for s in current.ifc_sources if s.source_id!=source_id]
    removed_names={m.name for m in current.meshes if m.ifc_source_id==source_id}
    meshes=[m for m in current.meshes if m.ifc_source_id!=source_id]
    return Project.model_validate({**current.model_dump(),'ifc_sources':sources,'meshes':meshes,'ifc_metadata':summary(sources,meshes),
        'candidate_surfaces':[name for name in current.candidate_surfaces if name not in removed_names],
        'acknowledged_ifc_omissions':[a for a in current.acknowledged_ifc_omissions if not a.startswith(source_id+':')],
        'ifc_review_confirmed':False,'reference_surface_confirmed':False})
