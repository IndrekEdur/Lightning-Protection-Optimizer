type MountingProject={geometry_source?:string;candidate_surfaces?:string[];equipment?:{name:string;role?:string}[];meshes?:{name:string;role?:string}[]};
export function cleanMountings<T extends MountingProject>(project:T):T{
 const names=new Set([...(project.geometry_source==='ifc'?[]:['Roof']),...(project.equipment||[]).filter(o=>o.role!=='excluded').map(o=>o.name),...(project.meshes||[]).filter(o=>o.role!=='excluded').map(o=>o.name)]);
 const candidates=project.candidate_surfaces??(project.geometry_source==='ifc'?[]:['Roof']);
 return {...project,candidate_surfaces:[...new Set(candidates.filter(name=>names.has(name)))]};
}
export function nextEquipmentName(objects:{name:string}[]):string{
 const names=new Set(objects.map(o=>o.name));let number=1;
 while(names.has('Ventilation '+number))number++;
 return 'Ventilation '+number;
}
export function apiError(detail:unknown):string{
 if(typeof detail==='string')return detail;
 if(Array.isArray(detail))return detail.map(item=>typeof item?.msg==='string'?item.msg:'Invalid project field').join('; ');
 return 'Calculation request failed. Check project settings and backend connection.';
}
