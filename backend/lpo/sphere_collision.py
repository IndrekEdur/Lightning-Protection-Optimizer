"""Exact triangle/segment distances, bounding-sphere KD broad phase. Coordinates xyz, z up."""
import numpy as np
import trimesh
from scipy.spatial import cKDTree


def segment_distances(centers, starts, ends):
    c=np.asarray(centers,float).reshape(-1,3)
    a=np.asarray(starts,float).reshape(-1,3); b=np.asarray(ends,float).reshape(-1,3)
    if not len(a): return np.empty((len(c),0))
    v=b-a
    t=np.clip(np.sum((c[:,None]-a)*v,axis=2)/np.maximum(np.sum(v*v,axis=1),1e-30),0,1)
    return np.linalg.norm(c[:,None]-a-t[:,:,None]*v,axis=2)

class Collider:
    def __init__(self, mesh):
        self.mesh=mesh
        self.triangles=np.asarray(mesh.triangles)
        self.centroids=self.triangles.mean(axis=1)
        self.radii=np.linalg.norm(self.triangles-self.centroids[:,None],axis=2).max(axis=1)
        self.tree=cKDTree(self.centroids)
        self.max_radius=float(self.radii.max())
        self.bounds=mesh.bounds

    def inside(self,c):
        if np.any(c<=self.bounds[0]) or np.any(c>=self.bounds[1]): return False
        # Generalized winding number; no optional rtree dependency.
        a,b,d=np.moveaxis(self.triangles-c,1,0)
        la=np.linalg.norm(a,axis=1);lb=np.linalg.norm(b,axis=1);ld=np.linalg.norm(d,axis=1)
        numerator=np.einsum('ij,ij->i',a,np.cross(b,d))
        denominator=la*lb*ld+np.einsum('ij,ij->i',a,b)*ld+np.einsum('ij,ij->i',b,d)*la+np.einsum('ij,ij->i',d,a)*lb
        return abs(np.sum(2*np.arctan2(numerator,denominator)))>2*np.pi

    def clearance(self,center,radius):
        c=np.asarray(center,float)
        inside=self.inside(c)
        ids=list(range(len(self.triangles))) if inside else self.tree.query_ball_point(c,radius+self.max_radius+1e-6)
        if not ids: return 1e6,None
        ids=np.asarray(ids)
        if not inside: ids=ids[np.linalg.norm(self.centroids[ids]-c,axis=1)-self.radii[ids]<=radius+1e-6]
        if not len(ids): return 1e6,None
        closest=trimesh.triangles.closest_point(self.triangles[ids],np.repeat(c[None],len(ids),axis=0))
        distances=np.linalg.norm(closest-c,axis=1)
        i=int(np.argmin(distances));distance=float(distances[i])
        if inside: distance=-distance
        return distance-radius,closest[i].tolist()


def segment_crosses_mesh(a,b,mesh,tolerance=1e-8):
    """Moller-Trumbore segment/triangle intersections, including end contacts."""
    tri=np.asarray(mesh.triangles);direction=np.asarray(b)-a
    e1=tri[:,1]-tri[:,0];e2=tri[:,2]-tri[:,0]
    h=np.cross(np.broadcast_to(direction,e2.shape),e2);det=np.einsum('ij,ij->i',e1,h)
    valid=np.abs(det)>1e-12
    inv=np.divide(1.,det,out=np.zeros_like(det),where=valid)
    delta=np.asarray(a)-tri[:,0];u=inv*np.einsum('ij,ij->i',delta,h)
    q=np.cross(delta,e1);v=inv*(q@direction);t=inv*np.einsum('ij,ij->i',e2,q)
    return bool(np.any(valid&(u>=-tolerance)&(v>=-tolerance)&(u+v<=1+tolerance)&(t>tolerance)&(t<=1+tolerance)))


def ray_segment_distances(origin, starts, ends):
    """Exact distance from upward vertical ray to finite segments (vectorized)."""
    c=np.asarray(origin);a=np.asarray(starts);v=np.asarray(ends)-a
    if not len(a):return np.empty(0)
    w=c-a
    horizontal=np.sum(v[:,:2]**2,axis=1)
    full=np.sum(v*v,axis=1)
    sxy=np.divide(np.sum(w[:,:2]*v[:,:2],axis=1),horizontal,out=np.zeros(len(a)),where=horizontal>1e-24)
    sfull=np.divide(np.sum(w*v,axis=1),full,out=np.zeros(len(a)),where=full>1e-24)
    sz=np.divide(w[:,2],v[:,2],out=np.zeros(len(a)),where=np.abs(v[:,2])>1e-24)
    s=np.clip(np.stack([sxy,sfull,sz,np.zeros(len(a)),np.ones(len(a))],axis=1),0,1)
    p=a[:,None,:]+s[:,:,None]*v[:,None,:]
    closest=np.broadcast_to(c,p.shape).copy();closest[:,:,2]=np.maximum(p[:,:,2],c[2])
    return np.linalg.norm(p-closest,axis=2).min(axis=1)


def ray_mesh_distance(origin, mesh):
    """Exact upward ray/triangle distance, including interior plane crossings."""
    c=np.asarray(origin,float);tri=np.asarray(mesh.triangles)
    closest=trimesh.triangles.closest_point(tri,np.repeat(c[None],len(tri),axis=0))
    distance=float(np.linalg.norm(closest-c,axis=1).min())
    starts=tri.reshape(-1,3);ends=np.roll(tri,-1,axis=1).reshape(-1,3)
    distance=min(distance,float(ray_segment_distances(c,starts,ends).min()))
    normals=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);nz=normals[:,2]
    t=np.divide(np.einsum('ij,ij->i',normals,tri[:,0]-c),nz,out=np.full(len(tri),-1.),where=np.abs(nz)>1e-16)
    ids=np.where(t>=0)[0]
    if len(ids):
        pts=np.repeat(c[None],len(ids),axis=0);pts[:,2]+=t[ids]
        bary=trimesh.triangles.points_to_barycentric(tri[ids],pts)
        if np.any(np.all(bary>=-1e-12,axis=1)):return 0.
    return distance
