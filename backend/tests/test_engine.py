import itertools
import numpy as np
import pytest
from fastapi.testclient import TestClient
from lpo.api import app
from lpo.models import Project, RodType, Rod, Rect
from lpo.geometry import candidates, samples, roof_mesh
from lpo.calculation import coverage, verify
from lpo.optimization import solve


def test_analytic_cone_boundary():
    # At 45 degrees, radius equals height; exact boundary included.
    a=coverage(np.array([[3.,4.],[5.001,0.]]),np.array([[0.,0.]]),[5],45)
    assert a[:,0].tolist()==[True,False]
    assert verify([[3,4],[5.001,0]],[Rod(x=0,y=0,type_index=0)],[RodType(name='A',height=5,price=1)],45)==[True,False]


def test_grid_constraints_and_mesh():
    p=Project(width=10,depth=10,spacing=5,prohibited=[Rect(x=0,y=0,width=1,depth=1)])
    assert len(candidates(p))==8
    assert roof_mesh(p).bounds.tolist()==[[0,0,0],[10,10,10]]


def test_milp_matches_exhaustive_reference():
    p=Project(width=2,depth=2,spacing=2,sample_spacing=2,demo_angle_deg=45,catalogue=[RodType(name='A',height=2.5,price=3),RodType(name='B',height=5,price=8)])
    pos=candidates(p); pts=samples(p)
    best=float('inf')
    for choices in itertools.product([-1,0,1],repeat=4):
        rods=[Rod(x=pos[i,0],y=pos[i,1],type_index=t) for i,t in enumerate(choices) if t>=0]
        if all(verify(pts,rods,p.catalogue,p.demo_angle_deg)):
            best=min(best,sum(p.catalogue[r.type_index].price for r in rods))
    result=solve(p)
    assert result['total_cost']==best==6
    assert not result['engineering_verified']


def test_infeasible():
    result=solve(Project(width=20,depth=20,spacing=20,sample_spacing=5,demo_angle_deg=10))
    assert result['solver_status']=='infeasible'
    assert result['unprotected_samples']>0


def test_manual_refined_gaps():
    p=Project(width=10,depth=10,objective='manual',rods=[Rod(x=0,y=0,type_index=0)])
    r=solve(p)
    assert r['unprotected_samples']>0 and r['protected_samples']>0


@pytest.mark.parametrize('method',['protection_angle'])
def test_no_invented_normative_data(method):
    with pytest.raises(ValueError,match='unverified'):
        solve(Project(method=method))


def test_manual_outside_and_no_candidates():
    with pytest.raises(ValueError,match='outside'):
        solve(Project(objective='manual',rods=[Rod(x=-1,y=0,type_index=0)]))
    with pytest.raises(ValueError,match='No permitted'):
        solve(Project(permitted=[Rect(x=500,y=500,width=1,depth=1)]))


def test_api_and_validation():
    client=TestClient(app)
    assert client.get('/api/health').json()=={'status':'ok'}
    assert client.post('/api/optimize',json={'spacing':0}).status_code==422
    assert client.post('/api/optimize',json={'method':'protection_angle'}).status_code==422
    response=client.post('/api/optimize',json={'width':5,'depth':5,'spacing':5,'objective':'manual'})
    assert response.status_code==200
    assert response.json()['unprotected_samples']>0


def test_project_import_validation():
    client=TestClient(app)
    assert client.post('/api/project/validate',json={'width':30}).json()['depth']==40
    assert client.post('/api/project/validate',json={'catalogue':[]}).status_code==422
