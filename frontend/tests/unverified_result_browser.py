"""Presentation regression; mocked API checks messaging, not engineering maths."""
from pathlib import Path
import json,sys,shutil
from playwright.sync_api import sync_playwright,expect
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/'backend'))
from lpo.models import Project
project=Project(method='rolling_sphere').model_dump()
result={'rods':[],'counts':{'A':0,'B':0},'total_cost':760,'solver_status':'verification_limit','mip_gap':0,'engineering_verified':False,'geometry_verified':False,'verification_status':'unprotected','protected_samples':0,'unprotected_samples':1,'undetermined_samples':0,'samples':[],'checks':[],'verification':{'points':[],'patches':[],'verified_surface_area_m2':0}}
with sync_playwright() as tool:
 browser=tool.chromium.launch(executable_path=shutil.which('chromium') or tool.chromium.executable_path,headless=True,args=['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
 page=browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script('localStorage.setItem("lpo",'+json.dumps(json.dumps(project))+');')
 page.route('**/api/optimize',lambda route:route.fulfill(json=result))
 page.route('**/api/sphere/inspect',lambda route:route.fulfill(json={'radius':45,'clearance':-2,'admissible':False,'escape_verified':False,'contacts':[{'object':'Ventilation 1','point':[10,10,12],'relation':'penetration'}]}))
 page.goto('http://127.0.0.1:5173')
 page.get_by_role('button',name='Run optimization',exact=True).click()
 expect(page.get_by_role('alert')).to_contain_text('No verified protection solution found')
 expect(page.get_by_text('Unverified candidate cost · project currency',exact=True)).to_be_visible()
 page.get_by_role('button',name='Inspect sphere contacts',exact=True).click()
 expect(page.get_by_text('Inspection sphere intersects geometry.',exact=False)).to_be_visible()
 assert not errors,errors
 browser.close();print('Unverified candidate cost/status and inadmissible inspection-sphere warning: PASS')
