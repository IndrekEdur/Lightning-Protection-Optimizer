"""Metre-based flat roof geometry. No normative lightning claims."""
import numpy as np
import trimesh
from .models import Project

TOL = 1e-8

def in_rect(points, rect):
    return ((points[:,0] >= rect.x-TOL) & (points[:,0] <= rect.x+rect.width+TOL) &
            (points[:,1] >= rect.y-TOL) & (points[:,1] <= rect.y+rect.depth+TOL))

def grid(width, depth, spacing):
    x = np.linspace(0,width,int(np.ceil(width/spacing))+1)
    y = np.linspace(0,depth,int(np.ceil(depth/spacing))+1)
    return np.array(np.meshgrid(x,y)).reshape(2,-1).T

def allowed(points, p):
    if p.geometry_source=='ifc':
        mask=np.ones(len(points),dtype=bool)
    else:
        mask = ((points[:,0]>=0)&(points[:,0]<=p.width)&(points[:,1]>=0)&(points[:,1]<=p.depth))
    if p.permitted:
        mask &= np.logical_or.reduce([in_rect(points,r) for r in p.permitted])
    for r in p.prohibited:
        mask &= ~in_rect(points,r)
    return mask

def candidates(p):
    pts=grid(p.width,p.depth,p.spacing)
    return pts[allowed(pts,p)]

def samples(p, refinement=1):
    pts=grid(p.width,p.depth,p.sample_spacing/refinement)
    if p.protected:
        pts=pts[np.logical_or.reduce([in_rect(pts,r) for r in p.protected])]
    return pts

def roof_mesh(p: Project):
    mesh=trimesh.creation.box(extents=[p.width,p.depth,max(p.roof_height,0.1)])
    mesh.apply_translation([p.width/2,p.depth/2,p.roof_height/2])
    return mesh
