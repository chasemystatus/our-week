import os
APP_FILE = 'file://' + os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app', 'index.html'))
APP_DEMO = APP_FILE + '?demo=1'
import asyncio
from playwright.async_api import async_playwright
bad=[]
def check(n,ok):
    print('PASS' if ok else 'FAIL',n)
    if not ok: bad.append(n)
async def op(pg): return float(await pg.eval_on_selector('#saveState','e=>getComputedStyle(e).opacity'))
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(viewport={'width':390,'height':844},locale='en-GB')).new_page()
        errs=[]; pg.on('pageerror',lambda e:errs.append(e))
        await pg.goto(APP_DEMO)
        check('hidden on load', await op(pg)==0)
        await pg.click('[data-view=week]'); await pg.click('[data-nav="1"]'); await pg.click('[data-who=toby]'); await pg.click('[data-view=today]')
        check('hidden after only changing views', await op(pg)==0)
        await pg.click('.tab.add'); await pg.fill('#fName','Test'); await pg.click('#fOwner [data-owner=both]'); await pg.click('.head-save')
        await pg.wait_for_timeout(900)
        check('shows Saved after saving', await op(pg)>0.9 and 'Saved' in await pg.inner_text('#saveState'))
        await pg.wait_for_timeout(4500)
        check('fades away afterwards', await op(pg)==0)
        await pg.click('.tab.add'); await pg.fill('#fName','Again'); await pg.click('#fOwner [data-owner=both]'); await pg.click('.head-save')
        await pg.wait_for_timeout(1500); await pg.click("[data-view=week]"); await pg.wait_for_timeout(800)
        check('still showing about 2.5s after saving, even after switching view', await op(pg)>0.9)
        check('no page errors', not errs)
        await b.close()
    print('FAILED:', bad or 'none')
asyncio.run(main())
