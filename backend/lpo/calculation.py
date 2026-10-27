"""Synthetic cone geometry ONLY. Verified IEC angle tables are not distributed.
Rolling sphere radii are metadata, never substituted for protection-angle data.
"""
import numpy as np
from .geometry import TOL

SPHERE_RADII={'I':20,'II':30,'III':45,'IV':60}

def require_method(p):
    if p.method != 'demo_angle':
        raise ValueError(f'{p.method} is unverified/unavailable for {p.edition}. Select synthetic demo geometry to explore optimization.')

def coverage(points, positions, heights, angle):
    radii=np.asarray(heights)*np.tan(np.deg2rad(angle))
    return np.linalg.norm(points[:,None,:]-positions[None,:,:],axis=2) <= radii[None,:]+TOL

def verify(points, rods, catalogue, angle):
    # Independent scalar evaluation; does not reuse candidate coverage matrix.
    from math import hypot, tan, radians
    return [any(hypot(float(x)-r.x,float(y)-r.y) <= catalogue[r.type_index].height*tan(radians(angle))+TOL for r in rods) for x,y in points]
