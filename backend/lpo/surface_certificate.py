"""Continuous closed-surface certificates using interval subdivision.

Smooth triangle interiors have a unique outward tangent-center normal. Physical
mesh edges and vertices are checked separately over the entire unit sphere.
Certificates exclude *all* static contact centers, so do not depend on sampled
exterior connectivity. No-contact samples are never used as a proof.
"""
import time
import numpy as np
import trimesh
from scipy.spatial import ConvexHull
from .sphere_collision import segment_distances


def split_triangle(v):
    a,b,c=v;ab=(a+b)/2;bc=(b+c)/2;ca=(c+a)/2
    return [np.array(t) for t in [(a,ab,ca),(ab,b,bc),(ca,bc,c),(ab,bc,ca)]]


def support(directions, vectors):
    """Max w.u over the spherical triangle's minor great-circle cone.

    A linear functional's maximum is at a vertex, on an edge's great circle,
    or at w/|w| in the interior. Enumerating all gives an exact support value.
    """
    tri=np.asarray(directions);w=np.asarray(vectors).reshape(-1,3)
    values=(w@tri.T).max(axis=1)
    if len(tri)==1:return values+1e-10*np.maximum(1,np.linalg.norm(w,axis=1))
    if len(tri)==2:
        a,b=tri;dot=float(a@b)
        if dot>1-1e-14:return values+1e-9
        wa=w@a;wb=w@b
        alpha=(wa-dot*wb)/(1-dot*dot);beta=(wb-dot*wa)/(1-dot*dot)
        projected=alpha[:,None]*a+beta[:,None]*b
        values=np.where((alpha>=-1e-12)&(beta>=-1e-12),np.maximum(values,np.linalg.norm(projected,axis=1)),values)
        return values+1e-10*np.maximum(1,np.linalg.norm(w,axis=1))
    norm=np.linalg.norm(w,axis=1)
    inv=np.linalg.inv(tri.T)
    coeff=w@inv.T
    interior=np.all(coeff>=-1e-12,axis=1)
    values=np.where(interior,norm,values)
    for i,j in [(0,1),(1,2),(2,0)]:
        a,b=tri[i],tri[j];dot=float(a@b)
        wa=w@a;wb=w@b
        alpha=(wa-dot*wb)/(1-dot*dot);beta=(wb-dot*wa)/(1-dot*dot)
        proj=alpha[:,None]*a+beta[:,None]*b
        valid=(alpha>=-1e-12)&(beta>=-1e-12)
        values=np.where(valid,np.maximum(values,np.linalg.norm(proj,axis=1)),values)
    # Round toward the conservative side (never underestimate a maximum).
    return values+1e-10*np.maximum(1,norm)


def tip_blocks(scene,qverts,utri):
    """Sufficient full product bound, not independent rod coverage circles."""
    if not len(scene.b):return False
    w=qverts[:,None,:]-scene.b[None,:,:]
    maxdot=support(utri,w.reshape(-1,3)).reshape(len(qverts),len(scene.b))
    maxdist2=scene.radius**2+np.sum(w*w,axis=2)+2*scene.radius*maxdot
    return bool(np.any(np.max(maxdist2,axis=0)<(scene.radius-scene.tol)**2-1e-8))


def certificate(scene, max_depth=7, max_nodes=80000, seconds=30):
    """Certify required triangle interiors, physical edges and vertices.

    `protected` proves that every target contact center penetrates an included
    solid, ground or air terminal by more than tolerance. It does not certify
    bonding/structural/electrical standard requirements.
    """
    start=time.perf_counter();nodes=0;patches=[];unresolved=[];witnesses=[];counterexamples=[]
    R=scene.radius;tol=scene.tol
    base=trimesh.creation.icosphere(subdivisions=0,radius=1)
    directions=[base.vertices[f] for f in base.faces]
    target_faces=[];features=[]
    def normal_domains(normals):
        normals=np.asarray(normals)
        _,ids=np.unique(np.round(normals,12),axis=0,return_index=True);normals=normals[ids]
        if len(normals)<=2:return [normals]
        axis=normals.sum(axis=0);length=np.linalg.norm(axis)
        if length<1e-12:return directions
        axis/=length
        dots=normals@axis
        if np.min(dots)<1e-8:return directions
        e=np.cross(axis,[1,0,0] if abs(axis[0])<.8 else [0,1,0]);e/=np.linalg.norm(e);f=np.cross(axis,e)
        xy=np.column_stack([normals@e,normals@f])/dots[:,None]
        try:order=ConvexHull(xy).vertices
        except Exception:return directions
        return [np.array([axis,normals[a],normals[b]]) for a,b in zip(order,np.roll(order,-1))]

    roof=scene.objects[0][2]
    # Respect protection rectangles by constructing the requested top plane.
    rects=scene.p.protected or [None]
    for rect in rects:
        x0=max(0,rect.x) if rect else 0;y0=max(0,rect.y) if rect else 0
        x1=min(scene.p.width,rect.x+rect.width) if rect else scene.p.width
        y1=min(scene.p.depth,rect.y+rect.depth) if rect else scene.p.depth
        if x1<=x0 or y1<=y0:continue
        z=scene.p.roof_height
        verts=np.array([[x0,y0,z],[x1,y0,z],[x1,y1,z],[x0,y1,z]])
        target_faces.extend(('Roof',verts[ids],np.array([0.,0.,1.])) for ids in [[0,1,2],[0,2,3]])
        # Artificial protection boundaries inside the roof are smooth, not
        # physical edges. Only real boundary portions require angular checks.
        for a,b in [(0,1),(1,2),(2,3),(3,0)]:
            v=verts[[a,b]]
            if (np.all(v[:,0]==0) or np.all(v[:,0]==scene.p.width) or np.all(v[:,1]==0) or np.all(v[:,1]==scene.p.depth)):
                if np.all(v[:,0]==0):side=[-1.,0.,0.]
                elif np.all(v[:,0]==scene.p.width):side=[1.,0.,0.]
                elif np.all(v[:,1]==0):side=[0.,-1.,0.]
                else:side=[0.,1.,0.]
                features.append(('Roof',v,[np.array([[0.,0.,1.],side])]))
        for v in verts:
            if v[0] in (0,scene.p.width) and v[1] in (0,scene.p.depth):features.append(('Roof',v[None],[np.array([[0.,0.,1.],[-1. if v[0]==0 else 1.,0.,0.],[0.,-1. if v[1]==0 else 1.,0.]])]))
    for name,role,m in scene.objects[1:]:
        if role!='protected':continue
        for face,normal in zip(m.triangles,m.face_normals):target_faces.append((name,face,normal))
        for pair,edge,convex in zip(m.face_adjacency,m.face_adjacency_edges,m.face_adjacency_convex):
            if np.dot(m.face_normals[pair[0]],m.face_normals[pair[1]])<1-1e-10:
                features.append((name,m.vertices[edge],[m.face_normals[pair]] if convex else directions))
        for vi,v in enumerate(m.vertices):
            incident=np.any(m.faces==vi,axis=1)
            adjacent=np.any(m.face_adjacency_edges==vi,axis=1)
            domain=normal_domains(m.face_normals[incident]) if np.all(m.face_adjacency_convex[adjacent]) else directions
            features.append((name,v[None],domain))
    if not target_faces:
        return {'status':'invalid_model','error':'No required protection surfaces','surface_certified':False,'patches':[],'points':[]}

    def limit():return nodes>=max_nodes or time.perf_counter()-start>seconds

    # Smooth face interior proof: convexity makes the maximum distance to a
    # rod segment occur at a triangle vertex. Multiple rods are resolved by
    # subdivision; other solids may also rigorously block centers.
    stack=[(name,tri,n,0) for name,tri,n in target_faces]
    while stack:
        name,tri,normal,level=stack.pop();nodes+=1
        centers=tri+R*normal
        d=segment_distances(centers,scene.a,scene.b)
        blocked=bool(len(scene.b) and np.any(d.max(axis=0)<R-tol-1e-9))
        qc=tri.mean(axis=0);center=qc+R*normal
        if not blocked:
            info=scene.inspect(center)
            bound=float(np.linalg.norm(tri-qc,axis=1).max())
            blocked=info['clearance']+bound<-tol-1e-9
        if blocked:
            patches.append({'object':name,'vertices':tri.tolist(),'status':'protected','kind':'face_interior'});continue
        info=scene.inspect(center)
        if info['admissible']:
            counterexamples.append({'object':name,'point':qc.tolist(),'status':'undetermined','witness':info})
        if info['admissible'] and info['escape_verified']:
            witnesses.append({'object':name,'point':qc.tolist(),'status':'unprotected','witness':info,'directions_tested':1})
            patches.append({'object':name,'vertices':tri.tolist(),'status':'unprotected','kind':'face_interior'})
            continue
        if info['admissible'] or level>=max_depth or limit():
            unresolved.append({'object':name,'vertices':tri.tolist(),'status':'undetermined','kind':'face_interior'})
            if limit():
                unresolved.extend({'object':n,'vertices':t.tolist(),'status':'undetermined','kind':'face_interior'} for n,t,_,_ in stack);stack=[]
            continue
        stack.extend((name,t,normal,level+1) for t in split_triangle(tri))

    # Features are verified over all sphere approaches, including approaches
    # below/sideways. Ground and all solids participate, not only rod tips.
    for index,(name,qverts,domains) in enumerate(features):
        if limit():
            unresolved.extend({'object':n,'vertices':q.tolist(),'status':'undetermined','kind':'edge_or_vertex'} for n,q,_ in features[index:]);break
        pending=[(qverts,u,0,0) for u in domains]
        feature_ok=True
        while pending:
            q,u,qd,ud=pending.pop();nodes+=1
            maxuz=float(support(u,[[0,0,1]])[0])
            if np.max(q[:,2])+R*maxuz < scene.p.ground_z+R-tol-1e-9:continue
            if tip_blocks(scene,q,u):continue
            qc=q.mean(axis=0);uc=u.sum(axis=0);uc/=np.linalg.norm(uc)
            qbound=float(np.linalg.norm(q-qc,axis=1).max())
            ubound=R*np.sqrt(max(0,2-2*float(np.min(u@uc))))
            info=scene.inspect(qc+R*uc)
            if info['clearance']+qbound+ubound < -tol-1e-9:continue
            if info['admissible']:
                counterexamples.append({'object':name,'point':qc.tolist(),'status':'undetermined','witness':info})
            if info['admissible'] and info['escape_verified']:
                witnesses.append({'object':name,'point':qc.tolist(),'status':'unprotected','witness':info,'directions_tested':1})
                feature_ok=False;break
            if info['admissible']:
                feature_ok=False;break
            if limit() or (ud>=max_depth and (qd>=max_depth or len(q)==1)):
                feature_ok=False;break
            if len(q)>1 and qbound>ubound and qd<max_depth:
                mid=(q[0]+q[1])/2
                pending.extend([(np.array([q[0],mid]),u,qd+1,ud),(np.array([mid,q[1]]),u,qd+1,ud)])
            elif ud<max_depth and len(u)==1:
                if len(q)>1 and qd<max_depth:
                    mid=(q[0]+q[1])/2
                    pending.extend([(np.array([q[0],mid]),u,qd+1,ud),(np.array([mid,q[1]]),u,qd+1,ud)])
                else:feature_ok=False;break
            elif ud<max_depth and len(u)==2:
                a,b=u;mid=a+b;mid/=np.linalg.norm(mid)
                pending.extend([(q,np.array([a,mid]),qd,ud+1),(q,np.array([mid,b]),qd,ud+1)])
            elif ud<max_depth:
                a,b,c=u;ab=a+b;ab/=np.linalg.norm(ab);bc=b+c;bc/=np.linalg.norm(bc);ca=c+a;ca/=np.linalg.norm(ca)
                pending.extend((q,np.array(t),qd,ud+1) for t in [(a,ab,ca),(ab,b,bc),(ca,bc,c),(ab,bc,ca)])
            else:
                mid=(q[0]+q[1])/2
                pending.extend([(np.array([q[0],mid]),u,qd+1,ud),(np.array([mid,q[1]]),u,qd+1,ud)])
        record={'object':name,'vertices':qverts.tolist(),'status':'protected' if feature_ok else 'undetermined','kind':'edge_or_vertex'}
        (patches if feature_ok else unresolved).append(record)
    status='unprotected' if witnesses else 'undetermined' if unresolved else 'protected'
    all_patches=patches+unresolved
    object_status={}
    for name in dict.fromkeys(n for n,_,_ in target_faces):
        object_status[name]='unprotected' if any(pt['object']==name for pt in witnesses) else 'undetermined' if any(pt['object']==name for pt in unresolved) else 'protected'
    area=sum(float(trimesh.triangles.area(np.array([p['vertices']]))[0]) for p in patches if p['kind']=='face_interior' and p['status']=='protected')
    return {'status':status,'object_status':object_status,'verified_surface_area_m2':area,'surface_certified':status=='protected','patches':all_patches,'points':witnesses,'counterexamples':counterexamples,'nodes':nodes,'duration_seconds':time.perf_counter()-start,'tolerance':tol,'max_depth':max_depth,'max_nodes':max_nodes,'unresolved_patches':len(unresolved),'proof':'Continuous triangle-interior bounds and full normal-cone direction bounds on physical edges/vertices; static exclusion implies inaccessibility.','limit_reached':limit()}
