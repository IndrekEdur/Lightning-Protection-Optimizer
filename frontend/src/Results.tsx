export type Patch={object:string;vertices:number[][];status:string;kind:string};
export function SurfacePatches({patches,onObject,origin=[0,0,0]}:{origin?:number[];patches:Patch[];onObject:(name:string)=>void}){
 return <>{patches.filter(p=>p.kind==='face_interior'&&p.vertices.length===3).map((p,i)=><mesh key={i} onClick={e=>{e.stopPropagation();onObject(p.object)}}><bufferGeometry><bufferAttribute attach="attributes-position" args={[new Float32Array(p.vertices.flatMap(([x,y,z])=>[x-origin[0],z-origin[2]+.035,y-origin[1]])),3]}/></bufferGeometry><meshBasicMaterial color={p.status==='protected'?'#4ccea4':p.status==='unprotected'?'#f04c69':'#efbd64'} transparent opacity={.42} side={2} depthWrite={false}/></mesh>)}</>
}
export function Comparison({results,load}:{results:Record<string,{total_cost:number;verification_status?:string;rods:unknown[]}>;load:(key:string)=>void}){
 return <><h3>Compare configurations</h3>{Object.keys(results).length===0?<p>Run cost, count or manual calculation to save a comparison for the current model and prices.</p>:<table><thead><tr><th>Objective</th><th>Rods</th><th>Cost</th><th>Status</th></tr></thead><tbody>{Object.entries(results).map(([key,r])=><tr key={key}><td><button onClick={()=>load(key)}>{key}</button></td><td>{r.rods.length}</td><td>{r.total_cost.toFixed(2)}</td><td>{r.verification_status||'demo'}</td></tr>)}</tbody></table>}</>
}
