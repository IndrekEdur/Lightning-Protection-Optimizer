from fastapi import FastAPI, HTTPException
from .models import Project
from .optimization import solve

app=FastAPI(title='Lightning Protection Optimizer')

@app.get('/api/health')
def health():
    return {'status':'ok'}

@app.post('/api/optimize')
def optimize(project: Project):
    try:
        result=solve(project)
        from .reports import token
        result['report_token']=token(project,result)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc

@app.post("/api/project/validate")
def validate_project(project: Project):
    return project

class InspectionRequest(Project):
    center: tuple[float, float, float]

@app.post('/api/sphere/inspect')
def inspect_sphere(request: InspectionRequest):
    from .rolling_sphere import Scene
    try:
        return Scene(request, request.rods).inspect(request.center)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

from pydantic import BaseModel
from fastapi.responses import Response

class ExportRequest(BaseModel):
    project: Project
    result: dict

@app.post('/api/report/{format}')
def export_report(format: str, request: ExportRequest):
    from .reports import check_token, xlsx, pdf
    if format not in ('xlsx','pdf'):
        raise HTTPException(status_code=404,detail='Supported formats: xlsx, pdf')
    try:
        check_token(request.project,request.result)
        data=(xlsx if format=='xlsx' else pdf)(request.project,request.result)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc
    mime='application/pdf' if format=='pdf' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    return Response(data,media_type=mime,headers={'Content-Disposition':f'attachment; filename="lightning-protection-report.{format}"'})


from fastapi import UploadFile, File, Form

@app.post('/api/ifc/import')
def upload_ifc(file: UploadFile = File(...), height_min_m: float | None = Form(None), height_max_m: float | None = Form(None)):
    from .ifc_import import import_ifc, MAX_FILE_BYTES
    from pathlib import Path
    import tempfile
    import os
    if not file.filename or Path(file.filename).suffix.lower()!='.ifc':
        file.file.close()
        raise HTTPException(status_code=422,detail='Select an uncompressed IFC STEP (.ifc) file')
    import math
    if any(v is not None and not math.isfinite(v) for v in (height_min_m,height_max_m)) or (height_min_m is not None and height_max_m is not None and height_min_m>height_max_m):
        file.file.close()
        raise HTTPException(status_code=422,detail='Enter finite heights with minimum not greater than maximum')
    path=None
    try:
        with tempfile.NamedTemporaryFile(suffix='.ifc',delete=False) as target:
            path=target.name;size=0
            while chunk:=file.file.read(1024*1024):
                size+=len(chunk)
                if size>MAX_FILE_BYTES:raise HTTPException(status_code=413,detail=f'IFC upload exceeds {MAX_FILE_BYTES//(1024*1024)} MiB; configure LPO_IFC_MAX_UPLOAD_MIB or use a subset')
                target.write(chunk)
        return import_ifc(path,filename=file.filename,height_min_m=height_min_m,height_max_m=height_max_m)
    except ValueError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc
    finally:
        if path is not None:os.unlink(path)
        file.file.close()

class MountingRequest(Project):
    surface: str | None = None

@app.post('/api/rod/mountings')
def rod_mountings(request: MountingRequest):
    from .mounting import mounting_positions
    from .rolling_sphere import Scene
    try:
        project=request.model_copy(update={'candidate_surfaces':[request.surface]}) if request.surface else request
        positions=mounting_positions(project,Scene(project,[]))
        if not positions:raise ValueError('No permitted mountings on the selected surfaces')
        if len(positions)>5000:raise ValueError('More than 5000 mountings; increase candidate spacing')
        return {'positions':positions,'units':'m'}
    except ValueError as exc:raise HTTPException(status_code=422,detail=str(exc)) from exc
