import numpy as np
import pytest
import trimesh
from fastapi.testclient import TestClient
from lpo.api import app
from lpo.models import Project, Rod, Equipment, MeshObject
from lpo.rolling_sphere import Scene, sagitta, verify_scene
from lpo.sphere_collision import Collider, segment_distances
from lpo.optimization import solve


def project(**kwargs):
    return Project(method='rolling_sphere',width=20,depth=20,sample_spacing=10,sphere_refinement=0,objective='manual',**kwargs)


def test_A_single_rod_reference_cross_section():
    p=project(rods=[Rod(x=0,y=0,type_index=0)])
    r=45;h=2.5;x=np.sqrt(2*r*h-h*h)
    result=Scene(p,p.rods).inspect([x,0,55])
    assert result['admissible']
    assert {c['object'] for c in result['contacts']}=={'Roof','Rod 1'}
    assert abs(result['clearance'])<1e-9
    assert not Scene(p,p.rods).inspect([x-.1,0,55])['admissible']


def test_B_two_rod_sagitta_and_actual_tangencies():
    penetration=sagitta(45,20)
    assert penetration==pytest.approx(1.125178063,abs=1e-9)
    p=project(rods=[Rod(x=0,y=10,type_index=0),Rod(x=20,y=10,type_index=0)])
    center=[10,10,12.5+np.sqrt(45**2-10**2)]
    result=Scene(p,p.rods).inspect(center)
    assert result['admissible']
    assert center[2]-45-p.roof_height==pytest.approx(1.374821937)
    assert {c['object'] for c in result['contacts']}=={'Rod 1','Rod 2'}
    # A 2D rod-to-rod cross section does not certify the 3D roof.
    exterior=[10,-np.sqrt(45**2-35**2),45]
    assert Scene(p,p.rods).inspect(exterior)['admissible']
    assert Scene(p,p.rods).inspect(exterior)['escape_verified']


def test_C_four_rods_complete_configuration():
    p=project(rods=[Rod(x=x,y=y,type_index=0) for x,y in [(0,0),(20,0),(0,20),(20,20)]])
    scene=Scene(p,p.rods)
    assert not scene.inspect([10,10,55])['admissible']
    # Test oblique directions as well as the upward axis. Full contact search
    # remains conservative when its angular budget cannot prove blockage.
    r=scene.contact(np.array([0.,0.,10.]))
    assert r['directions_tested']>=20
    assert r['status'] in ('undetermined','protected','unprotected')
    assert verify_scene(p,p.rods)['status']!='protected'


def test_D_equipment_contact_is_not_approved_interception():
    p=project(equipment=[Equipment(name='Vent',x=8,y=8,z=10,width=4,depth=4,height=5)],rods=[Rod(x=0,y=0,type_index=0),Rod(x=20,y=20,type_index=0)])
    result=Scene(p,p.rods).inspect([10,10,60])
    assert result['admissible']
    assert any(c['object']=='Vent' and c['role']=='protected' for c in result['contacts'])
    assert Scene(p,p.rods).contact(np.array([10.,10.,15.]))['status']=='unprotected'


def test_E_exterior_edge_approach_and_ground():
    p=project(rods=[Rod(x=10,y=10,type_index=0)])
    center=[-np.sqrt(45**2-35**2),0,45]
    r=Scene(p,p.rods).inspect(center)
    assert r['admissible'] and r['escape_verified']
    assert {c['object'] for c in r['contacts']}=={'Roof','Ground'}
    assert not Scene(p,p.rods).inspect([center[0],0,44])['admissible']


def test_F_height_changes_interception():
    p=project()
    center=[18,0,55]
    low=Scene(p,[Rod(x=0,y=0,type_index=0)]).inspect(center)
    high=Scene(p,[Rod(x=0,y=0,type_index=1)]).inspect(center)
    assert low['admissible'] and not high['admissible']


def mesh_input(mesh):
    return MeshObject(name='Model',vertices=mesh.vertices.tolist(),faces=mesh.faces.tolist())


@pytest.mark.parametrize('issue',['open','gap','duplicate','degenerate','missing'])
def test_G_invalid_geometry(issue):
    m=trimesh.creation.box()
    if issue in ('open','gap'): m.update_faces(np.arange(len(m.faces)-1))
    if issue=='duplicate':m.faces=np.vstack([m.faces,m.faces[0]])
    if issue=='degenerate':m.faces=np.vstack([m.faces,[0,0,0]])
    obj=mesh_input(m)
    if issue=='missing':obj.faces=[]
    result=verify_scene(project(meshes=[obj]),[])
    assert result['status']=='invalid_model'
    assert result['error']


def test_G_wrong_units_rejected():
    with pytest.raises(ValueError):Project(units='mm')


def test_deep_inside_solid_collision_and_segment():
    m=trimesh.creation.box(extents=[200,200,200])
    assert Collider(m).clearance([0,0,0],1)[0]<0
    assert segment_distances([[1,0,5]],[[0,0,0]],[[0,0,10]])[0,0]==1


@pytest.mark.parametrize('lps,R',[('I',20),('II',30),('III',45),('IV',60)])
def test_class_radius_api(lps,R):
    client=TestClient(app)
    response=client.post('/api/sphere/inspect',json={'method':'rolling_sphere','lps':lps,'center':[15,20,10+R]})
    assert response.status_code==200
    assert response.json()['radius']==R
    assert response.json()['admissible']


def test_manual_results_and_candidate_search():
    p=Project(method='rolling_sphere',width=2,depth=2,sample_spacing=2,spacing=2,sphere_refinement=0)
    result=solve(p)
    assert result['method']=='rolling_sphere'
    assert not result['engineering_verified']
    assert result['best_verified_feasible'] is not None
    assert result['verification_status']=='protected'
    assert result['geometry_verified']
    assert result['rods']
    assert result['cut_iterations']>=1


def test_reference_domain():
    with pytest.raises(ValueError): sagitta(45,91)
    assert sagitta(45,0)==0
    assert sagitta(45,90)==45


def test_rod_crossing_equipment_rejected_and_custom_base():
    from lpo.sphere_collision import segment_crosses_mesh
    m=trimesh.creation.box(extents=[2,2,2])
    assert segment_crosses_mesh(np.array([0,0,-3]),np.array([0,0,3]),m)
    p=project(equipment=[Equipment(x=0,y=0,z=11,width=3,depth=3,height=1)])
    assert verify_scene(p,[Rod(x=1,y=1,type_index=1)])['status']=='invalid_model'
    s=Scene(project(equipment=[Equipment(x=4,y=4,z=10,width=2,depth=2,height=5)]),[Rod(x=5,y=5,base_z=15,type_index=0)])
    assert s.b[0,2]==17.5


def test_sloped_mesh_and_roles():
    m=trimesh.creation.box(extents=[4,4,2])
    m.apply_transform(trimesh.transformations.rotation_matrix(.15,[0,1,0]))
    m.apply_translation([10,10,20])
    obj=mesh_input(m)
    scene=Scene(project(meshes=[obj]),[])
    assert scene.objects[-1][1]=='protected'
    q=m.triangles_center[np.argmax(m.face_normals[:,2])]
    assert scene.contact(q)['status']=='unprotected'
    obj.role='excluded'
    assert len(Scene(project(meshes=[obj]),[]).objects)==1
