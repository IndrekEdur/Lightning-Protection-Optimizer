"""IFC height-selection/reimport smoke test; synthetic private fixture only."""
from pathlib import Path
import sys,json,shutil
from playwright.sync_api import sync_playwright,expect
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'backend/tests'))
from ifc_fixtures import write_fixture
path=root/'test_models/height-browser.ifc';path.parent.mkdir(exist_ok=True)
write_fixture(path,millimetres=True,equipment=True)
with sync_playwright() as tool:
    browser=tool.chromium.launch(executable_path=shutil.which('chromium') or tool.chromium.executable_path,headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
    page=browser.new_page(viewport={'width':1600,'height':1050});errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto('http://127.0.0.1:5173')
    page.locator('input[accept=".ifc,.IFC"]').set_input_files(str(path))
    expect(page.get_by_text('2 elements · 24 triangles',exact=False).last).to_be_visible(timeout=30000)
    minimum=page.locator('input[placeholder="No lower limit"]');maximum=page.locator('input[placeholder="No upper limit"]')
    page.locator('label').filter(has_text='Import operation').locator('select').select_option(index=1)
    minimum.fill('11');maximum.fill('12')
    page.get_by_role('button',name='Import selected file with height range',exact=True).click()
    expect(page.get_by_text('1 elements · 12 triangles',exact=False).last).to_be_visible(timeout=30000)
    expect(page.get_by_text('Loaded range: 11 … 12 m',exact=False).last).to_be_visible()
    with page.expect_download() as download:page.get_by_role('button',name='Save project',exact=True).click()
    output=root/'test_models/height-browser.project.json';download.value.save_as(str(output))
    saved=json.loads(output.read_text());assert len(saved['meshes'])==1
    assert saved['meshes'][0]['ifc_class']=='IfcBuildingElementProxy'
    page.locator('label').filter(has_text='Import operation').locator('select').select_option(index=1)
    minimum.fill('100');maximum.fill('110')
    page.get_by_role('button',name='Import selected file with height range',exact=True).click()
    expect(page.get_by_role('alert')).to_contain_text('previous model remains loaded',timeout=30000)
    assert not errors,errors
    page.screenshot(path=str(root/'test_models/height-range-browser.png'))
    browser.close()
    print('Height bounds, same-file reimport, whole-element selection, source units and failed-import preservation: PASS')
