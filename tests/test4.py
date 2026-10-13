import os
APP_FILE = 'file://' + os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app', 'index.html'))
APP_DEMO = APP_FILE + '?demo=1'
from fake import FAKE
import asyncio
from playwright.async_api import async_playwright
fails = []
def check(label, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + label + (' ' + str(extra) if extra and not cond else ''))
    if not cond: fails.append(label)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width':390,'height':844}, device_scale_factor=2, locale='en-GB')
        pg = await ctx.new_page()
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.add_init_script(FAKE); await pg.goto(APP_DEMO)

        # wording
        labels = await pg.eval_on_selector_all('#filter button', 'els => els.map(e => e.textContent)')
        check('filter reads Both / Eloise / Toby', labels == ['Both','Eloise','Toby'], labels)
        check('Both note', await pg.inner_text('#filterNote') == "Eloise and Toby's day, including joint entries")
        await pg.click('#filter [data-who=eloise]')
        check('Eloise note unchanged', await pg.inner_text('#filterNote') == "Eloise's day, including joint entries")
        await pg.click('#filter [data-who=all]')

        # Until close
        await pg.click('.tab.add')
        await pg.fill('#fName', 'Bar shift')
        await pg.click('#fType [data-type=shift]')
        await pg.click('#fOwner [data-owner=toby]')
        check('Until close shown for shifts', await pg.is_visible('#btnUntil'))
        await pg.fill('#fStart', '17:00')
        await pg.fill('#fEnd', '23:00')
        await pg.click('#btnUntil')
        check('finish field disabled and cleared', await pg.is_disabled('#fEnd') and await pg.input_value('#fEnd') == '')
        check('no explanation line under Until close', (await pg.inner_text('#endNote')).strip() == '')
        await pg.click('.head-save')
        check('card shows start–close', '17:00–close' in await pg.inner_text('#todayView'))
        # edit: prefilled pressed, then turn off
        await pg.click('.card:has-text("Bar shift") .body')
        check('edit shows Until close on', await pg.get_attribute('#btnUntil','aria-pressed') == 'true')
        await pg.click('#btnUntil')
        check('turning it off re-enables finish', not await pg.is_disabled('#fEnd'))
        await pg.click('#btnUntil')
        await pg.click('[data-close]')

        # After midnight
        await pg.click('.tab.add')
        await pg.fill('#fName', 'Late shift')
        await pg.click('#fType [data-type=shift]')
        await pg.click('#fOwner [data-owner=toby]')
        await pg.fill('#fStart', '22:00'); await pg.fill('#fEnd', '02:00')
        check('after-midnight note', 'following day' in await pg.inner_text('#endNote'))
        await pg.click('.head-save')
        check('card shows hours only, no next day', '22:00–02:00' in await pg.inner_text('#todayView') and 'next day' not in await pg.inner_text('#todayView'))
        await pg.click('.day[data-day="2026-10-13"]')
        check('not shown on the following day', 'Late shift' not in await pg.inner_text('#todayView'))
        await pg.click('.day[data-day="2026-10-12"]')

        # Guards
        await pg.click('.tab.add')
        await pg.fill('#fName', 'Typo check'); await pg.click('#fOwner [data-owner=both]')
        await pg.click('#fWhen [data-when=time]')
        await pg.fill('#fStart', '16:15'); await pg.fill('#fEnd', '16:15')
        await pg.click('.head-save')
        check('same start and finish caught', 'same time' in await pg.inner_text('#formError'))
        await pg.fill('#fEnd', '15:00')
        await pg.click('.head-save')
        check('22h45 typo caught', '22h 45m' in await pg.inner_text('#formError'))
        await pg.fill('#fEnd', '09:15')  # 17h
        await pg.click('.head-save')
        check('17h caught', '17h 0m' in await pg.inner_text('#formError'))
        await pg.fill('#fEnd', '07:15')  # 15h -> allowed
        await pg.click('.head-save')
        check('15h overnight allowed', 'Typo check' in await pg.inner_text('#todayView'))

        # Day line under chips
        await pg.click('.tab.add')
        await pg.click('#fDays [data-fday="2026-10-14"]')
        check('full date shown under day chips', await pg.inner_text('#dayNote') == 'Wednesday 14 October')

        # Save reachable with a short viewport (stand-in for the keyboard being up)
        await pg.fill('#fName', 'Keyboard test'); await pg.click('#fOwner [data-owner=both]')
        await pg.set_viewport_size({'width':390,'height':500})
        box = await pg.eval_on_selector('.head-save', 'e => { const r = e.getBoundingClientRect(); return [r.top, r.bottom, innerHeight]; }')
        check('header Save visible in a short viewport', 0 <= box[0] and box[1] <= box[2], box)
        await pg.screenshot(path='sheet-short.png')
        await pg.click('.head-save')
        check('header Save saves', 'Keyboard test' in await pg.inner_text('#todayView'))
        await pg.set_viewport_size({'width':390,'height':844})
        check('no page errors', not errs, errs)
        await b.close()
    print('FAILED:', fails if fails else 'none')
asyncio.run(main())
