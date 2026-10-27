from pathlib import Path
import json,sys,shutil
from playwright.sync_api import sync_playwright,expect
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/'backend'))
from lpo.models import Project
project=Project().model_dump();project.update(method='rolling_sphere',candidate_surfaces=['Roof','Ventilation 1','Ventilation 2'],equipment=[{'name':'Ventilation 2','x':10,'y':10,'z':10,'width':3,'depth':3,'height':2,'role':'protected'}])
with sync_playwright() as tool:
 browser=tool.chromium.launch(executable_path=shutil.which('chromium') or tool.chromium.executable_path,headless=True,args=['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
 page=browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script('localStorage.setItem("lpo",'+json.dumps(json.dumps(project))+');')
 page.goto('http://127.0.0.1:5173')
 def saved():
  with page.expect_download() as download:page.get_by_role('button',name='Save project',exact=True).click()
  path=root/'test_models/equipment-mounting-browser.json';download.value.save_as(str(path));return json.loads(path.read_text())
 assert saved()['candidate_surfaces']==['Roof','Ventilation 2']
 details=page.locator('details').filter(has=page.locator('summary',has_text='Ventilation 2')).first
 details.locator('summary').click();details.locator('label').filter(has_text='Name').locator('input').fill('HVAC')
 assert saved()['candidate_surfaces']==['Roof','HVAC']
 page.get_by_role('button',name='Remove object',exact=True).click()
 assert saved()['candidate_surfaces']==['Roof']
 page.get_by_role('button',name='Add box / equipment',exact=True).click()
 page.get_by_role('button',name='Add box / equipment',exact=True).click()
 assert [o['name'] for o in saved()['equipment']]==['Ventilation 1','Ventilation 2']
 assert not errors,errors
 browser.close();print('Stale saved state, mounting rename/delete and unique new equipment browser regression: PASS')
