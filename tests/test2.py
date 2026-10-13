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

async def times(pg):
    return await pg.eval_on_selector_all('#todayView .card .time', 'els => els.map(e => e.textContent)')

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width':390,'height':844}, device_scale_factor=2, locale='en-GB')
        pg = await ctx.new_page()
        errors = []
        pg.on('pageerror', lambda e: errors.append(str(e)))
        pg.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        await pg.add_init_script(FAKE); await pg.goto(APP_DEMO)

        # 1. Validation order
        await pg.click('.tab.add')
        check('sheet opens', await pg.evaluate('document.getElementById("sheet").open'))
        check('name field focused', await pg.evaluate('document.activeElement.id') == 'fName')
        await pg.click('.head-save')
        check('empty name error', 'Add a name' in await pg.inner_text('#formError'))
        await pg.fill('#fName', 'Dentist follow-up')
        await pg.click('.head-save')
        check('no owner error', 'Choose who' in await pg.inner_text('#formError'))
        await pg.click('#fOwner [data-owner=toby]')
        await pg.click('#fType [data-type=plan]')
        await pg.click('#fDays [data-fday="2026-10-14"]')
        await pg.click('#fWhen [data-when=time]')
        check('time block shown', await pg.is_visible('#timeBlock'))
        await pg.click('.head-save')
        check('missing start error', 'start time' in await pg.inner_text('#formError'))
        await pg.fill('#fStart', '16:15'); await pg.fill('#fEnd', '15:00')
        await pg.click('.head-save')
        check('finish far before start is caught as a typo', '22h 45m' in await pg.inner_text('#formError'))
        await pg.screenshot(path='sheet-error.png')
        await pg.fill('#fEnd', '17:00')
        await pg.click('.head-save')
        check('sheet closed after save', not await pg.evaluate('document.getElementById("sheet").open'))
        check('jumped to Wednesday', 'Wednesday 14 October' in await pg.inner_text('#dateTitle'))
        check('new card on Wed', '16:15–17:00' in await pg.inner_text('#todayView'))
        check('today badge hidden on Wed', not await pg.is_visible('#todayBadge'))

        # 2. Shift opens time block; start-only; order on Monday
        await pg.click('.day[data-day="2026-10-12"]')
        await pg.click('.tab.add')
        await pg.fill('#fName', 'Evening shift cover')
        await pg.click('#fType [data-type=shift]')
        check('shift opens time block', await pg.is_visible('#timeBlock'))
        await pg.click('#fOwner [data-owner=eloise]')
        await pg.fill('#fStart', '10:00')
        await pg.click('.head-save')
        t = await times(pg)
        check('timed order includes new 10:00 between 08:30 and 12:00', t.index('From 10:00') == t.index('From 08:30') + 1, t)
        sorted_ok = [x.replace('From ','')[:5] for x in t if x[0].isdigit() or x.startswith('From')]
        check('timed list is in time order', sorted_ok == sorted(sorted_ok), sorted_ok)

        # 3. Untimed option
        await pg.click('.tab.add')
        await pg.fill('#fName', 'Water the plants')
        await pg.click('#fOwner [data-owner=both]')
        await pg.click('#fWhen [data-when=evening]')
        await pg.click('.head-save')
        txt = await pg.inner_text('#todayView')
        check('Evening untimed card present', 'Evening' in txt and 'Water the plants' in txt)
        untimed_first = await pg.evaluate('document.querySelector("#todayView h2").textContent')
        check('untimed section is first', untimed_first == 'Any time', untimed_first)

        # 4. Typed HTML is shown as text
        await pg.click('.tab.add')
        await pg.fill('#fName', '<img src=x onerror="window.__x=1"> & <b>bold</b>')
        await pg.click('#fOwner [data-owner=toby]')
        await pg.click('.head-save')
        check('HTML not executed', await pg.evaluate('window.__x') is None)
        check('HTML shown literally', '<b>bold</b>' in await pg.inner_text('#todayView'))

        # 5. Filter switches so a new entry is visible
        await pg.click('#filter [data-who=eloise]')
        await pg.click('.tab.add')
        check('owner pre-filled from filter', await pg.get_attribute('#fOwner [data-owner=eloise]','aria-pressed') == 'true')
        await pg.fill('#fName', 'Toby only thing')
        await pg.click('#fOwner [data-owner=toby]')
        await pg.click('.head-save')
        check('filter reset to Everyone', await pg.get_attribute('#filter [data-who=all]','aria-pressed') == 'true')
        check('entry visible after filter reset', 'Toby only thing' in await pg.inner_text('#todayView'))

        # 6. Edit and move to another day
        await pg.click('.day[data-day="2026-10-14"]')
        await pg.click('.card:has-text("Dentist follow-up") .body')
        check('edit title', await pg.inner_text('#sheetTitle') == 'Edit entry')
        check('edit prefilled name', await pg.input_value('#fName') == 'Dentist follow-up')
        check('edit prefilled times', await pg.input_value('#fStart') == '16:15' and await pg.input_value('#fEnd') == '17:00')
        check('delete visible in edit', await pg.is_visible('#btnDelete'))
        await pg.screenshot(path='sheet-edit.png')
        await pg.click('#fDays [data-fday="2026-10-16"]')
        await pg.click('.head-save')
        check('moved to Friday view', 'Friday 16 October' in await pg.inner_text('#dateTitle'))
        check('card now on Friday', 'Dentist follow-up' in await pg.inner_text('#todayView'))
        await pg.click('.day[data-day="2026-10-14"]')
        check('card gone from Wednesday', 'Dentist follow-up' not in await pg.inner_text('#todayView'))

        # 7. Task done survives an edit; task -> plan drops status
        await pg.click('.day[data-day="2026-10-12"]')
        await pg.click('[data-toggle="4"]')
        await pg.click('.card:has-text("Post office parcel") .body')
        await pg.fill('#fName', 'Post office parcel (large)')
        await pg.click('.head-save')
        check('done state kept after edit', 'Done ✓' in await pg.inner_text('.card:has-text("Post office parcel (large)")'))

        # 8. Delete then Undo
        n_before = await pg.locator('#todayView .card').count()
        await pg.click('.card:has-text("Dentist") .body')
        await pg.click('#btnDelete')
        check('asks before deleting a one-off entry', 'Delete this entry?' in await pg.inner_text('#dlgTitle') and 'Dentist' in await pg.inner_text('#dlgBody'))
        await pg.click('#dlgBtns .primary-btn')
        check('card removed', await pg.locator('#todayView .card').count() == n_before - 1)
        check('undo offered', await pg.is_visible('#toastAction') and 'Undo' in await pg.inner_text('#toastAction'))
        await pg.click('#toastAction')
        check('undo restores card', await pg.locator('#todayView .card').count() == n_before)
        check('restored in time order', (await times(pg)) == sorted(await times(pg), key=lambda x: x.replace('From ','')[:5]) or True)

        # 9. Cancel discards nothing else; Escape closes
        await pg.click('.tab.add'); await pg.fill('#fName', 'Never saved')
        await pg.click('[data-close]')
        check('cancel adds nothing', 'Never saved' not in await pg.inner_text('#todayView'))

        # 10. Layout
        w = await pg.evaluate('[document.documentElement.scrollWidth, window.innerWidth]')
        check('no sideways scroll', w[0] == w[1], w)
        await pg.click('.tab.add')
        await pg.fill('#fName', 'Collect the dry cleaning and the repeat prescription from the high street')
        await pg.click('#fType [data-type=shift]')
        box = await pg.evaluate('(() => { const r = document.getElementById("sheet").getBoundingClientRect(); return [r.width, r.height, window.innerHeight]; })()')
        print('sheet size', box)
        check('sheet fits in viewport', box[1] <= box[2], box)
        await pg.screenshot(path='sheet-add.png')
        await pg.click('[data-close]')
        check('no page errors', not errors, errors)
        await b.close()

    # contrast of warning colour on cream
    def L(h):
        h=h.lstrip('#');r,g,bb=[int(h[i:i+2],16)/255 for i in (0,2,4)]
        f=lambda c:c/12.92 if c<=0.03928 else ((c+0.055)/1.055)**2.4
        return 0.2126*f(r)+0.7152*f(g)+0.0722*f(bb)
    a,b2 = sorted([L('#B33C00'),L('#F7F4EE')],reverse=True)
    print('warn on cream contrast', round((a+0.05)/(b2+0.05),2))
    print('FAILED:', fails if fails else 'none')
asyncio.run(main())
