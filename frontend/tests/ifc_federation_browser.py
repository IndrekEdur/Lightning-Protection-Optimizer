"""Synthetic federation UI test; no actual client BIM is used."""
from pathlib import Path
import sys,json,shutil
from playwright.sync_api import sync_playwright,expect
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'backend/tests'))
from ifc_fixtures import write_fixture
folder=root/'test_models';folder.mkdir(exist_ok=True)
arch=folder/'architecture-browser.ifc';mep=folder/'ventilation-browser.ifc'
write_fixture(arch,equipment=False);write_fixture(mep,millimetres=True,equipment=False,offset=(700003,6500004,12))
third=folder/'third-browser.ifc';write_fixture(third,equipment=False)
bad=folder/'invalid-browser.ifc';bad.write_text('not an IFC file')
with sync_playwright() as tool:
 browser=tool.chromium.launch(executable_path=shutil.which('chromium') or tool.chromium.executable_path,headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
 page=browser.new_page(viewport={'width':1600,'height':1050});errors=[]
 page.on('pageerror',lambda error:errors.append(str(error)))
 page.goto('http://127.0.0.1:5173')
 page.locator('input[accept=".ifc,.IFC"]').set_input_files([str(arch),str(mep)])
 expect(page.get_by_role('heading',name='Loaded IFC files (2)',exact=True)).to_be_visible(timeout=30000)
 page.get_by_role('button',name='Run optimization',exact=True).click()
 page.locator('.metric').wait_for(timeout=60000)
 expect(page.get_by_text('unprotected',exact=True).first).to_be_visible()
 with page.expect_download() as download:page.get_by_role('button',name='Save project',exact=True).click()
 output=folder/'federation-browser.json';download.value.save_as(str(output))
 project=json.loads(output.read_text());assert len(project['ifc_sources'])==2
 assert len({m['name'] for m in project['meshes']})==2
 assert sorted(s['length_unit_scale_to_m'] for s in project['ifc_sources'])==[.001,1]
 # Batch rollback: the first candidate is valid, the second file is invalid.
 page.locator('input[accept=".ifc,.IFC"]').set_input_files([str(third),str(bad)])
 expect(page.get_by_role('alert')).to_contain_text('previous model remains loaded',timeout=30000)
 expect(page.get_by_role('heading',name='Loaded IFC files (2)',exact=True)).to_be_visible()
 source=page.locator('details').filter(has=page.locator('summary',has_text='ventilation-browser.ifc')).first
 source.locator('summary').click()
 source.get_by_role('button',name='Remove IFC file',exact=True).click()
 expect(page.get_by_role('heading',name='Loaded IFC files (1)',exact=True)).to_be_visible(timeout=30000)
 assert not errors,errors
 page.screenshot(path=str(folder/'federation-browser.png'))
 browser.close()
 print('Multiple IFC selection, source provenance, combined calculation, failed-batch rollback and source removal: PASS')
