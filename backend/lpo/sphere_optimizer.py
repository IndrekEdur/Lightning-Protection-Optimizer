"""Necessary witness cuts + sufficient continuous surface certification.
Keeps the cheapest certified incumbent; no continuous-placement optimum claim.
"""
import time
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import csc_matrix
from .models import Rod
from .mounting import mounting_positions
from .rolling_sphere import Scene, verify_scene, rods_segments
from .sphere_collision import segment_distances
from .surface_certificate import certificate
from .calculation import SPHERE_RADII


def verify_complete(p,rods,seconds=12,depth=7):
    try:
        scene=Scene(p,rods)
        result=certificate(scene,seconds=seconds,max_depth=depth)
    except ValueError as exc:
        return {'status':'invalid_model','error':str(exc),'points':[],'patches':[],'surface_certified':False}
    # Independent scalar target/direction evaluation, not MILP cut matrices or
    # the certificate's support-function calculations. Certificate is primary;
    # any contradicting contact invalidates it conservatively.
    if result['status']=='protected':
        independent=verify_scene(p,rods,refine=2,depth=min(3,p.sphere_refinement+1))
        result['independent_check']={k:v for k,v in independent.items() if k not in ('points',)}
        contacts=[pt for pt in independent['points'] if pt['status']=='unprotected']
        if contacts or independent['status']=='invalid_model':
            result['status']='unprotected' if contacts else 'invalid_model';result['surface_certified']=False
            result['points'].extend(contacts)
    return result


def cost(p,rods):return sum(p.catalogue[r.type_index].price for r in rods) if p.objective!='count' else len(rods)


def solve_sphere(p, _refined=False):
    start=time.perf_counter();iterations=0;gap=None;best=None;best_verification=None
    rods=p.rods if p.objective=='manual' else []
    status='manual';notes=[];cuts=[];lower_bound=None
    try:Scene(p,rods)
    except ValueError as exc:return package(p,rods,{'status':'invalid_model','error':str(exc),'points':[],'patches':[],'surface_certified':False},'invalid_model',start,0,None)
    if p.objective=='manual':
        verification=verify_complete(p,rods,seconds=30,depth=8)
        return package(p,rods,verification,status,start,0,None)
    positions=mounting_positions(p,Scene(p,[]));k=len(p.catalogue)
    if not len(positions):raise ValueError('No permitted candidate positions')
    if len(positions)*k>1500:raise ValueError('At most 1500 candidate/type combinations; increase spacing')
    options=[]
    for x,y,z in positions:
        for t in range(k):
            rod=Rod(x=float(x),y=float(y),base_z=float(z),type_index=t)
            try:Scene(p,[rod])
            except ValueError:continue
            options.append(rod)
    if not options:raise ValueError('No feasible rod mountings on candidate grid')
    a,b=rods_segments(p,options);n=len(options)
    keys=list(dict.fromkeys((r.x,r.y,r.base_z) for r in options));mapping={key:i for i,key in enumerate(keys)}
    groups=[mapping[(r.x,r.y,r.base_z)] for r in options]
    exclusive=csc_matrix((np.ones(n),(groups,np.arange(n))),shape=(len(keys),n))
    costs=np.array([p.catalogue[r.type_index].price if p.objective=='cost' else 1 for r in options],float)
    # Establish a safe incumbent first. Longest segments dominate shorter rods
    # with the same base; this is a feasibility seed, never called optimal.
    seed=[]
    for key in keys:
        seed.append(max((r for r in options if (r.x,r.y,r.base_z)==key),key=lambda r:p.catalogue[r.type_index].height))
    proposals=[seed]
    xs=sorted(set(r.x for r in options));ys=sorted(set(r.y for r in options))
    for sx in range(1,min(8,len(xs))+1):
        for sy in range(1,min(8,len(ys))+1):
            chosen_x=set(xs[::sx]+xs[-1:]);chosen_y=set(ys[::sy]+ys[-1:])
            for t in range(k):
                subset=[r for r in options if r.type_index==t and r.x in chosen_x and r.y in chosen_y]
                if subset:proposals.append(subset)
    proposals.sort(key=lambda rs:cost(p,rs))
    seen=set()
    for proposed in proposals:
        if time.perf_counter()-start>12:break
        key=tuple((r.x,r.y,r.base_z,r.type_index) for r in proposed)
        if key in seen:continue
        seen.add(key)
        initial=certificate(Scene(p,proposed),seconds=1,max_depth=7,max_nodes=10000)
        if initial['surface_certified']:
            best=proposed;best_verification=initial;break
    if best is None:
        initial=verify_complete(p,seed,seconds=5)
        if initial['surface_certified']:best=seed;best_verification=initial
    if best is None:notes.append('Even the densest longest-rod seed was not certified; candidate refinement may be required.')
    verification=verify_complete(p,rods,seconds=5,depth=6)
    for iterations in range(1,17):
        if time.perf_counter()-start>55:status='time_limit';break
        witnesses=[pt['witness']['center'] for pt in verification.get('counterexamples',verification['points']) if pt.get('witness')]
        if verification['status']=='protected':
            if best is None or cost(p,rods)<cost(p,best):best=rods;best_verification=verification
            status='certified_candidate_solution';break
        if not witnesses:
            status='verification_limit';break
        blocking=segment_distances(witnesses,a,b)<SPHERE_RADII[p.lps]-p.sphere_tolerance-1e-9
        if not blocking.any(axis=1).all():
            status='candidate_grid_infeasible';notes.append('At least one contact center cannot be intercepted on this grid.');break
        cuts.extend(blocking.astype(float))
        # Necessary sphere interception constraints; full-system proof follows.
        result=milp(costs,integrality=np.ones(n),bounds=Bounds(0,1),constraints=[LinearConstraint(csc_matrix(np.array(cuts)),1,np.inf),LinearConstraint(exclusive,0,1)],options={'time_limit':3,'mip_rel_gap':0.0})
        gap=float(result.mip_gap) if getattr(result,'mip_gap',None) is not None else None
        bound=getattr(result,'mip_dual_bound',None)
        if bound is not None:lower_bound=float(bound)
        if result.x is None:status='candidate_grid_infeasible' if result.status==2 else 'solver_limit';break
        rods=[options[i] for i,v in enumerate(result.x) if v>.5]
        verification=verify_complete(p,rods,seconds=8,depth=7)
        if verification['surface_certified']:
            if best is None or cost(p,rods)<cost(p,best):best=rods;best_verification=verification
            status='certified_candidate_solution';break
        status='cut_iteration_limit'
    # If cuts leave an unresolved candidate, keep the verified incumbent and
    # reduce it by deletion/downgrade while time remains. Every accepted change
    # receives a fresh continuous proof and independent point check.
    if best is not None and status!='certified_candidate_solution':
        ordered=sorted(list(best),key=lambda r:p.catalogue[r.type_index].price,reverse=True)
        for rod in ordered:
            if time.perf_counter()-start>55:break
            if rod not in best:continue
            trial=[r for r in best if r!=rod]
            check=verify_complete(p,trial,seconds=2,depth=6)
            if check['surface_certified']:best=trial;best_verification=check
    if best is not None:
        rods=best;verification=best_verification
    # Independent final geometry verification is mandatory; do not return a
    # cached incumbent as verified after any last change.
    verification=verify_complete(p,rods,seconds=20,depth=8)
    result=package(p,rods,verification,status,start,iterations,gap)
    result['objective_lower_bound_on_witness_model']=lower_bound
    result['candidate_count']=len(keys);result['checks'].extend(notes)
    if best is None and not _refined and p.spacing>1 and len(options)<350 and time.perf_counter()-start<40:
        finer=p.model_copy(update={'spacing':max(1,p.spacing/2)})
        refined=solve_sphere(finer,_refined=True)
        refined['candidate_refinement']={'original_spacing':p.spacing,'final_spacing':finer.spacing}
        refined['duration_seconds']=time.perf_counter()-start
        return refined
    return result


def package(p,rods,verification,status,start,iterations,gap):
    points=verification['points'];certified=verification.get('surface_certified',False)
    placement=[{**r.model_dump(),'base_z':p.roof_height if r.base_z is None else r.base_z,'height':p.catalogue[r.type_index].height,'price':p.catalogue[r.type_index].price} for r in rods]
    return {'rods':[r.model_dump() for r in rods],'rod_schedule':placement,'counts':{t.name:sum(r.type_index==i for r in rods) for i,t in enumerate(p.catalogue)},'total_cost':sum(p.catalogue[r.type_index].price for r in rods),
        'solver_status':status,'mip_gap':gap,'engineering_verified':False,'geometry_verified':certified,'verification_status':verification['status'],'verification':verification,
        'method':'rolling_sphere','lps':p.lps,'radius':SPHERE_RADII[p.lps],'duration_seconds':time.perf_counter()-start,'optimization_method':'witness-cut MILP + continuous surface certificate + independent point/direction check','cut_iterations':iterations,
        'best_verified_feasible':{'rods':placement,'total_cost':sum(p.catalogue[r.type_index].price for r in rods),'scope':'Static sphere-contact exclusion on the modeled required surfaces within stated tolerances'} if certified else None,
        'protected_samples':sum(pt['status']=='protected' for pt in points),'unprotected_samples':sum(pt['status']=='unprotected' for pt in points),'undetermined_samples':sum(pt['status']=='undetermined' for pt in points),'samples':[],
        'checks':['Protected means continuously verified modeled geometry, not edition-wide IEC/EN compliance.','Finite candidate grid and bounded search: best certified solution found; no continuous-placement global optimality.','Static sphere-center exclusion is conservative; trapped contact centers can leave a model undetermined.','Closed externally validated solid meshes in metres; zero-radius vertical rods; infinite horizontal ground.','Bonding, down conductors, separation distances, structural checks and standard-edition applicability require engineering review.']+([verification['error']] if 'error' in verification else [])}
