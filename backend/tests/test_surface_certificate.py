"""Independent analytical references and continuous-domain regression cases."""
import numpy as np
import pytest
import trimesh
from lpo.models import Project,Rod,Equipment,MeshObject
from lpo.rolling_sphere import Scene
from lpo.surface_certificate import certificate,support
from lpo.sphere_optimizer import verify_complete
from lpo.mounting import mounting_positions
from lpo.sphere_collision import ray_segment_distances,ray_mesh_distance


def dense(p,height=1):
    return [Rod(x=float(x),y=float(y),type_index=height) for x in np.linspace(0,p.width,5) for y in np.linspace(0,p.depth,5)]


@pytest.mark.parametrize('lps',['I','II','III','IV'])
def test_closed_roof_continuous_certificate(lps):
    p=Project(width=10,depth=10,lps=lps,method='rolling_sphere')
    result=certificate(Scene(p,dense(p)))
    assert result['status']=='protected'
    assert result['surface_certified']
    assert result['verified_surface_area_m2']==pytest.approx(100)
    assert result['object_status']['Roof']=='protected'
    assert any(patch['kind']=='edge_or_vertex' for patch in result['patches'])


def test_exposed_roof_has_real_witness_not_just_sampling_failure():
    p=Project(width=30,depth=40)
    rods=[Rod(x=x,y=y,type_index=1) for x,y in [(0,0),(30,0),(0,40),(30,40)]]
    result=certificate(Scene(p,rods))
    assert result['status']=='unprotected'
    assert not result['surface_certified']
    assert result['points']
    for point in result['points']:
        witness=point['witness'];q=np.array(point['point']);c=np.array(witness['center'])
        assert np.linalg.norm(c-q)==pytest.approx(45)
        assert witness['clearance']>=-p.sphere_tolerance
        assert witness['escape_verified']


def test_four_rods_can_collectively_protect_continuous_roof():
    p=Project(width=20,depth=20)
    rods=[Rod(x=x,y=y,type_index=0) for x,y in [(0,0),(20,0),(0,20),(20,20)]]
    result=certificate(Scene(p,rods),max_depth=9)
    assert result['surface_certified']
    # No individual rod alone covers the normal-center domain of all corners.
    for rod in rods:
        assert certificate(Scene(p,[rod]),seconds=1)['status']!='protected'


def test_no_certificate_from_zero_budget():
    p=Project(width=10,depth=10)
    result=certificate(Scene(p,dense(p)),max_nodes=0)
    assert not result['surface_certified']
    assert result['status']=='undetermined'
    assert result['unresolved_patches']>0


def test_protection_rectangles_area_and_artificial_edges():
    from lpo.models import Rect
    p=Project(width=30,depth=40,protected=[Rect(x=5,y=5,width=2,depth=3)])
    r=certificate(Scene(p,[Rod(x=6,y=6,type_index=1)]))
    assert r['surface_certified']
    assert r['verified_surface_area_m2']==pytest.approx(6)
    assert not any(v['kind']=='edge_or_vertex' for v in r['patches'])


def test_exact_spherical_support_dominates_independent_random_search():
    rng=np.random.default_rng(725)
    sphere=trimesh.creation.icosphere(subdivisions=1)
    for face in sphere.faces[::8]:
        tri=sphere.vertices[face]
        weights=rng.dirichlet([1,1,1],size=1000)
        u=weights@tri;u/=np.linalg.norm(u,axis=1)[:,None]
        w=rng.normal(size=(15,3))
        maximum=support(tri,w)
        assert np.all(maximum>=(w@u.T).max(axis=1)-1e-10)
        assert np.all(maximum<=np.linalg.norm(w,axis=1)+1e-8)


def test_ray_segment_independent_cases():
    c=[0,0,0]
    result=ray_segment_distances(c,np.array([[3,0,-5],[0,0,5],[3,0,-5]]),np.array([[3,0,5],[0,0,7],[4,0,-5]]))
    assert result.tolist()==pytest.approx([3,0,np.sqrt(34)])


def test_ray_mesh_clearance_and_blocked_escape():
    box=trimesh.creation.box(extents=[2,2,2]);box.apply_translation([0,0,10])
    assert ray_mesh_distance([0,0,0],box)==0
    assert ray_mesh_distance([4,0,0],box)==pytest.approx(3)
    assert ray_mesh_distance([4,0,12],box)==pytest.approx(np.sqrt(10))
    p=Project(width=10,depth=10,equipment=[Equipment(name='Tall neighbour',x=100,y=100,z=0,width=10,depth=10,height=80,role='obstacle')])
    # Below the tallest included object, but away from it: exact swept clearance can prove
    # escape without requiring the center to start above the global scene top.
    scene=Scene(p,[Rod(x=10,y=0,type_index=1)])
    c=[-np.sqrt(45**2-35**2),10,45]
    r=scene.inspect(c)
    assert r['admissible']
    assert r['escape_verified']


def test_mounting_on_sloped_mesh_and_high_equipment():
    m=trimesh.creation.box(extents=[4,4,2]);m.apply_transform(trimesh.transformations.rotation_matrix(.1,[1,0,0]));m.apply_translation([10,10,20])
    obj=MeshObject(name='Slope',vertices=m.vertices.tolist(),faces=m.faces.tolist())
    p=Project(width=20,depth=20,meshes=[obj],candidate_surfaces=['Slope'])
    positions=mounting_positions(p,Scene(p,[]))
    assert positions and all(z>20 for _,_,z in positions)
    for x,y,z in positions:
        Scene(p,[Rod(x=x,y=y,base_z=z,type_index=0)])


def test_no_floating_rod_or_buried_base():
    p=Project(width=10,depth=10)
    with pytest.raises(ValueError,match='mounting surface'):
        Scene(p,[Rod(x=5,y=5,base_z=15,type_index=0)])
    with pytest.raises(ValueError):
        Scene(p,[Rod(x=5,y=5,base_z=5,type_index=0)])


def test_ventilation_remains_exposed_while_roof_is_protected():
    p=Project(width=10,depth=10,equipment=[Equipment(name='Vent',x=4,y=4,z=10,width=2,depth=2,height=8)])
    rods=[r for r in dense(p) if not (4<=r.x<=6 and 4<=r.y<=6)]
    r=certificate(Scene(p,rods),seconds=5)
    assert r['status']=='unprotected'
    assert r['object_status']['Vent']=='unprotected'


def test_independent_contact_invalidates_object_patches_and_feeds_optimizer(monkeypatch):
    import lpo.sphere_optimizer as engine
    p=Project(width=2,depth=2)
    witness={'object':'Roof','point':[0,0,10],'status':'unprotected','witness':{'center':[0,0,55],'admissible':True},'directions_tested':1}
    proof={'status':'protected','surface_certified':True,'object_status':{'Roof':'protected'},'verified_surface_area_m2':2.,'patches':[{'object':'Roof','vertices':[[0,0,10],[2,0,10],[0,2,10]],'status':'protected','kind':'face_interior'}],'points':[],'counterexamples':[]}
    monkeypatch.setattr(engine,'certificate',lambda *a,**kw:proof)
    monkeypatch.setattr(engine,'verify_scene',lambda *a,**kw:{'status':'unprotected','points':[witness]})
    result=engine.verify_complete(p,[])
    assert result['status']=='unprotected' and not result['surface_certified']
    assert result['object_status']['Roof']=='unprotected'
    assert result['patches'][0]['status']=='undetermined'
    assert result['verified_surface_area_m2']==0
    assert result['counterexamples']==[witness]


def test_inspection_penetration_is_not_tangency():
    p=Project(width=30,depth=40,equipment=[Equipment()])
    result=Scene(p,[]).inspect([15,20,55])
    assert not result['admissible']
    assert any(c['object']=='Ventilation' and c['relation']=='penetration' for c in result['contacts'])
    assert any(c['object']=='Roof' and c['relation']=='tangent' for c in result['contacts'])
