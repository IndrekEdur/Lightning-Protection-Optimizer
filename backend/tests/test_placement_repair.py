"""Regression for the user's exact six-rod 760-cost roof/equipment project."""
from pathlib import Path
import pytest
from lpo.models import Project,Rod
from lpo.rolling_sphere import Scene,rods_segments
from lpo.mounting import mounting_positions
from lpo.sphere_optimizer import verify_complete,repair_configuration


def fixture_project():
    return Project.model_validate_json((Path(__file__).resolve().parents[2]/'examples/roof-equipment-regression.json').read_text())


def feasible_options(p):
    scene=Scene(p,[]);options=[]
    for x,y,z in mounting_positions(p,scene):
        for t in range(len(p.catalogue)):
            rod=Rod(x=x,y=y,base_z=z,type_index=t);a,b=rods_segments(p,[rod])
            try:scene.check_mounting(a[0],b[0])
            except ValueError:continue
            options.append(rod)
    return options


def test_exact_760_candidate_reproduces_roof_and_equipment_contacts():
    p=fixture_project();original=p.model_dump_json()
    assert sum(p.catalogue[r.type_index].price for r in p.rods)==760
    result=verify_complete(p,p.rods,seconds=5,depth=8)
    assert result['status']=='unprotected'
    assert {pt['object'] for pt in result['points']}=={'Roof','Ventilation 1'}
    assert p.model_dump_json()==original


def test_exact_760_repair_adds_or_upgrades_and_passes_full_verification():
    p=fixture_project();original=p.model_dump_json()
    rods,result,steps=repair_configuration(p,feasible_options(p),p.rods,seconds=40)
    assert steps and any(step['action']=='add' for step in steps)
    assert result['surface_certified'],result['status']
    assert result['status']=='protected'
    assert not result['points']
    assert result['object_status']=={'Roof':'protected','Ventilation 1':'protected'}
    assert result.get('independent_check')
    assert p.model_dump_json()==original
    assert len({(r.x,r.y,r.base_z) for r in rods})==len(rods)


def test_full_optimizer_repairs_supplied_candidate_and_retains_verified_result():
    from lpo.optimization import solve
    p=fixture_project()
    result=solve(p)
    assert result['geometry_verified']
    assert result['solution_status']=='verified_solution'
    assert result['best_verified_feasible'] is not None
    assert result['verification_status']=='protected'
    assert result['verification']['object_status']=={'Roof':'protected','Ventilation 1':'protected'}
    assert result['unprotected_samples']==0
    assert sum(result['placement_changes'].values())>0
    assert result['repair_steps']
