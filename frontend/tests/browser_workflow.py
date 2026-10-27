import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
root=Path('/workspace/Lightning-Protection-Optimizer')
project=json.loads((root/'examples/rolling-sphere.json').read_text())
project.update(width=10,depth=10,equipment=[],spacing=5,objective='cost',rods=[],sphere_refinement=0)
(root/'artifacts/browser-project.json').write_text(json.dumps(project))
with sync_playwright() as tool:
 browser=tool.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
 page=browser.new_page(viewport={'width':1600,'height':1050})
 page.on('response',lambda response:print('Report HTTP',response.status,response.text()[:300] if response.status!=200 else '',flush=True) if '/api/report/' in response.url else None)
 errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
 page.goto('http://127.0.0.1:5173')
 page.locator('input[type=file]').set_input_files(str(root/'artifacts/browser-project.json'))
 expect(page.locator('select:has(option[value=rolling_sphere])')).to_have_value('rolling_sphere')
 page.get_by_role('button',name='Run optimization',exact=True).click()
 page.locator('.metric').wait_for(timeout=90000)
 assert 'Verified' in page.locator('body').inner_text(),page.locator('body').inner_text()
 print('Cost result',page.locator('.metric').inner_text(),flush=True)
 page.locator('select:has(option[value=cost])').select_option('count')
 page.get_by_role('button',name='Run optimization',exact=True).click()
 page.locator('.metric').wait_for(timeout=90000)
 page.get_by_role('button',name='cost',exact=True).click()
 page.get_by_role('button',name='Inspect sphere contacts',exact=True).click()
 page.screenshot(path=str(root/'artifacts/rolling-sphere-verified.png'))
 for format in ['Excel','PDF']:
  with page.expect_download(timeout=8000) as download:
   page.get_by_role('button',name='Export '+format,exact=True).click()
  file=download.value;file.save_as(str(root/'artifacts'/file.suggested_filename))
  print('Downloaded',file.suggested_filename,flush=True)
 assert not errors,errors
 print('Browser workflow PASS; runtime errors:',errors,flush=True)
 browser.close()
