"""End-to-end synthetic IFC smoke test. Requires local backend/Vite and Chromium."""
from pathlib import Path
import sys
import shutil
from playwright.sync_api import sync_playwright,expect
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'backend/tests'))
from ifc_fixtures import write_fixture
path=root/'test_models/browser-reference.ifc';path.parent.mkdir(exist_ok=True)
write_fixture(path,millimetres=True,slope=.1,equipment=False)
with sync_playwright() as tool:
    browser=tool.chromium.launch(executable_path=shutil.which('chromium') or tool.chromium.executable_path,headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
    page=browser.new_page(viewport={'width':1600,'height':1050});errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto('http://127.0.0.1:5173')
    page.locator('input[accept=".ifc,.IFC"]').set_input_files(str(path))
    expect(page.get_by_text('Source unit → metre: × 0.001',exact=False)).to_be_visible(timeout=30000)
    assert page.locator('canvas').count()==1
    page.get_by_role('button',name='Run optimization',exact=True).click()
    page.locator('.metric').wait_for(timeout=60000)
    expect(page.get_by_text('unprotected',exact=True).first).to_be_visible()
    page.get_by_role('button',name='Add rod',exact=True).click()
    expect(page.locator('input[type=number]').filter()).not_to_have_count(0)
    expect(page.locator('select:has(option[value="0"])').last).to_be_visible()
    with page.expect_download() as download:
        page.get_by_role('button',name='Save project',exact=True).click()
    download.value.save_as(str(root/'test_models/browser-imported-project.json'))
    page.screenshot(path=str(root/'test_models/ifc-browser.png'))
    assert not errors,errors
    print('IFC browser import, unit metadata, floating-origin viewer, rolling-sphere contact and manual mounting: PASS')
    browser.close()
