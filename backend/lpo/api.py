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
