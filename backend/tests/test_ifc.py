import hashlib
import numpy as np
import pytest
pytest.importorskip("ifcopenshell")
from fastapi.testclient import TestClient
from lpo.api import app
from lpo.ifc_import import import_ifc
from lpo.rolling_sphere import Scene
from lpo.mounting import mounting_positions
from lpo.sphere_optimizer import verify_complete
from ifc_fixtures import write_fixture


@pytest.mark.parametrize('schema',['IFC2X3','IFC4'])
@pytest.mark.parametrize('mm',[False,True])
def test_actual_ifcopenshell_units_world_placements_equipment(tmp_path,schema,mm):
    path=tmp_path/'reference.ifc';write_fixture(path,schema=schema,millimetres=mm)
    before=hashlib.sha256(path.read_bytes()).hexdigest()
    p=import_ifc(path)
    assert p.geometry_source=='ifc'
    assert p.ifc_metadata.source_sha256==before
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before
    assert p.ifc_metadata.length_unit_scale_to_m==(.001 if mm else 1)
    assert len(p.meshes)==2
    roof=next(m for m in p.meshes if m.ifc_class=='IfcSlab')
    v=np.array(roof.vertices)
    assert v.min(axis=0)==pytest.approx([700000,6500000,10])
    assert v.max(axis=0)==pytest.approx([700010,6500020,10.2])
    assert roof.ifc_guid and roof.ifc_name
    scene=Scene(p,[])
    assert len(scene.objects)==2 and not any(name=='Roof' for name,_,_ in scene.objects)
    mountings=mounting_positions(p,scene)
    assert mountings and all(x>=700000 and y>=6500000 for x,y,z in mountings)
    assert all(z==pytest.approx(10.2) for _,_,z in mountings)
    r=verify_complete(p,[],seconds=2,depth=3)
    assert r['status']=='unprotected'
    assert any(pt['object']==roof.name for pt in r['points'])


def test_sloped_ifc_not_flattened(tmp_path):
    path=tmp_path/'sloped.ifc';write_fixture(path,slope=.2,equipment=False)
    p=import_ifc(path);scene=Scene(p,[])
    assert np.ptp(np.array(p.meshes[0].vertices)[:,2])>3
    mounts=mounting_positions(p,scene)
    assert len(set(round(z,4) for _,_,z in mounts))>2
    r=verify_complete(p,[],seconds=2)
    assert not r['surface_certified']


def test_missing_units_and_corrupt_ifc_fail_clearly(tmp_path):
    path=tmp_path/'bad.ifc';f,_=write_fixture(path)
    f.by_type('IfcProject')[0].UnitsInContext=None;f.write(str(path))
    with pytest.raises(ValueError,match='explicit units'):import_ifc(path)
    path.write_text('this is not IFC')
    with pytest.raises(ValueError,match='Cannot parse IFC'):import_ifc(path)


def test_missing_element_not_silently_dropped(tmp_path):
    path=tmp_path/'missing.ifc';f,roof=write_fixture(path)
    roof.Representation=None;f.write(str(path))
    p=import_ifc(path)
    assert p.ifc_metadata.failures
    with pytest.raises(ValueError,match='failed import'):Scene(p,[])


def test_ifc_upload_endpoint_and_ignored_private_directory(tmp_path):
    path=tmp_path/'upload.ifc';write_fixture(path)
    client=TestClient(app)
    with path.open('rb') as stream:r=client.post('/api/ifc/import',files={'file':('building.ifc',stream,'application/octet-stream')})
    assert r.status_code==200,r.text
    data=r.json();assert data['ifc_metadata']['filename']=='building.ifc'
    assert client.post('/api/ifc/import',files={'file':('bad.txt',b'bad')}).status_code==422
    import subprocess
    assert subprocess.run(['git','check-ignore','test_models/private-project.json'],capture_output=True).returncode==0


def test_non_watertight_kept_for_viewer_but_calculation_rejected(tmp_path):
    path=tmp_path/'open.ifc';write_fixture(path)
    p=import_ifc(path)
    p.meshes[0].faces=p.meshes[0].faces[:-1]
    r=verify_complete(p,[],seconds=1)
    assert r['status']=='invalid_model'
    assert not r['surface_certified']


def test_imported_model_cannot_use_demo_angle(tmp_path):
    from lpo.optimization import solve
    path=tmp_path/'angle.ifc';write_fixture(path)
    p=import_ifc(path).model_copy(update={'method':'demo_angle'})
    with pytest.raises(ValueError,match='requires Rolling Sphere'):solve(p)


def test_map_conversion_retained_not_double_applied(tmp_path):
    path=tmp_path/'mapped.ifc';f,_=write_fixture(path,equipment=False)
    crs=f.create_entity('IfcProjectedCRS',Name='EPSG:3301')
    f.create_entity('IfcMapConversion',SourceCRS=f.by_type('IfcGeometricRepresentationContext')[0],TargetCRS=crs,Eastings=650000.,Northings=6000000.,OrthogonalHeight=100.,XAxisAbscissa=0.,XAxisOrdinate=1.,Scale=1.)
    f.write(str(path));p=import_ifc(path)
    assert p.ifc_metadata.map_conversions[0]['Eastings']==650000
    assert p.ifc_metadata.map_conversions[0]['TargetCRS']['Name']=='EPSG:3301'
    assert np.array(p.meshes[0].vertices).min(axis=0)==pytest.approx([700000,6500000,10])


def test_nested_rotated_placement(tmp_path):
    path=tmp_path/'rotation.ifc';f,roof=write_fixture(path,offset=(10,20,10),equipment=False)
    point=f.create_entity('IfcCartesianPoint',Coordinates=(100.,200.,0.))
    axis=f.create_entity('IfcAxis2Placement3D',Location=point,Axis=f.create_entity('IfcDirection',DirectionRatios=(0.,0.,1.)),RefDirection=f.create_entity('IfcDirection',DirectionRatios=(0.,1.,0.)))
    roof.ObjectPlacement.PlacementRelTo=f.create_entity('IfcLocalPlacement',RelativePlacement=axis)
    f.write(str(path));p=import_ifc(path)
    vertices=np.array(p.meshes[0].vertices)
    assert vertices.min(axis=0)==pytest.approx([60,210,10])
    assert vertices.max(axis=0)==pytest.approx([80,220,10.2])


def test_ifc_foot_conversion_not_scaled_twice(tmp_path):
    path=tmp_path/'feet.ifc';f,_=write_fixture(path,equipment=False,offset=(0,0,10))
    metre=f.by_type('IfcSIUnit')[0]
    dimensions=f.create_entity('IfcDimensionalExponents',LengthExponent=1,MassExponent=0,TimeExponent=0,ElectricCurrentExponent=0,ThermodynamicTemperatureExponent=0,AmountOfSubstanceExponent=0,LuminousIntensityExponent=0)
    factor=f.create_entity('IfcMeasureWithUnit',ValueComponent=f.create_entity('IfcLengthMeasure',.3048),UnitComponent=metre)
    foot=f.create_entity('IfcConversionBasedUnit',Dimensions=dimensions,UnitType='LENGTHUNIT',Name='FOOT',ConversionFactor=factor)
    f.by_type('IfcProject')[0].UnitsInContext.Units=[foot]
    f.write(str(path));p=import_ifc(path)
    assert p.ifc_metadata.length_unit_scale_to_m==pytest.approx(.3048)
    v=np.array(p.meshes[0].vertices)
    assert v.max(axis=0)==pytest.approx([3.048,6.096,10.2*.3048])


def test_certificate_budget_is_enforced_for_already_blocked_faces():
    from lpo.models import Project,Rod
    from lpo.surface_certificate import certificate
    p=Project(width=2,depth=2)
    result=certificate(Scene(p,[Rod(x=1,y=1,type_index=1)]),max_nodes=0)
    assert result['nodes']==0
    assert result['status']=='undetermined'


def test_review_and_ground_confirmation_gate_ifc_protection(tmp_path):
    from lpo.models import Rod
    path=tmp_path/'review.ifc';write_fixture(path,equipment=False)
    p=import_ifc(path).model_copy(update={'ground_z':0})
    rods=[Rod(x=x,y=y,base_z=10.2,type_index=1) for x in [700000,700010] for y in [6500000,6500020]]
    preliminary=verify_complete(p,rods,seconds=3)
    assert preliminary['status']=='undetermined'
    assert not preliminary['surface_certified']
    reviewed=p.model_copy(update={'reference_surface_confirmed':True,'ifc_review_confirmed':True})
    result=verify_complete(reviewed,rods,seconds=3)
    assert result['status']=='protected'
    assert result['surface_certified']


def test_aggregate_roof_children_classified_without_dummy_roof(tmp_path):
    import ifcopenshell.guid
    path=tmp_path/'assembly.ifc';f,slab=write_fixture(path,equipment=False)
    slab.PredefinedType='NOTDEFINED'
    roof=f.create_entity('IfcRoof',GlobalId=ifcopenshell.guid.new(),Name='Roof container',PredefinedType='FLAT_ROOF')
    f.create_entity('IfcRelAggregates',GlobalId=ifcopenshell.guid.new(),RelatingObject=roof,RelatedObjects=[slab])
    f.write(str(path));p=import_ifc(path)
    assert not p.ifc_metadata.failures
    assert len(p.meshes)==1 and p.meshes[0].role=='protected'
    assert len(Scene(p,[]).objects)==1
