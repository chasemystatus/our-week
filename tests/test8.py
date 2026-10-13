import os
APP_FILE = 'file://' + os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app', 'index.html'))
APP_DEMO = APP_FILE + '?demo=1'
import asyncio
from playwright.async_api import async_playwright
from fake import FAKE
bad=[]
async def rep(pg,k):
    if not await pg.is_visible('#repPanel'): await pg.click('#repToggle')
    await pg.click(f'[data-rep={k}]')
def check(n,ok):
    print('PASS' if ok else 'FAIL',n)
    if not ok: bad.append(n)
async def title(pg): return await pg.inner_text('#dateTitle')
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        ctx=await b.new_context(viewport={'width':390,'height':700},locale='en-GB'); await ctx.add_init_script(FAKE)
        pg=await ctx.new_page(); errs=[]; pg.on('pageerror',lambda e:errs.append(e))
        await pg.goto(APP_DEMO)
        await pg.click('.tab.add'); await pg.fill('#fName','Pay the window cleaner'); await pg.click('#fOwner [data-owner=both]')
        await rep(pg,'monthdate')
        check('summary follows chosen day (12th)', 'Monthly on the 12th' in await pg.inner_text('#repSummary'))
        await pg.click('[data-fday="2026-10-14"]')
        check('summary follows day change (14th)', 'Monthly on the 14th' in await pg.inner_text('#repSummary'))
        await rep(pg,'monthdate')
        check('day box shows 14', await pg.input_value('#fMonthDay')=='14' and await pg.is_visible('#monthDayBlock'))
        note=await pg.inner_text('#repNote')
        check('note says forwards, not "on"', 'forwards' in note and 'from this one on.' not in note)
        await pg.fill('#fMonthDay','28')
        check('summary and note follow typed day', 'Monthly on the 28th' in await pg.inner_text('#repSummary') and 'first entry will be on Wednesday 28th October' in await pg.inner_text('#repNote'))
        await pg.fill('#fMonthDay','')
        await pg.click('.head-save'); check('empty day rejected', '1 to 31' in await pg.inner_text('#formError'))
        await pg.fill('#fMonthDay','28'); await pg.click('.head-save')
        check('jumps to the first 28th', '28 October' in await title(pg))
        check('entry there with repeat marker', 'Pay the window cleaner' in await pg.inner_text('#todayView') and '↻' in await pg.inner_text('#todayView'))
        async def on(date):
            await pg.click('[data-view=week]'); await pg.click('[data-view=today]')
            # walk by weeks until the week holding date, then pick the day
            for _ in range(60):
                if await pg.locator(f'[data-day="{date}"]').count(): break
                await pg.click('[data-nav="1"]')
            await pg.click(f'[data-day="{date}"]')
            return 'Pay the window cleaner' in await pg.inner_text('#todayView')
        check('28 Nov', await on('2026-11-28'))
        check('not 27 Nov', not await on('2026-11-27'))
        check('not 14 Oct (picked day, but not the 28th)', not await on('2026-10-14'))
        # short months: day 31
        await pg.click('[data-view=week]'); await pg.click('[data-view=today]')
        await pg.click('.tab.add'); await pg.fill('#fName','Month end'); await pg.click('#fOwner [data-owner=toby]'); await rep(pg,'monthdate'); await pg.fill('#fMonthDay','31')
        check('31 note mentions shorter months', 'last day in shorter months' in await pg.inner_text('#repNote'))
        await pg.click('.head-save')
        async def has(date, name='Month end'):
            await pg.click('[data-view=week]'); await pg.click('[data-view=today]')
            for _ in range(80):
                if await pg.locator(f'[data-day="{date}"]').count(): break
                await pg.click('[data-nav="1"]')
            await pg.click(f'[data-day="{date}"]'); return name in await pg.inner_text('#todayView')
        check('31 Oct', await has('2026-10-31')); check('30 Nov (no 31st)', await has('2026-11-30')); check('29 Nov not', not await has('2026-11-29'))
        check('31 Dec', await has('2026-12-31')); check('28 Feb 2027', await has('2027-02-28')); check('27 Feb 2027 not', not await has('2027-02-27'))
        # edit existing date series: change only the name -> asks week-only/forwards
        await has('2026-10-28')
        await pg.click('#todayView .card:has-text("Pay the window cleaner") .body')
        check('edit preselects the date option with 28', await pg.get_attribute('[data-rep=monthdate]','aria-pressed')=='true' and await pg.input_value('#fMonthDay')=='28')
        await pg.fill('#fName','Window cleaner'); await pg.click('.head-save')
        check('asks which weeks, with the choice', await pg.is_visible('#scopeOne') and 'forwards' not in await pg.inner_text('#scopeTitle'))
        await pg.click('#scopeFuture'); check('renamed', 'Window cleaner' in await pg.inner_text('#todayView'))
        # sticky header
        await pg.click('.tab.add')
        await pg.evaluate("document.querySelector('#sheet').scrollTo(0,99999)")
        top=await pg.eval_on_selector('.head-save','e=>e.getBoundingClientRect().top')
        sheetTop=await pg.eval_on_selector('#sheet','e=>e.getBoundingClientRect().top')
        check('Save still visible after scrolling to the bottom', await pg.is_visible('.head-save') and top>=sheetTop-1 and top<700)
        check('Cancel still visible too', await pg.is_visible('#sheet .link-btn'))
        check('no page errors', not errs)
        await b.close()
    print('FAILED:', bad or 'none')
asyncio.run(main())
