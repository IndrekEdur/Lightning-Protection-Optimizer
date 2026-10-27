"""Candidate mountings on selected upward-facing roof/equipment mesh surfaces."""
import numpy as np
from .geometry import candidates,grid,allowed
from .models import Rod


def mounting_positions(p,scene):
    positions=[]
    if 'Roof' in p.candidate_surfaces:
        positions.extend((float(x),float(y),p.roof_height) for x,y in candidates(p))
    for name,_,mesh in scene.objects[1:]:
        if name not in p.candidate_surfaces:continue
        lo,hi=mesh.bounds
        xy=grid(max(hi[0]-lo[0],1e-8),max(hi[1]-lo[1],1e-8),p.spacing)+lo[:2]
        xy=np.vstack([xy,mesh.vertices[:,:2]])
        xy=xy[allowed(xy,p)]
        for tri,normal in zip(mesh.triangles,mesh.face_normals):
            if normal[2]<p.min_mount_normal_z:continue
            matrix=np.column_stack([tri[1,:2]-tri[0,:2],tri[2,:2]-tri[0,:2]])
            if abs(np.linalg.det(matrix))<1e-12:continue
            uv=np.linalg.solve(matrix,(xy-tri[0,:2]).T).T
            mask=(uv[:,0]>=-1e-9)&(uv[:,1]>=-1e-9)&(uv.sum(axis=1)<=1+1e-9)
            for point,coeff in zip(xy[mask],uv[mask]):
                z=float(tri[0,2]+coeff[0]*(tri[1,2]-tri[0,2])+coeff[1]*(tri[2,2]-tri[0,2]))
                positions.append((float(point[0]),float(point[1]),z))
    return list(dict.fromkeys(tuple(round(v,9) for v in pos) for pos in positions))
