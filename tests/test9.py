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
        # weekday rule every 2 months: 2nd Wednesday, starting 14 Oct
        await pg.click('.tab.add'); await pg.fill('#fName','Dentist check-up'); await pg.click('#fOwner [data-owner=both]'); await pg.click('[data-fday="2026-10-14"]')
        await pg.click('#repToggle')
        check('months box hidden until a monthly option', not await pg.is_visible('#monthsBlock'))
        await rep(pg,'monthly')
        check('months box shows, defaults to 1', await pg.is_visible('#monthsBlock') and await pg.input_value('#fMonths')=='1' and await pg.inner_text('#monthsWord')=='month')
        await pg.fill('#fMonths','2')
        check('summary says every 2 months', 'Every 2 months on the 2nd Wednesday' in await pg.inner_text('#repSummary') and await pg.inner_text('#monthsWord')=='months')
        check('note says every 2 months', 'every 2 months' in await pg.inner_text('#repNote'))
        await pg.fill('#fMonths','0'); await pg.click('.head-save')
        check('0 months rejected', '1 to 12' in await pg.inner_text('#formError'))
        await pg.fill('#fMonths','13'); await pg.click('.head-save'); check('13 rejected', '1 to 12' in await pg.inner_text('#formError'))
        await pg.fill('#fMonths','2'); await pg.click('.head-save')
        check('14 Oct', 'Dentist check-up' in await pg.inner_text('#todayView'))
        check('not 11 Nov (skipped month)', not await has('2026-11-11','Dentist check-up'))
        check('9 Dec (2nd Wed, two months on)', await has('2026-12-09','Dentist check-up'))
        check('not 13 Jan', not await has('2027-01-13','Dentist check-up'))
        check('10 Feb 2027', await has('2027-02-10','Dentist check-up'))
        # date rule every 3 months, from the 28th
        await pg.click('[data-view=week]'); await pg.click('[data-view=today]')
        await pg.click('.tab.add'); await pg.fill('#fName','Service the car'); await pg.click('#fOwner [data-owner=toby]'); await rep(pg,'monthdate')
        await pg.fill('#fMonthDay','28'); await pg.fill('#fMonths','3')
        check('summary says every 3 months on the 28th', 'Every 3 months on the 28th' in await pg.inner_text('#repSummary'))
        n=await pg.inner_text('#repNote'); check('note wording', 'every 3 months' in n and 'The first entry will be on Wednesday 28th October.' in n)
        await pg.click('.head-save')
        check('starts on 28 Oct', '28 October' in await pg.inner_text('#dateTitle'))
        check('not 28 Nov', not await has('2026-11-28','Service the car'))
        check('not 28 Dec', not await has('2026-12-28','Service the car'))
        check('28 Jan 2027', await has('2027-01-28','Service the car'))
        check('28 Apr 2027', await has('2027-04-28','Service the car'))
        # changing only the interval on an existing series is a repeat change (applies forwards)
        await has('2027-01-28','Service the car')
        await pg.click('#todayView .card:has-text("Service the car") .body')
        check('edit shows 3 months', await pg.input_value('#fMonths')=='3')
        await pg.click('#repToggle'); await pg.fill('#fMonths','6'); await pg.click('.head-save')
        check('interval change forces the forwards message', await pg.is_visible('#scopeBox') and not await pg.is_visible('#scopeOne') and 'forwards' in await pg.inner_text('#scopeTitle'))
        await pg.click('#scopeFuture')
        check('28 Jul 2027 now (6 months on)', await has('2027-07-28','Service the car'))
        check('28 Apr 2027 no longer', not await has('2027-04-28','Service the car'))
        check('28 Oct 2026 earlier entry kept', await has('2026-10-28','Service the car'))
        # existing seeded monthly series (no interval stored) still monthly
        check('book club seed unchanged (11 Nov)', await has('2026-11-11','Book club'))
        check('no page errors', not errs)
        await b.close()
    print('FAILED:', bad or 'none')
asyncio.run(main())
