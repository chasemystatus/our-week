import os
APP_FILE = 'file://' + os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app', 'index.html'))
APP_DEMO = APP_FILE + '?demo=1'
import asyncio
from playwright.async_api import async_playwright
from fake import FAKE, fake
URL = APP_DEMO
fails = []
def check(label, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + label + (' ' + str(extra) if (extra != '' and not cond) else ''))
    if not cond: fails.append(label)

async def newpage(b, init=FAKE, w=390, h=844, tz=None):
    kw = dict(viewport={'width': w, 'height': h}, device_scale_factor=2, locale='en-GB')
    if tz: kw['timezone_id'] = tz
    pg = await (await b.new_context(**kw)).new_page()
    await pg.add_init_script(init); await pg.goto(URL)
    return pg

async def txt(pg, sel): return (await pg.inner_text(sel)).strip()

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await newpage(b)
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))

        # --- opening state
        check('opens on Today view', await txt(pg, '#dateTitle') == 'Monday 12 October')
        check('Today badge shown', await pg.is_visible('#todayBadge'))
        check('week range', await txt(pg, '#weekLabel') == '12–18 October', await txt(pg, '#weekLabel'))
        check('Back to today hidden on today', not await pg.is_visible('#jump'))

        # --- next / previous week
        await pg.click('[data-nav="1"]')
        check('next week heading', await txt(pg, '#dateTitle') == 'Monday 19 October', await txt(pg, '#dateTitle'))
        check('next week range', await txt(pg, '#weekLabel') == '19–25 October')
        check('next week shows its own entry', 'Eye test' in await txt(pg, '#todayView') and 'Library books due' not in await txt(pg, '#todayView'))
        check('Back to today appears', await pg.is_visible('#jump'))
        check('Today badge hidden on another day', not await pg.is_visible('#todayBadge'))
        await pg.click('[data-jump]')
        check('Back to today works', await txt(pg, '#dateTitle') == 'Monday 12 October' and not await pg.is_visible('#jump'))
        await pg.click('[data-nav="-1"]')
        check('previous week reachable with its entries', 'Garden centre shift' in await txt(pg, '#todayView') and 'Book boiler service' in await txt(pg, '#todayView'))
        check('previous week range', await txt(pg, '#weekLabel') == '5–11 October')
        await pg.click('[data-nav="-1"]'); await pg.click('[data-nav="-1"]'); await pg.click('[data-nav="-1"]')
        check('several weeks back still fine', await txt(pg, '#weekLabel') == '14–20 September', await txt(pg, '#weekLabel'))
        await pg.click('[data-view=today]')
        check('Today tab returns to real today', await txt(pg, '#dateTitle') == 'Monday 12 October')

        # --- Week view
        await pg.click('[data-view=week]')
        check('week title', await txt(pg, '#dateTitle') == 'This week')
        check('seven day sections', await pg.locator('.daysec').count() == 7)
        check('strip hidden in week view', not await pg.is_visible('#days'))
        check('Monday section has all 8 entries', await pg.locator('.daysec').nth(0).locator('.card').count() == 8)
        check('empty day is blank apart from its heading', (await txt(pg, '.daysec:nth-child(7)')).strip() == 'Sun 18 Oct')
        check('no per-day Add buttons', await pg.locator('.mini-add, [data-addday]').count() == 0)
        check('Today tag on Monday', 'today' in (await txt(pg, '.daysec.is-today .daylink')).lower() and 'Mon 12 Oct' in await txt(pg, '.daysec.is-today .daylink'))
        check('week note', await txt(pg, '#filterNote') == "Eloise and Toby's week, including joint entries")
        check('close shift shown in week', '17:00–close' in await txt(pg, '#weekView'))
        check('after-midnight shift shown on the day it starts only',
              '22:00–02:00' in await txt(pg, '.daysec:nth-child(5)') and 'next day' not in await txt(pg, '.daysec:nth-child(5)') and '22:00–02:00' not in await txt(pg, '.daysec:nth-child(6)'))
        await pg.click('#filter [data-who=eloise]')
        mon = await txt(pg, '.daysec:nth-child(1)')
        check('Eloise week filter keeps hers and joint, hides Toby-only', 'Café shift' in mon and 'Library books due' in mon and 'Dentist' not in mon, mon[:120])
        check('Eloise week note', await txt(pg, '#filterNote') == "Eloise's week, including joint entries")
        await pg.click('#filter [data-who=all]')
        # complete and undo from the week view
        await pg.click('.daysec:nth-child(1) [data-toggle="4"]')
        check('mark done from week view', 'Done ✓' in await txt(pg, '.daysec:nth-child(1) .card[data-id="4"]'))
        await pg.click('.daysec:nth-child(1) [data-toggle="4"]')
        check('undo from week view', 'To do' in await txt(pg, '.daysec:nth-child(1) .card[data-id="4"]'))
        # add to a particular day
        await pg.click('.tab.add')
        await pg.click('[data-fday="2026-10-14"]')
        await pg.fill('#fName', 'Parcel pickup'); await pg.click('#fOwner [data-owner=both]'); await pg.click('.head-save')
        check('new entry lands in Wednesday section', 'Parcel pickup' in await txt(pg, '.daysec:nth-child(3)'))
        check('still in week view after saving', await pg.is_visible('#weekView'))
        # edit and delete from week view
        await pg.click('.daysec:nth-child(3) .card:has-text("Parcel pickup") .body')
        check('edit opens from week view', await txt(pg, '#sheetTitle') == 'Edit entry')
        await pg.click('#btnDelete'); await pg.click('#dlgBtns .primary-btn')
        check('delete from week view', 'Parcel pickup' not in await txt(pg, '#weekView'))
        await pg.click('#toastAction')
        check('undo delete from week view', 'Parcel pickup' in await txt(pg, '.daysec:nth-child(3)'))
        # open a day
        await pg.click('[data-goday="2026-10-15"]')
        check('tapping a day opens it in Today view', await txt(pg, '#dateTitle') == 'Thursday 15 October' and await pg.is_visible('#todayView'))
        # week arrows in week view
        await pg.click('[data-view=week]'); await pg.click('[data-nav="1"]')
        check('week view next week title', await txt(pg, '#dateTitle') == 'Next week')
        check('week view next week content', 'Eye test' in await txt(pg, '#weekView'))
        check('jump visible in week view', await pg.is_visible('#jump'))
        await pg.click('[data-nav="1"]')
        check('further ahead titled by date', await txt(pg, '#dateTitle') == 'Week of 26 October', await txt(pg, '#dateTitle'))
        await pg.click('[data-jump]')
        check('jump returns to this week', await txt(pg, '#dateTitle') == 'This week')

        # --- sideways overflow in week view at phone widths
        for w in (320, 375, 390, 430):
            await pg.set_viewport_size({'width': w, 'height': 844})
            sw = await pg.evaluate('[document.documentElement.scrollWidth, document.documentElement.clientWidth]')
            check('week view no overflow at %d' % w, sw[0] == sw[1], sw)
        await pg.set_viewport_size({'width': 390, 'height': 844})
        await pg.screenshot(path='week-phone-top.png')
        await pg.add_style_tag(content='.bar{position:static!important}.app{padding-bottom:16px!important}')
        await pg.screenshot(path='week-phone-full.png', full_page=True)
        check('no page errors', not errs, errs)
        await pg.context.close()

        # --- desktop width
        pg = await newpage(b, w=1280, h=900)
        await pg.click('[data-view=week]')
        lefts = await pg.eval_on_selector_all('.daysec', 'els => [...new Set(els.map(e => Math.round(e.getBoundingClientRect().left)))]')
        check('desktop shows the whole week across', len(lefts) == 7, lefts)
        sw = await pg.evaluate('[document.documentElement.scrollWidth, document.documentElement.clientWidth]')
        check('desktop no overflow', sw[0] == sw[1], sw)
        await pg.screenshot(path='week-desktop.png')
        await pg.click('[data-view=today]')
        await pg.screenshot(path='today-desktop.png')
        await pg.context.close()

        # --- month boundary: week 26 Oct to 1 Nov
        pg = await newpage(b, fake('2026-10-28T11:00:00Z'))
        check('month-crossing range', await txt(pg, '#weekLabel') == '26 October – 1 November', await txt(pg, '#weekLabel'))
        chips = await pg.eval_on_selector_all('#days .day', 'els => els.map(e => e.innerText.replace(/\\n/g," "))')
        check('first chip and the 1st carry the month', 'Oct' in chips[0] and 'Nov' in chips[6] and 'Oct' not in chips[3], chips)
        await pg.click('.tab.add')
        chips2 = await pg.eval_on_selector_all('#fDays button', 'els => els.map(e => e.innerText.replace(/\\n/g," "))')
        check('Add sheet chips carry the month too', 'Nov' in chips2[6], chips2)
        await pg.click('#fDays [data-fday="2026-11-01"]')
        check('Add sheet date line across month end', await txt(pg, '#dayNote') == 'Sunday 1 November')
        await pg.context.close()

        # --- year boundary
        pg = await newpage(b, fake('2026-12-30T11:00:00Z'))
        check('year-crossing range', await txt(pg, '#weekLabel') == '28 December 2026 – 3 January 2027', await txt(pg, '#weekLabel'))
        await pg.click('[data-nav="1"]')
        check('next week after year end', await txt(pg, '#weekLabel') == '4–10 January 2027', await txt(pg, '#weekLabel'))
        await pg.context.close()

        # --- clocks go back on Sunday 25 October 2026 (London)
        pg = await newpage(b, fake('2026-10-24T23:30:00Z'))   # 00:30 BST on Sunday 25th
        check('just after midnight BST counts as the 25th', await txt(pg, '#dateTitle') == 'Sunday 25 October', await txt(pg, '#dateTitle'))
        days = await pg.eval_on_selector_all('#days .day', 'els => els.map(e => e.dataset.day)')
        check('clock-change week has seven consecutive dates', days == ['2026-10-19','2026-10-20','2026-10-21','2026-10-22','2026-10-23','2026-10-24','2026-10-25'], days)
        await pg.click('[data-nav="1"]')
        check('next week after clock change keeps the weekday (Sunday 1 November)', await txt(pg, '#dateTitle') == 'Sunday 1 November' and await txt(pg, '#weekLabel') == '26 October – 1 November', await txt(pg, '#dateTitle'))
        await pg.context.close()
        pg = await newpage(b, fake('2026-07-01T23:30:00Z'))   # 00:30 BST on 2 July
        check('late UTC evening is already tomorrow in London', await txt(pg, '#dateTitle') == 'Thursday 2 July', await txt(pg, '#dateTitle'))
        await pg.context.close()

        # --- device set to another time zone still uses London
        pg = await newpage(b, fake('2026-10-12T05:00:00Z'), tz='America/Los_Angeles')   # still 11 Oct in LA
        check('device in Los Angeles still shows London date', await txt(pg, '#dateTitle') == 'Monday 12 October', await txt(pg, '#dateTitle'))
        await pg.context.close()
        await b.close()
    print('FAILED:', fails if fails else 'none')
asyncio.run(main())
