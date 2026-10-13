import os
APP_FILE = 'file://' + os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app', 'index.html'))
APP_DEMO = APP_FILE + '?demo=1'
import asyncio, re
from playwright.async_api import async_playwright
from fake import FAKE
bad=[]
async def rep(pg,k):
    if not await pg.is_visible('#repPanel'): await pg.click('#repToggle')
    await pg.click(f'[data-rep={k}]')
def check(n,ok):
    print('PASS' if ok else 'FAIL',n)
    if not ok: bad.append(n)
async def day(pg): return await pg.inner_text('#todayView')
async def go(pg, n):
    k = 'nav'
    for _ in range(abs(n)): await pg.click(f'[data-nav="{1 if n>0 else -1}"]')
async def home(pg):
    await pg.click('[data-view=week]'); await pg.click('[data-view=today]')
async def open_card(pg, text):
    await pg.click(f'#todayView .card:has-text("{text}") .body')
async def rep_(pg,k):
    if not await pg.is_visible('#repPanel'): await pg.click('#repToggle')
    await pg.click(f'[data-rep={k}]')
async def add(pg, name, owner='both', rep=None, every=None, day=None, typ=None):
    await pg.click('.tab.add'); await pg.fill('#fName', name)
    if typ: await pg.click(f'#fType [data-type={typ}]')
    await pg.click(f'#fOwner [data-owner={owner}]')
    if day: await pg.click(f'[data-fday="{day}"]')
    if rep: await rep_(pg, rep)
    if every is not None: await pg.fill('#fEvery', str(every))
    await pg.click('.head-save')
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        ctx=await b.new_context(viewport={'width':390,'height':844},locale='en-GB'); await ctx.add_init_script(FAKE)
        pg=await ctx.new_page(); errs=[]; pg.on('pageerror',lambda e:errs.append(e))
        await pg.goto(APP_DEMO)
        # seeded series
        t=await day(pg)
        check('bins repeat marker today', 'Put bins out' in t and '↻' in t)
        await go(pg,1); t=await day(pg); check('bins next Monday', 'Put bins out' in t)
        check('fortnightly shift not next week', 'Café shift' not in t)
        check('one-offs not carried (Dentist, Library books)', 'Dentist' not in t and 'Library books' not in t)
        await go(pg,1); t=await day(pg); check('fortnightly shift two weeks on', 'Café shift' in t and 'Put bins out' in t)
        await go(pg,-3); t=await day(pg); check('bins last week (series started 2 weeks ago)', 'Put bins out' in t and 'Café shift' not in t)
        await go(pg,-1); t=await day(pg); check('bins two weeks ago', 'Put bins out' in t)
        await go(pg,-1); t=await day(pg); check('nothing before series start', 'Put bins out' not in t)
        # monthly: 2nd Wednesday
        await home(pg); await pg.click('[data-day="2026-10-14"]'); t=await day(pg); check('book club 14 Oct', 'Book club' in t)
        await pg.click('[data-nav="1"]'); t=await day(pg); check('not 21 Oct', 'Book club' not in t)
        for _ in range(3): await pg.click('[data-nav="1"]')
        check('book club 11 Nov (2nd Wed)', '11 November' in await pg.inner_text('#dateTitle') and 'Book club' in await day(pg))
        await pg.click('[data-nav="1"]'); check('not 18 Nov', 'Book club' not in await day(pg))
        for _ in range(6): await pg.click('[data-nav="-1"]')
        check('not 7 Oct, before it started', 'Book club' not in await day(pg))
        # week view agrees
        await home(pg); await pg.click('[data-view=week]')
        w=await pg.inner_text('#weekView'); check('week view shows bins and book club', w.count('Put bins out')==1 and 'Book club' in w)
        await pg.click('[data-view=today]')
        # add one-off (default off) and weekly
        await add(pg,'One-off thing',day='2026-10-13'); await pg.click('[data-nav="1"]')
        check('one-off not on next week', 'One-off thing' not in await day(pg))
        await home(pg); await add(pg,'Gym','toby',rep='weekly',day='2026-10-14',typ='plan')
        check('weekly entry shows with marker', 'Gym' in await day(pg) and '↻' in await day(pg))
        await pg.click('[data-nav="1"]'); check('Gym next Wed', 'Gym' in await day(pg))
        await pg.click('[data-nav="1"]'); check('Gym again', 'Gym' in await day(pg))
        for _ in range(3): await pg.click('[data-nav="-1"]')
        check('Gym not before it was created', 'Gym' not in await day(pg))
        # joint repeating task done for both, only that week
        await home(pg); await add(pg,'Water the plants','both',rep='weekly',typ='task')
        card=pg.locator('#todayView .card:has-text("Water the plants")')
        await card.locator('[data-toggle]').click()
        check('done this week', 'Done' in await card.inner_text())
        await pg.click('[data-who=eloise]'); check('Eloise sees it done too (one entry)', 'Done' in await pg.locator('#todayView .card:has-text("Water the plants")').inner_text())
        await pg.click('[data-who=all]'); await pg.click('[data-nav="1"]')
        check('next week it is a fresh to-do', 'To do' in await pg.locator('#todayView .card:has-text("Water the plants")').inner_text())
        # edit: this week only (bins, this Monday)
        await home(pg); await open_card(pg,'Put bins out')
        check('edit shows Every week selected', await pg.get_attribute('[data-rep=weekly]','aria-pressed')=='true')
        await pg.fill('#fName','Bins and recycling'); await pg.click('.head-save')
        check('scope box asks', await pg.is_visible('#scopeBox') and await pg.is_visible('#scopeOne'))
        await pg.click('#scopeOne')
        check('this week renamed', 'Bins and recycling' in await day(pg))
        await pg.click('[data-nav="1"]'); check('next week unchanged', 'Put bins out' in await day(pg) and 'Bins and recycling' not in await day(pg))
        # edit all later weeks from next Monday
        await open_card(pg,'Put bins out'); await pg.fill('#fName','Bins out early'); await pg.click('.head-save'); await pg.click('#scopeFuture')
        await pg.click('[data-nav="1"]'); check('later week uses new name', 'Bins out early' in await day(pg))
        await pg.click('[data-nav="-1"]'); await pg.click('[data-nav="-1"]')
        check('this week keeps its own one-week edit', 'Bins and recycling' in await day(pg))
        await pg.click('[data-nav="-1"]'); check('earlier week untouched', 'Put bins out' in await day(pg))
        # delete this week only
        await go(pg,2); await open_card(pg,'Bins out early'); await pg.click('#btnDelete')
        check('delete asks which', await pg.is_visible('#scopeBox') and 'Delete' in await pg.inner_text('#scopeTitle'))
        await pg.click('#scopeOne'); check('that week gone', 'Bins out early' not in await day(pg))
        await pg.click('[data-nav="1"]'); check('following week still there', 'Bins out early' in await day(pg))
        # delete this and later, then undo
        await open_card(pg,'Bins out early'); await pg.click('#btnDelete'); await pg.click('#scopeFuture')
        check('gone from here', 'Bins out early' not in await day(pg))
        await pg.click('#toastAction')
        await pg.wait_for_timeout(100)
        check('undo restores this week', 'Bins out early' in await day(pg))
        await go(pg,2); check('undo restores later weeks', 'Bins out early' in await day(pg))
        await open_card(pg,'Bins out early'); await pg.click('#btnDelete'); await pg.click('#scopeFuture')
        await go(pg,2); check('deleted: later weeks gone', 'Bins out early' not in await day(pg))
        await go(pg,-3); check('deleted from week 5: week 4 still has it', 'Bins out early' in await day(pg))
        # turn repeat off from this week on (Gym)
        await home(pg); await go(pg,1); await pg.click('[data-day="2026-10-21"]')
        await open_card(pg,'Gym'); await rep(pg,'off'); await pg.click('.head-save')
        check('repeat change skips the week-only choice', await pg.is_visible('#scopeBox') and not await pg.is_visible('#scopeOne'))
        await pg.click('#scopeFuture')
        check('kept this week as a one-off', 'Gym' in await day(pg) and '↻' not in await pg.locator('#todayView .card:has-text("Gym")').inner_text())
        await pg.click('[data-nav="1"]'); check('none after', 'Gym' not in await day(pg))
        await go(pg,-2); check('week before keeps repeating', 'Gym' in await day(pg) and '↻' in await pg.locator('#todayView .card:has-text("Gym")').inner_text())
        # custom interval
        await home(pg); await add(pg,'Boiler check','both',rep='custom',every=3,typ='plan')
        check('custom shows', 'Boiler check' in await day(pg))
        await go(pg,1); a='Boiler check' in await day(pg); await go(pg,1); b2='Boiler check' in await day(pg); await go(pg,1); c='Boiler check' in await day(pg)
        check('every 3 weeks: not +1, not +2, yes +3', (not a) and (not b2) and c)
        await home(pg); await pg.click('.tab.add'); await pg.fill('#fName','Bad'); await pg.click('#fOwner [data-owner=both]'); await rep(pg,'custom'); await pg.fill('#fEvery','1'); await pg.click('.head-save')
        check('custom 1 rejected', 'number from 2 to 26' in await pg.inner_text('#formError'))
        await rep(pg,'monthly'); check('monthly summary names the day', 'Monthly on the 2nd Monday' in await pg.inner_text('#repSummary'))
        await pg.click('#sheet .link-btn')
        # sheet fits and Save visible at 320x568-ish with the long form
        await pg.set_viewport_size({'width':390,'height':700}); await pg.click('.tab.add')
        check('header Save visible with long form', await pg.is_visible('.head-save') and (await pg.eval_on_selector('.head-save','e=>e.getBoundingClientRect().top'))>=0)
        check('no page errors', not errs)
        await b.close()
    print('FAILED:', bad or 'none')
asyncio.run(main())
