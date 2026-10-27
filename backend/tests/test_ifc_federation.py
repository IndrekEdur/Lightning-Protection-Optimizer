"""Federation tests use real IfcOpenShell parsing of synthetic, not client, files."""
import pytest
pytest.importorskip('ifcopenshell')
from fastapi.testclient import TestClient
from lpo.api import app
from lpo.models import Project,Rod
from lpo.ifc_import import import_ifc
from lpo.ifc_federation import merge,remove
from lpo.rolling_sphere import Scene
from ifc_fixtures import write_fixture


def imported(tmp_path,name,mm=False,offset=(700000,6500000,10),equipment=False):
    path=tmp_path/name;write_fixture(path,millimetres=mm,offset=offset,equipment=equipment)
    return import_ifc(path)


def test_two_disciplines_units_coordinates_and_persistence(tmp_path):
    arch=imported(tmp_path,'architecture.ifc')
    mep=imported(tmp_path,'ventilation.ifc',mm=True,offset=(700003,6500004,12))
    arch=arch.model_copy(update={'ground_z':0,'ifc_review_confirmed':True,'reference_surface_confirmed':True,'rods':[Rod(x=700000,y=6500000,base_z=10.2,type_index=1)]})
    arch.catalogue[0].price=123
    result=merge(arch,mep)
    assert len(result.ifc_sources)==2 and len(result.meshes)==2
    assert [s.length_unit_scale_to_m for s in result.ifc_sources]==[1,.001]
    assert result.ground_z==0 and result.catalogue[0].price==123 and len(result.rods)==1
    assert not result.ifc_review_confirmed and not result.reference_surface_confirmed
    assert min(v[0] for v in result.meshes[1].vertices)==pytest.approx(700003)
    assert result.ifc_metadata.bounds_m[1][2]==pytest.approx(12.2)
    assert len(Scene(result,result.rods).objects)==2
    restored=Project.model_validate_json(result.model_dump_json())
    assert restored==result


def test_same_guid_in_different_sources_does_not_collide(tmp_path):
    first=tmp_path/'arch.ifc';second=tmp_path/'mep.ifc'
    f,roof=write_fixture(first,equipment=False)
    # Same bytes/GUID, different discipline filename: both identities retained.
    f.write(str(second))
    result=merge(import_ifc(first),import_ifc(second))
    assert result.meshes[0].ifc_guid==result.meshes[1].ifc_guid
    assert result.meshes[0].name!=result.meshes[1].name
    assert result.meshes[0].ifc_source_id!=result.meshes[1].ifc_source_id
    assert any('Repeated IFC GUIDs' in warning for warning in result.ifc_metadata.warnings)


def test_replace_only_one_source_and_reject_accidental_duplicate(tmp_path):
    path=tmp_path/'architecture.ifc';write_fixture(path,equipment=True)
    arch=import_ifc(path,height_max_m=10.1)
    other=imported(tmp_path,'other.ifc',offset=(700020,6500000,10))
    p=merge(arch,other);before=p.model_dump_json()
    with pytest.raises(ValueError,match='already loaded'):merge(p,arch)
    assert p.model_dump_json()==before
    incoming=import_ifc(path,height_min_m=11,height_max_m=12)
    replaced=merge(p,incoming,replace_source_id=arch.ifc_sources[0].source_id)
    assert len(replaced.ifc_sources)==2
    assert any(m.ifc_class=='IfcBuildingElementProxy' for m in replaced.meshes)
    assert any(s.filename=='other.ifc' for s in replaced.ifc_sources)
    assert next(s for s in replaced.ifc_sources if s.filename=='architecture.ifc').height_min_m==11
    assert len(replaced.candidate_surfaces)==1


def test_remove_and_empty_project_are_safe(tmp_path):
    arch=imported(tmp_path,'arch.ifc');mep=imported(tmp_path,'mep.ifc')
    p=merge(arch,mep);remaining=remove(p,mep.ifc_sources[0].source_id)
    assert len(remaining.ifc_sources)==1 and len(remaining.meshes)==1
    assert remaining.ifc_metadata.filename=='arch.ifc'
    assert set(remaining.candidate_surfaces)=={remaining.meshes[0].name}
    empty=remove(remaining,remaining.ifc_sources[0].source_id)
    assert empty.ifc_metadata is None and not empty.meshes
    with pytest.raises(ValueError,match='metadata is missing'):Scene(empty,[])
    assert len(merge(empty,mep).ifc_sources)==1


def test_failed_elements_are_scoped_to_their_source(tmp_path):
    first=tmp_path/'arch.ifc';second=tmp_path/'mep.ifc'
    f,roof=write_fixture(first,equipment=True);roof.Representation=None;f.write(str(first));f.write(str(second))
    p=merge(import_ifc(first),import_ifc(second))
    failures=p.ifc_metadata.failures
    assert len(failures)==2 and failures[0]['source_guid']==failures[1]['source_guid']
    assert failures[0]['guid']!=failures[1]['guid']
    with pytest.raises(ValueError,match='failed import'):Scene(p,[])
    p.acknowledged_ifc_omissions=[failures[0]['guid']]
    with pytest.raises(ValueError,match='failed import'):Scene(p,[])
    p.acknowledged_ifc_omissions.append(failures[1]['guid'])
    assert len(Scene(p,[]).objects)==2


def test_legacy_single_file_project_can_be_extended(tmp_path):
    p=imported(tmp_path,'legacy.ifc');new=imported(tmp_path,'new.ifc')
    names={m.name:m.name.split(' / ',1)[1] for m in p.meshes}
    legacy=p.model_copy(update={'ifc_sources':[],'meshes':[m.model_copy(update={'name':names[m.name],'ifc_source_id':None}) for m in p.meshes],'candidate_surfaces':[names[n] for n in p.candidate_surfaces]})
    assert len(merge(legacy,new).ifc_sources)==2


def test_api_merge_remove_and_first_import_preserves_catalogue(tmp_path):
    client=TestClient(app);incoming=imported(tmp_path,'arch.ifc')
    existing=Project();existing.catalogue[1].price=777
    response=client.post('/api/ifc/merge',json={'project':existing.model_dump(),'incoming':incoming.model_dump()})
    assert response.status_code==200,response.text
    p=response.json();assert p['catalogue'][1]['price']==777
    sid=p['ifc_sources'][0]['source_id']
    assert client.post('/api/ifc/remove',json={'project':p,'source_id':'missing'}).status_code==422
    response=client.post('/api/ifc/remove',json={'project':p,'source_id':sid})
    assert response.status_code==200 and response.json()['meshes']==[]
