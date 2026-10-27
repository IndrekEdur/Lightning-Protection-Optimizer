import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import csc_matrix
from .models import Rod
from .geometry import candidates, samples, allowed
from .calculation import coverage, verify, require_method

def solve(p):
    if p.method == "rolling_sphere":
        from .sphere_optimizer import solve_sphere
        return solve_sphere(p)
    require_method(p)
    pts=samples(p)
    if len(pts)==0:
        raise ValueError('No protected samples: protection rectangles do not intersect roof')
    solver_status='manual'
    gap=None
    if p.objective=='manual':
        rods=p.rods
        if rods and not allowed(np.array([[r.x,r.y] for r in rods]),p).all():
            raise ValueError('Manual rod lies outside permitted installation area')
    else:
        pos=candidates(p)
        n=len(pos); k=len(p.catalogue)
        if len(pts)*n*k>8_000_000 or n*k>6000:
            raise ValueError('Grid too large; increase candidate or sample spacing')
        if not n:
            raise ValueError('No permitted candidate positions')
        positions=np.repeat(pos,k,axis=0)
        heights=np.tile([r.height for r in p.catalogue],n)
        a=coverage(pts,positions,heights,p.demo_angle_deg)
        costs=np.tile([r.price if p.objective=='cost' else 1 for r in p.catalogue],n)
        # At most one catalogue type at a position.
        exclusive=csc_matrix((np.ones(n*k),(np.repeat(np.arange(n),k),np.arange(n*k))),shape=(n,n*k))
        result=milp(costs,integrality=np.ones(n*k),bounds=Bounds(0,1),constraints=[LinearConstraint(csc_matrix(a.astype(float)),1,np.inf),LinearConstraint(exclusive,0,1)],options={'time_limit':15,'mip_rel_gap':0.0})
        solver_status={0:'optimal_on_candidate_grid',1:'solver_limit',2:'infeasible',3:'unbounded',4:'solver_error'}.get(result.status,'unknown')
        gap=float(result.mip_gap) if getattr(result,'mip_gap',None) is not None else None
        rods=[] if result.x is None else [Rod(x=float(positions[i,0]),y=float(positions[i,1]),type_index=i%k) for i,v in enumerate(result.x) if v>0.5]
    fine=samples(p,2)
    if len(fine)*max(len(rods),1)>10_000_000:
        raise ValueError('Verification too large; increase sample spacing')
    covered=verify(fine,rods,p.catalogue,p.demo_angle_deg)
    missing=len(fine)-sum(covered)
    return {'rods':[r.model_dump() for r in rods], 'counts':{t.name:sum(r.type_index==i for r in rods) for i,t in enumerate(p.catalogue)},'total_cost':sum(p.catalogue[r.type_index].price for r in rods),'solver_status':solver_status,'mip_gap':gap,'engineering_verified':False,'protected_samples':sum(covered),'unprotected_samples':missing,'samples':[[float(x),float(y),bool(ok)] for (x,y),ok in zip(fine,covered)],'checks':['Synthetic constant-angle geometry; not IEC/EN compliance.','Finite grid only; no continuous-placement optimality.','Independent scalar check at half sample spacing; unsampled gaps may remain.']+(['Refined verification found unprotected points.'] if missing else [])}
