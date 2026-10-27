"""Conservative adaptive 3D contact search. No-contact is NOT a surface certificate."""
import time
import numpy as np
import trimesh
from .calculation import SPHERE_RADII
from .geometry import roof_mesh, samples, allowed
from .sphere_collision import Collider, segment_distances, segment_crosses_mesh, ray_mesh_distance, ray_segment_distances


def sagitta(radius, separation):
    if radius<=0 or not 0<=separation<=2*radius: raise ValueError('Require R > 0 and 0 <= d <= 2R')
    return radius-np.sqrt(radius*radius-(separation/2)**2)


def rods_segments(p,rods):
    a=np.array([[r.x,r.y,p.roof_height if r.base_z is None else r.base_z] for r in rods],float).reshape(-1,3)
    b=a.copy()
    if len(a): b[:,2]+=[p.catalogue[r.type_index].height for r in rods]
    return a,b


def validated(mesh,name):
    if not len(mesh.faces) or not np.isfinite(mesh.vertices).all(): raise ValueError(f'{name}: missing/nonfinite geometry')
    if np.any(mesh.area_faces<1e-12): raise ValueError(f'{name}: degenerate triangles')
    if len(np.unique(np.sort(mesh.faces,axis=1),axis=0))!=len(mesh.faces): raise ValueError(f'{name}: duplicated faces')
    local=mesh.copy();local.apply_translation(-mesh.bounds.mean(axis=0))
    if not mesh.is_watertight or not mesh.is_winding_consistent or local.volume<=0:
        raise ValueError(f'{name}: closed, consistently outward oriented solid required; gaps/non-watertight mesh')
    return mesh

class VerificationLimitError(ValueError):
    pass

class Scene:
    def __init__(self,p,rods):
        build_start=time.perf_counter()
        self.p=p;self.radius=SPHERE_RADII[p.lps];self.tol=p.sphere_tolerance
        self.a,self.b=rods_segments(p,rods)
        if len(rods) and not allowed(self.a[:,:2],p).all(): raise ValueError('Rod outside permitted installation area')
        self.objects=[]
        if p.geometry_source=='ifc':
            if p.ifc_metadata is None:raise ValueError('IFC source metadata is missing')
            missing=[f['guid'] for f in p.ifc_metadata.failures if f['guid'] not in p.acknowledged_ifc_omissions]
            if missing:raise ValueError('IFC elements failed import; explicitly review/exclude omissions before calculation: '+', '.join(missing[:10]))
        else:
            if p.roof_height<=p.ground_z: raise ValueError('Roof elevation must exceed ground reference')
            self.objects.append(('Roof','protected',validated(roof_mesh(p),'Roof')))
        for obj in p.equipment:
            if obj.role=='excluded': continue
            m=trimesh.creation.box(extents=[obj.width,obj.depth,obj.height])
            m.apply_translation([obj.x+obj.width/2,obj.y+obj.depth/2,obj.z+obj.height/2])
            self.objects.append((obj.name,obj.role,validated(m,obj.name)))
        for obj in p.meshes:
            if obj.role=='excluded':continue
            v=np.asarray(obj.vertices,float); f=np.asarray(obj.faces,int)
            if not len(v) or not len(f) or np.min(f)<0 or np.max(f)>=len(v): raise ValueError(f'{obj.name}: missing vertices/faces or invalid indices')
            self.objects.append((obj.name,obj.role,validated(trimesh.Trimesh(v,f,process=False),obj.name)))
        if not self.objects:raise ValueError('No included building geometry')
        if not any(role=='protected' for _,role,_ in self.objects):raise ValueError('No surfaces selected for protection')
        if sum(len(m.faces) for _,_,m in self.objects)>30000: raise ValueError('Geometry limit: at most 30000 triangles')
        if any(np.finfo(float).eps*np.max(np.abs(m.vertices))>self.tol/100 for _,_,m in self.objects):raise ValueError('World coordinates exceed numerical precision for the requested tolerance')
        self.colliders=[Collider(m) for _,_,m in self.objects]
        self.max_z=max([float(m.bounds[1,2]) for _,_,m in self.objects]+[float(self.b[:,2].max()) if len(self.b) else p.ground_z])
        for a,b in zip(self.a,self.b):self.check_mounting(a,b)
        self.diagnostics={'scene_build_seconds':time.perf_counter()-build_start,'objects':len(self.objects),'triangles':sum(len(m.faces) for _,_,m in self.objects),'vertices':sum(len(m.vertices) for _,_,m in self.objects),'geometry_source':p.geometry_source,'coordinate_units':'m'}

    def check_mounting(self,a,b):
        if not allowed(np.array([a[:2]]),self.p)[0]:raise ValueError('Rod outside permitted installation area')
        attached=any(abs(collider.clearance(a,self.tol)[0]+self.tol)<=self.tol for collider in self.colliders)
        if not attached:raise ValueError('Rod base is not on an included mounting surface')
        for collider in self.colliders:
            if collider.inside(a+np.array([0,0,1e-5])) or collider.inside(b) or segment_crosses_mesh(a,b,collider.mesh):raise ValueError('Rod intersects model geometry; relocate rod')

    def inspect(self,center):
        c=np.asarray(center,float);R=self.radius
        contacts=[];clearance=float(c[2]-self.p.ground_z-R)
        if clearance<=self.tol:contacts.append({'object':'Ground','point':[float(c[0]),float(c[1]),self.p.ground_z],'clearance':clearance,'relation':'penetration' if clearance < -self.tol else 'tangent'})
        for (name,role,_),collider in zip(self.objects,self.colliders):
            gap,point=collider.clearance(c,R)
            clearance=min(clearance,gap)
            if gap<=self.tol: contacts.append({'object':name,'role':role,'point':point,'clearance':gap,'relation':'penetration' if gap < -self.tol else 'tangent'})
        d=segment_distances([c],self.a,self.b)[0]-R
        if len(d):
            clearance=min(clearance,float(d.min()))
            for i in np.where(d<=self.tol)[0]:
                v=self.b[i]-self.a[i];t=np.clip(np.dot(c-self.a[i],v)/np.dot(v,v),0,1)
                contacts.append({'object':f'Rod {i+1}','role':'air_terminal','point':(self.a[i]+t*v).tolist(),'clearance':float(d[i]),'relation':'penetration' if d[i] < -self.tol else 'tangent'})
        admissible=clearance>=-self.tol
        escape=admissible and bool(c[2]>=self.max_z-self.tol)
        if admissible and not escape:
            rod_gaps=ray_segment_distances(c,self.a,self.b)-R
            escape=bool((not len(rod_gaps) or np.min(rod_gaps)>=-self.tol) and all(ray_mesh_distance(c,m)>=R-self.tol for _,_,m in self.objects))
        return {'center':c.tolist(),'radius':R,'clearance':clearance,'admissible':admissible,'escape_verified':escape,'escape_method':'exact upward swept-sphere clearance','contacts':contacts}

    def targets(self,refine=1):
        result=[('Roof',np.array([x,y,self.p.roof_height])) for x,y in samples(self.p,refine)] if self.p.geometry_source=='parametric' else []
        for name,role,m in (self.objects[1:] if self.p.geometry_source=='parametric' else self.objects):
            if role!='protected':continue
            if len(m.faces)*(16 if refine>1 else 4)>3000:raise VerificationLimitError('Independent verification target limit: reduce protected geometry or use a model subset')
            # Deterministic subdivision samples all faces, including equipment sides.
            vertices,faces=m.vertices,m.faces
            for _ in range(2 if refine>1 else 1): vertices,faces=trimesh.remesh.subdivide(vertices,faces)
            pts=np.unique(np.round(np.vstack([vertices,vertices[faces].mean(axis=1)]),9),axis=0)
            result.extend((name,pt) for pt in pts if pt[2]>=self.p.ground_z)
        if len(result)>3000: raise VerificationLimitError('Verification limit: increase sample spacing or reduce geometry')
        return result

    def contact(self,q,depth=None):
        # A point strictly inside a planar solid face has exactly one locally
        # admissible tangent center, along the outward normal. This proves point
        # blockage without discretizing angular directions (not a surface proof).
        normal=None
        if self.p.geometry_source=='parametric' and abs(q[2]-self.p.roof_height)<1e-9 and 1e-8<q[0]<self.p.width-1e-8 and 1e-8<q[1]<self.p.depth-1e-8:
            normal=np.array([0.,0.,1.])
        else:
            for _,_,mesh in self.objects:
                close=trimesh.triangles.closest_point(mesh.triangles,np.repeat(q[None],len(mesh.faces),axis=0))
                ids=np.where(np.linalg.norm(close-q,axis=1)<1e-9)[0]
                for i in ids:
                    bary=trimesh.triangles.points_to_barycentric(mesh.triangles[i:i+1],q[None])[0]
                    if np.min(bary)>1e-8:
                        normal=mesh.face_normals[i];break
                if normal is not None:break
        if normal is not None:
            inspection=self.inspect(q+self.radius*normal)
            if not inspection['admissible']:
                return {'status':'protected','witness':None,'directions_tested':1,'proof':'Unique planar-face normal center blocked within tolerance'}
            return {'status':'unprotected' if inspection['escape_verified'] else 'undetermined','witness':inspection if inspection['escape_verified'] else None,'directions_tested':1}
        # Spherical icosahedron covers ALL directions, including side/below approaches.
        for u in np.vstack([np.eye(3),-np.eye(3)]):
            inspection=self.inspect(q+self.radius*u)
            if inspection['admissible'] and inspection['escape_verified']:
                return {'status':'unprotected','witness':inspection,'directions_tested':1}
        base=trimesh.creation.icosphere(subdivisions=0,radius=1)
        stack=[(base.vertices[f],0) for f in base.faces]
        uncertain=False;checked=0
        depth=self.p.sphere_refinement if depth is None else depth
        while stack:
            tri,level=stack.pop();u=tri.sum(axis=0);u/=np.linalg.norm(u)
            c=q+self.radius*u
            inspection=self.inspect(c);checked+=1
            if inspection['admissible'] and inspection['escape_verified']:
                return {'status':'unprotected','witness':inspection,'directions_tested':checked}
            # Signed clearance is 1-Lipschitz. Entire direction patch blocked if
            # center clearance + R*max-chord < -tolerance.
            bound=self.radius*np.sqrt(max(0,2-2*float(np.min(tri@u))))
            if inspection['clearance']+bound < -self.tol:continue
            if level>=depth:
                uncertain=True;continue
            a,b,d=tri;ab=a+b;ab/=np.linalg.norm(ab);bd=b+d;bd/=np.linalg.norm(bd);da=d+a;da/=np.linalg.norm(da)
            stack.extend((np.array(t),level+1) for t in [(a,ab,da),(ab,b,bd),(da,bd,d),(ab,bd,da)])
        return {'status':'undetermined' if uncertain else 'protected','witness':None,'directions_tested':checked}


def verify_scene(p,rods,refine=1,depth=None):
    start=time.perf_counter()
    try:
        scene=Scene(p,rods);targets=scene.targets(refine)
    except VerificationLimitError as e:
        return {'status':'undetermined','points':[],'duration_seconds':time.perf_counter()-start,'limit':str(e)}
    except ValueError as e:
        return {'status':'invalid_model','error':str(e),'points':[],'duration_seconds':time.perf_counter()-start}
    points=[]
    for name,q in targets:
        if time.perf_counter()-start>25:
            return {'status':'unprotected' if any(pt['status']=='unprotected' for pt in points) else 'undetermined','points':points,'duration_seconds':time.perf_counter()-start,'limit':'25 second verification limit; remaining targets not evaluated'}
        r=scene.contact(q,depth)
        points.append({'object':name,'point':q.tolist(),**r})
    # Even certified point statuses do not certify unsampled surface patches.
    status='unprotected' if any(r['status']=='unprotected' for r in points) else 'undetermined'
    return {'status':status,'points':points,'duration_seconds':time.perf_counter()-start,'radius':scene.radius,'tolerance':scene.tol,'angular_refinement':p.sphere_refinement if depth is None else depth,'surface_certified':False}
