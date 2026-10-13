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
        async def has(date, name):
            await pg.click('[data-view=week]'); await pg.click('[data-view=today]')
            for _ in range(80):
                if await pg.locator(f'[data-day="{date}"]').count(): break
                await pg.click('[data-nav="1"]')
            await pg.click(f'[data-day="{date}"]'); return name in await pg.inner_text('#todayView')
        # picked day is Monday 12 Oct (the 2nd Monday), but we want the 3rd Tuesday
        await pg.click('.tab.add'); await pg.fill('#fName','Book group'); await pg.click('#fOwner [data-owner=both]')
        await pg.click('#repToggle'); await pg.click('[data-rep=monthly]')
        check('chips are fixed wording', await pg.inner_text('[data-rep=monthly]')=='Monthly on a day' and await pg.inner_text('[data-rep=monthdate]')=='Monthly on a date')
        check('selectors default to the picked day (2nd Monday)', await pg.input_value('#fNth')=='2' and await pg.input_value('#fWd')=='0' and 'Monthly on the 2nd Monday' in await pg.inner_text('#repSummary'))
        await pg.select_option('#fNth','3'); await pg.select_option('#fWd','1')
        check('summary follows the selectors', 'Monthly on the 3rd Tuesday' in await pg.inner_text('#repSummary'))
        check('note names the first entry', 'The first entry will be on Tuesday 20th October.' in await pg.inner_text('#repNote'))
        await pg.click('[data-fday="2026-10-14"]')
        check('moving the day does not overwrite the choice', await pg.input_value('#fNth')=='3' and await pg.input_value('#fWd')=='1')
        await pg.click('.head-save')
        check('jumps to the first entry, 20 October', '20 October' in await pg.inner_text('#dateTitle') and 'Book group' in await pg.inner_text('#todayView'))
        check('not on the picked day', not await has('2026-10-12','Book group'))
        check('not 13 Oct (2nd Tuesday)', not await has('2026-10-13','Book group'))
        check('17 Nov (3rd Tuesday)', await has('2026-11-17','Book group'))
        check('not 10 Nov', not await has('2026-11-10','Book group'))
        # last Friday every month
        await pg.click('[data-view=week]'); await pg.click('[data-view=today]')
        await pg.click('.tab.add'); await pg.fill('#fName','Stock take'); await pg.click('#fOwner [data-owner=toby]')
        await pg.click('#repToggle'); await pg.click('[data-rep=monthly]'); await pg.select_option('#fNth','5'); await pg.select_option('#fWd','4')
        check('last Friday summary', 'Monthly on the last Friday' in await pg.inner_text('#repSummary'))
        await pg.click('.head-save')
        check('Fri 30 Oct', '30 October' in await pg.inner_text('#dateTitle'))
        check('Fri 27 Nov', await has('2026-11-27','Stock take'))
        check('not Fri 20 Nov', not await has('2026-11-20','Stock take'))
        # first Monday every 2 months
        await pg.click('[data-view=week]'); await pg.click('[data-view=today]')
        await pg.click('.tab.add'); await pg.fill('#fName','Review'); await pg.click('#fOwner [data-owner=both]')
        await pg.click('#repToggle'); await pg.click('[data-rep=monthly]'); await pg.select_option('#fNth','1'); await pg.select_option('#fWd','0'); await pg.fill('#fMonths','2')
        check('summary with interval', 'Every 2 months on the 1st Monday' in await pg.inner_text('#repSummary'))
        await pg.click('.head-save')
        check('first Monday is 2 Nov', '2 November' in await pg.inner_text('#dateTitle'))
        check('not 7 Dec', not await has('2026-12-07','Review'))
        check('4 Jan 2027', await has('2027-01-04','Review'))
        # edit one: selectors preloaded
        await has('2026-11-17','Book group')
        await pg.click('#todayView .card:has-text("Book group") .body')
        await pg.click('#repToggle')
        check('edit shows 3rd Tuesday preselected', await pg.input_value('#fNth')=='3' and await pg.input_value('#fWd')=='1')
        await pg.select_option('#fNth','2'); await pg.click('.head-save')
        check('changing the selectors forces the forwards message', await pg.is_visible('#scopeBox') and not await pg.is_visible('#scopeOne'))
        await pg.click('#scopeFuture')
        check('17 Nov no longer has it (the 2nd Tuesday of November had already passed)', not await has('2026-11-17','Book group'))
        check('8 Dec (2nd Tuesday)', await has('2026-12-08','Book group'))
        check('earlier 20 Oct kept', await has('2026-10-20','Book group'))
        check('no page errors', not errs)
        await b.close()
    print('FAILED:', bad or 'none')
asyncio.run(main())
