"""IfcOpenShell adapter: no mesh simplification, recentering, decimation or model repair.

IfcOpenShell geometry returns SI metres; USE_WORLD_COORDS resolves placements.
IFC map conversion/CRS is retained, not silently applied on top of placements.
Original file bytes and source unit metadata remain unchanged.
"""
from pathlib import Path
import hashlib
import time
import numpy as np
import trimesh
from .models import Project,MeshObject,IfcMetadata

MAX_FILE_BYTES=100*1024*1024
MAX_TRIANGLES=250000


def role_for(element):
    kind=element.is_a()
    predefined=getattr(element,'PredefinedType',None)
    if kind=='IfcRoof' or (kind=='IfcSlab' and predefined=='ROOF'):return 'protected','roof'
    # Roof assemblies often place the actual shape on an aggregated slab.
    current=element;seen=set()
    import ifcopenshell.util.element
    while current and current.id() not in seen:
        seen.add(current.id())
        current=ifcopenshell.util.element.get_aggregate(current)
        if current and current.is_a('IfcRoof'):return 'protected','roof'
    if element.is_a('IfcDistributionElement') or kind=='IfcBuildingElementProxy':return 'protected','equipment_or_proxy'
    return 'obstacle','building'


def import_ifc(path, filename=None):
    try:
        import ifcopenshell
        import ifcopenshell.geom
        import ifcopenshell.util.unit
    except ImportError as exc:raise ValueError('IFC dependencies missing. Install: python -m pip install -r requirements-ifc.txt') from exc
    start=time.perf_counter();path=Path(path)
    if path.stat().st_size>MAX_FILE_BYTES:raise ValueError('IFC upload limit is 100 MiB; use a relevant building subset')
    with path.open('rb') as stream:header=stream.read(4096).lstrip(b'\xef\xbb\xbf \t\r\n')
    if not header.startswith(b'ISO-10303-21;'):raise ValueError('Cannot parse IFC: expected an ISO-10303-21 STEP header; compressed/XML files are not supported')
    try:model=ifcopenshell.open(str(path))
    except Exception as exc:raise ValueError(f'Cannot parse IFC STEP file: {str(exc)[:300]}') from exc
    if model.schema not in ('IFC2X3','IFC4','IFC4X1','IFC4X2','IFC4X3','IFC4X3_ADD2'):
        raise ValueError(f'Unsupported IFC schema {model.schema}; IFC2x3/IFC4 expected')
    projects=model.by_type('IfcProject')
    if len(projects)!=1 or not projects[0].UnitsInContext:raise ValueError('IFC requires exactly one project with explicit units')
    assignments=projects[0].UnitsInContext.Units
    length_units=[u for u in assignments if getattr(u,'UnitType',None)=='LENGTHUNIT']
    if len(length_units)!=1:raise ValueError('IFC length unit is missing or ambiguous; do not assume metres')
    scale=float(ifcopenshell.util.unit.calculate_unit_scale(model))
    if not np.isfinite(scale) or scale<=0:raise ValueError('Invalid IFC length unit scale')
    settings=ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS,True)
    settings.set(settings.WELD_VERTICES,True)
    # CONVERT_BACK_UNITS deliberately remains false: geometry is already metres.
    meshes=[];failures=[];skipped=[];timings=[];triangles=0;seen_guids=set()
    for element in model.by_type('IfcElement'):
        if element.is_a('IfcFeatureElementSubtraction'):continue
        guid=element.GlobalId
        if not guid or guid in seen_guids:raise ValueError('IFC element GUID is missing or duplicated; repair source identity before import')
        seen_guids.add(guid)
        role,classification=role_for(element)
        if not getattr(element,'Representation',None):
            if not getattr(element,'IsDecomposedBy',()):
                failures.append({'guid':guid,'ifc_class':element.is_a(),'error':'Element has no geometry representation; inclusion cannot be evaluated'})
            else:skipped.append({'guid':guid,'reason':'No representation; aggregate/container or unrepresented obstacle'})
            continue
        element_start=time.perf_counter()
        try:
            shape=ifcopenshell.geom.create_shape(settings,element)
            vertices=np.asarray(shape.geometry.verts,float).reshape(-1,3)
            faces=np.asarray(shape.geometry.faces,int).reshape(-1,3)
            if not len(vertices) or not len(faces) or not np.isfinite(vertices).all():raise ValueError('Empty/non-finite triangulated geometry')
            # Exact-coordinate welding joins tessellator seam vertices. No near-
            # vertex tolerance weld, hole filling or automatic normal repair.
            vertices,inverse=np.unique(vertices,axis=0,return_inverse=True);faces=inverse[faces]
            if len(vertices)>100000 or len(faces)>200000:raise ValueError('Element exceeds per-mesh geometry limit')
            triangles+=len(faces)
            if triangles>MAX_TRIANGLES:raise OverflowError('IFC preview exceeds 250000 triangles; export a relevant subset')
            mesh=trimesh.Trimesh(vertices,faces,process=False)
            errors=[]
            if np.any(mesh.area_faces<1e-12):errors.append('degenerate triangles')
            if len(np.unique(np.sort(faces,axis=1),axis=0))!=len(faces):errors.append('duplicated faces')
            if not mesh.is_watertight:errors.append('non-watertight solid')
            local=mesh.copy();local.apply_translation(-mesh.bounds.mean(axis=0))
            if not mesh.is_winding_consistent or local.volume<=0:errors.append('inconsistent/outward orientation or non-positive volume')
            diagnostic={'triangle_count':len(faces),'vertex_count':len(vertices),'watertight':bool(mesh.is_watertight),'geometry_errors':errors,'classification':classification,'seconds':time.perf_counter()-element_start}
            meshes.append(MeshObject(name=f'{element.is_a()} {guid}',role=role,ifc_guid=guid,ifc_class=element.is_a(),ifc_name=element.Name,source_unit_scale_to_m=scale,vertices=vertices.tolist(),faces=faces.tolist(),import_diagnostics=diagnostic))
            timings.append({'guid':guid,'seconds':diagnostic['seconds']})
        except OverflowError:raise ValueError('IFC preview exceeds 250000 triangles; export a relevant subset')
        except Exception as exc:failures.append({'guid':guid,'ifc_class':element.is_a(),'error':str(exc)[:500]})
        if len(meshes)>1000:raise ValueError('IFC preview exceeds 1000 elements; export a relevant subset')
    if not meshes:raise ValueError('No renderable IFC element geometry. Check representations and import diagnostics: '+str(failures[:3]))
    bounds=np.array([trimesh.Trimesh(m.vertices,m.faces,process=False).bounds for m in meshes])
    lower=bounds[:,0].min(axis=0);upper=bounds[:,1].max(axis=0)
    warnings=['Certificates concern tessellated mesh geometry, not the exact IFC BRep surfaces.','Classification is preliminary: review roofs, equipment and installation surfaces before calculation.','Ground reference defaults to minimum model z; confirm actual terrain/reference elevation.','Open/invalid solids remain visible but block reliable calculation until explicitly excluded or repaired upstream.','Map conversion/CRS metadata is retained; triangulated coordinates are IFC placement coordinates in metres.']
    if skipped:warnings.append(f'{len(skipped)} elements have no representation; review the skipped-element inventory, including obstacles.')
    if np.max(np.abs(bounds))>1e5:warnings.append('Large world coordinates: viewer uses a display-only floating origin; engine retains world coordinates.')
    maps=[]
    if model.schema!='IFC2X3':
        for conversion in model.by_type('IfcMapConversion'):
            maps.append(conversion.get_info(recursive=True))
    # IFC get_info contains only JSON-compatible primitive values when recursive.
    units=[u.get_info(recursive=True) for u in assignments]
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    metadata=IfcMetadata(filename=Path(filename or path.name).name,schema_name=model.schema,source_sha256=digest,length_unit_scale_to_m=scale,source_units=units,map_conversions=maps,bounds_m=[lower.tolist(),upper.tolist()],warnings=warnings,failures=failures,diagnostics={'import_seconds':time.perf_counter()-start,'source_bytes':path.stat().st_size,'elements_loaded':len(meshes),'triangles':triangles,'elements_failed':len(failures),'skipped':skipped,'slowest_elements':sorted(timings,key=lambda x:x['seconds'],reverse=True)[:10],'ifcopenshell_version':ifcopenshell.version,'self_intersections_checked':False,'tessellation_linear_deflection_m':settings.get('mesher-linear-deflection'),'tessellation_angular_deflection_rad':settings.get('mesher-angular-deflection')})
    roofs=[m.name for m in meshes if m.import_diagnostics['classification']=='roof']
    # Width/depth are UI metadata only for IFC mode; no synthetic box is added.
    return Project(name=metadata.filename,geometry_source='ifc',ifc_metadata=metadata,meshes=meshes,method='rolling_sphere',objective='manual',candidate_surfaces=roofs,width=min(200,max(.1,float(upper[0]-lower[0]))),depth=min(200,max(.1,float(upper[1]-lower[1]))),roof_height=min(300,max(0,float(upper[2]))),ground_z=float(lower[2]))
