import {useState,useEffect,useRef} from 'react';
import {useThree} from '@react-three/fiber';
import type {MeshObject} from './Sphere';
export type IfcMetadata={height_min_m?:number|null;height_max_m?:number|null;filename:string;schema_name:string;length_unit_scale_to_m:number;bounds_m:number[][];source_sha256:string;warnings:string[];failures:{guid:string;source_guid?:string;filename?:string;error:string}[];diagnostics:{import_seconds:number;elements_loaded:number;triangles:number;elements_failed:number;elements_filtered_by_height?:number;skipped:unknown[]}};
export type IfcSource=IfcMetadata&{source_id:string};
export function IfcCamera({metadata}:{metadata?:IfcMetadata|null}){
 const {camera}=useThree();
 useEffect(()=>{if(!metadata)return;const size=Math.max(20,...metadata.bounds_m[1].map((v,i)=>v-metadata.bounds_m[0][i]));camera.position.set(size*1.3,size,size*1.3);camera.far=size*15+1000;camera.lookAt(0,0,0);camera.updateProjectionMatrix()},[metadata,camera]);return null;
}
async function readJson(response:Response){
 if(!response.headers.get('content-type')?.includes('application/json'))throw Error('IFC backend did not return JSON. Check that the Python server is running on port 8000.');
 const body=await response.json();if(!response.ok)throw Error(typeof body.detail==='string'?body.detail:JSON.stringify(body.detail));return body;
}
export function IfcPanel({project,metadata,sources,meshes,acknowledged,onImport,onRole,onOmission}:{project:unknown;metadata?:IfcMetadata|null;sources:IfcSource[];meshes:MeshObject[];acknowledged:string[];onImport:(p:unknown)=>void;onRole:(name:string,role:string)=>void;onOmission:(guid:string,on:boolean)=>void}){
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[filter,setFilter]=useState(''),[heightMin,setHeightMin]=useState(''),[heightMax,setHeightMax]=useState(''),[files,setFiles]=useState<File[]>([]),[replaceId,setReplaceId]=useState(''),[progress,setProgress]=useState('');
 const current=useRef(project);current.current=project;
 async function upload(selected:File[]){
  setBusy(true);setError('');const starting=project;let working=project;let filename='';
  try{
   if((heightMin!==''&&!Number.isFinite(Number(heightMin)))||(heightMax!==''&&!Number.isFinite(Number(heightMax)))||(heightMin!==''&&heightMax!==''&&Number(heightMin)>Number(heightMax)))throw Error('Minimum height must not exceed maximum; enter finite metres');
   if(replaceId&&selected.length!==1)throw Error('Replace one source at a time; select one IFC file');
   for(let i=0;i<selected.length;i++){
    const file=selected[i];filename=file.name;setProgress(`Importing ${i+1}/${selected.length}: ${file.name}`);
    const data=new FormData();data.append('file',file);if(heightMin!=='')data.append('height_min_m',heightMin);if(heightMax!=='')data.append('height_max_m',heightMax);
    const incoming=await readJson(await fetch('/api/ifc/import',{method:'POST',body:data}));
    working=await readJson(await fetch('/api/ifc/merge',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project:working,incoming,replace_source_id:replaceId||null})}));
   }
   if(current.current!==starting)throw Error('Project changed during import. Retry to avoid overwriting newer changes');
   onImport(working);setReplaceId('');
  }catch(e){setError((filename?filename+': ':'')+String(e))}finally{setBusy(false);setProgress('')}
 }
 async function remove(source:IfcSource){
  setBusy(true);setError('');const starting=project;
  try{
   const updated=await readJson(await fetch('/api/ifc/remove',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project,source_id:source.source_id})}));
   if(current.current!==starting)throw Error('Project changed during source removal; retry');
   onImport(updated);if(replaceId===source.source_id)setReplaceId('');
  }catch(e){setError(String(e))}finally{setBusy(false)}
 }
 return <>
  <h3>IFC building models</h3>
  <label>Import operation<select disabled={busy} value={replaceId} onChange={e=>setReplaceId(e.target.value)}><option value="">Add model(s) to project</option>{sources.map(s=><option key={s.source_id} value={s.source_id}>Replace: {s.filename}</option>)}</select></label>
  <label>Minimum import height · m<input type="number" step="any" placeholder="No lower limit" value={heightMin} disabled={busy} onChange={e=>setHeightMin(e.target.value)}/></label>
  <label>Maximum import height · m<input type="number" step="any" placeholder="No upper limit" value={heightMax} disabled={busy} onChange={e=>setHeightMax(e.target.value)}/></label>
  <p>Absolute IFC world Z in metres, before map conversion. Empty = unlimited. Elements touching the range are kept whole; geometry is not cut. Current bounds apply to each newly selected file.</p>
  <label>Import IFC2x3 / IFC4<input type="file" multiple accept=".ifc,.IFC" disabled={busy} onChange={e=>{const selected=Array.from(e.target.files||[]);if(selected.length){setFiles(selected);void upload(selected)}}}/></label>
  <button disabled={busy||!files.length} onClick={()=>void upload(files)}>Import selected file{files.length>1?'s':''} with height range</button>
  {busy&&<p role="status">{progress||'Updating IFC project…'}</p>}
  {error&&<p role="alert" className="error">{error}{metadata&&<><br/>Import failed. The previous model remains loaded: {metadata.filename}</>}</p>}
  {sources.length>0&&<><h3>Loaded IFC files ({sources.length})</h3><p>Models share their original IFC placement coordinates in metres. Check their alignment. Adding/removing/replacing resets engineering review; existing rods stay for recalculation.</p>{sources.map(source=><details key={source.source_id}>
   <summary>{source.filename}</summary>
   <p>{source.schema_name} · source → metre × {source.length_unit_scale_to_m}<br/>Loaded range: {source.height_min_m??'−∞'} … {source.height_max_m??'+∞'} m<br/>{source.diagnostics.elements_loaded} elements · {source.diagnostics.triangles} triangles<br/>Source ID: {source.source_id}</p>
   <button disabled={busy} onClick={()=>{setReplaceId(source.source_id);setHeightMin(source.height_min_m?.toString()||'');setHeightMax(source.height_max_m?.toString()||'')}}>Replace / change height range</button>
   <button disabled={busy} onClick={()=>void remove(source)}>Remove IFC file</button>
  </details>)}</>}
  {metadata&&<>
   <p>{metadata.filename} · {metadata.schema_name}<br/>{sources.length<=1?<>Source unit → metre: × {metadata.length_unit_scale_to_m}<br/>Loaded range: {metadata.height_min_m??'−∞'} … {metadata.height_max_m??'+∞'} m<br/></>:<>Federated SI geometry; see each file for original units and height range<br/></>}{metadata.diagnostics.elements_filtered_by_height??0} elements outside range<br/>{metadata.diagnostics.elements_loaded} elements · {metadata.diagnostics.triangles} triangles<br/>Import: {metadata.diagnostics.import_seconds.toFixed(2)} s</p>
   <details><summary>Import assumptions and errors</summary>{metadata.warnings.map(w=><p key={w}>{w}</p>)}{metadata.failures.map(f=><label key={f.guid}><input type="checkbox" style={{width:'auto',display:'inline'}} checked={acknowledged.includes(f.guid)} onChange={e=>onOmission(f.guid,e.target.checked)}/> Explicitly exclude failed element {f.filename} {f.source_guid||f.guid}: {f.error}</label>)}</details>
   <label>Find IFC element<input value={filter} onChange={e=>setFilter(e.target.value)}/></label>
   <details open><summary>Review element classifications</summary>{meshes.filter(m=>(m.name+' '+m.ifc_name+' '+sources.find(s=>s.source_id===m.ifc_source_id)?.filename).toLowerCase().includes(filter.toLowerCase())).map(m=><label key={m.name}>{m.ifc_name||m.name}<small style={{display:'block'}}>{sources.find(s=>s.source_id===m.ifc_source_id)?.filename}<br/>{m.ifc_class} · {m.ifc_guid}</small><select value={m.role} onChange={e=>onRole(m.name,e.target.value)}>{['protected','obstacle','air_terminal','excluded'].map(r=><option key={r}>{r}</option>)}</select>{(m.import_diagnostics?.geometry_errors?.length??0)>0&&<p className="error">{m.import_diagnostics?.geometry_errors.join(', ')}</p>}</label>)}</details>
   <p>IFC geometry stays in this browser session. Save project JSON inside test_models/ if needed. Confirm ground elevation and all classifications before calculation.</p>
  </>}
 </>
}
