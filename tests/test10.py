import os
APP_FILE = 'file://' + os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app', 'index.html'))
APP_DEMO = APP_FILE + '?demo=1'
import asyncio
from playwright.async_api import async_playwright
from fake import FAKE
bad=[]
def check(n,ok):
    print('PASS' if ok else 'FAIL',n)
    if not ok: bad.append(n)
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        ctx=await b.new_context(viewport={'width':390,'height':760},locale='en-GB'); await ctx.add_init_script(FAKE)
        pg=await ctx.new_page(); errs=[]; pg.on('pageerror',lambda e:errs.append(e))
        await pg.goto(APP_DEMO)
        await pg.click('.tab.add')
        check('closed by default', not await pg.is_visible('#repPanel') and await pg.get_attribute('#repToggle','aria-expanded')=='false')
        check('summary says Doesn\'t repeat', "Doesn't repeat" in await pg.inner_text('#repSummary'))
        h_closed=await pg.eval_on_selector('#entryForm','e=>e.scrollHeight')
        await pg.click('#repToggle')
        check('opens', await pg.is_visible('#repPanel') and await pg.get_attribute('#repToggle','aria-expanded')=='true')
        check('form is shorter when closed', await pg.eval_on_selector('#entryForm','e=>e.scrollHeight')>h_closed+100)
        await pg.click('[data-rep=weekly]'); await pg.click('#repToggle')
        check('closing keeps the choice, shown in the summary', not await pg.is_visible('#repPanel') and 'Every week' in await pg.inner_text('#repSummary'))
        await pg.fill('#fName','Water plants'); await pg.click('#fOwner [data-owner=both]'); await pg.click('.head-save')
        check('saved as repeating without opening again', '↻' in await pg.inner_text('#todayView'))
        # edit: closed again, summary shows existing repeat
        await pg.click('#todayView .card:has-text("Water plants") .body')
        check('edit starts closed with summary', not await pg.is_visible('#repPanel') and 'Every week' in await pg.inner_text('#repSummary'))
        await pg.click('#sheet .link-btn')
        # custom summary + error opens the panel
        await pg.click('.tab.add'); await pg.fill('#fName','x'); await pg.click('#fOwner [data-owner=both]')
        await pg.click('#repToggle'); await pg.click('[data-rep=custom]'); await pg.fill('#fEvery','4')
        check('custom summary', 'Every 4 weeks' in await pg.inner_text('#repSummary'))
        await pg.fill('#fEvery','1'); await pg.click('#repToggle')
        await pg.click('.head-save')
        check('a repeat error opens the panel', await pg.is_visible('#repPanel') and 'number from 2 to 26' in await pg.inner_text('#formError'))
        await pg.click('#sheet .link-btn'); await pg.click('.tab.add')
        check('a new Add starts closed again', not await pg.is_visible('#repPanel') and "Doesn't repeat" in await pg.inner_text('#repSummary'))
        check('toggle is a 44px+ target', (await pg.eval_on_selector('#repToggle','e=>e.getBoundingClientRect().height'))>=44)
        check('no page errors', not errs)
        await pg.screenshot(path='rep-closed.png')
        await b.close()
    print('FAILED:', bad or 'none')
asyncio.run(main())
