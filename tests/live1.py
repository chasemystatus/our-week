import asyncio, json, re
from playwright.async_api import async_playwright
from fake import FAKE
from helpers import until, saved
import mock
URL = 'http://127.0.0.1:8765/index.html'
bad = []
def check(n, ok, extra=''):
    print('PASS' if ok else 'FAIL', n, extra if not ok else '')
    if not ok: bad.append(n)

async def phone(b, store):
    ctx = await b.new_context(viewport={'width': 390, 'height': 800}, locale='en-GB', accept_downloads=True)
    await ctx.add_init_script(FAKE)
    await mock.attach(ctx, store)
    pg = await ctx.new_page()
    pg.errs = []; pg.csp = []
    pg.on('pageerror', lambda e: pg.errs.append(str(e)))
    pg.on('console', lambda m: pg.csp.append(m.text) if 'Content Security' in m.text or 'Refused' in m.text else None)
    return ctx, pg

async def sign_in(pg, email, pw):
    await pg.fill('#siEmail', email); await pg.fill('#siPass', pw); await pg.click('#siGo')

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        store = mock.Store()
        ctxE, E = await phone(b, store)
        await E.goto(URL)
        await E.wait_for_selector('#gSignin:not([hidden])')
        # ---- signed out ----
        check('sign-in screen shown first', await E.is_visible('#gSignin'))
        check('planner hidden when signed out', not await E.is_visible('#appMain') and not await E.is_visible('.bar'))
        check('no data requests while signed out', not any('/rest/v1/' in x[1] for x in store.log), store.log)
        check('page text has no entries', 'Dentist' not in await E.inner_text('body'))
        await sign_in(E, 'eloise@example.test', 'wrong-password-0')
        await until(E, "document.querySelector('#siMsg').textContent.length>0")
        check('wrong password refused with plain message', "isn't right" in await E.inner_text('#siMsg') and not await E.is_visible('#appMain'))
        check('password box cleared after a wrong try', await E.input_value('#siPass') == '')
        # ---- stranger (valid account, not on the list) ----
        ctxS, S = await phone(b, store)
        await S.goto(URL); await S.wait_for_selector('#gSignin:not([hidden])')
        await sign_in(S, 'stranger@example.test', 'not-on-the-list-3')
        await S.wait_for_selector('#gDenied:not([hidden])')
        check('account not on the list is turned away', await S.is_visible('#gDenied') and not await S.is_visible('#appMain'))
        check('stranger never asked for entries', not any(x[0] == 'GET' and '/rest/v1/entries' in x[1] for x in store.log[-6:]))
        await ctxS.close()
        # ---- Eloise signs in ----
        await sign_in(E, 'eloise@example.test', 'correct-horse-1')
        await E.wait_for_selector('#appMain:not([hidden])')
        check('planner shows after sign-in', await E.is_visible('#appMain') and await E.is_visible('.bar'))
        check('empty to start', 'Nothing planned' in await E.inner_text('#todayView'))
        check('no demo banner in the real app', not await E.is_visible('#demoNote'))
        check('footer says who is signed in', 'eloise@example.test' in await E.inner_text('#footWho'))
        await E.wait_for_timeout(600)
        check('live updates connected', 'straight away' in await E.inner_text('#footLive'), await E.inner_text('#footLive'))
        # ---- add an entry ----
        await E.click('.tab.add'); await E.fill('#fName', 'Dentist check-up'); await E.click('#fOwner [data-owner=eloise]')
        await E.click('[data-when=time]'); await E.fill('#fStart', '09:30'); await E.click('.head-save')
        await saved(E)
        check('shows Saved', True)
        rows = list(store.t['entries'].values())
        check('one row stored', len(rows) == 1, rows)
        r = rows[0] if rows else {}
        check('row has the right fields', r.get('name') == 'Dentist check-up' and r.get('owner') == 'eloise' and r.get('type') == 'task' or r.get('type') in ('task','plan','shift'))
        check('time stored', r.get('start_time') == '09:30' and r.get('date') == '2026-10-12', r)
        check('id is a uuid', bool(re.match(r'^[0-9a-f-]{36}$', r.get('id', ''))), r.get('id'))
        # ---- Toby's phone ----
        ctxT, T = await phone(b, store)
        await T.goto(URL); await T.wait_for_selector('#gSignin:not([hidden])')
        await sign_in(T, 'toby@example.test', 'battery-staple-2')
        await T.wait_for_selector('#appMain:not([hidden])')
        check('Toby sees Eloise\'s entry', 'Dentist check-up' in await T.inner_text('#todayView'))
        # ---- Toby adds a joint task; appears on Eloise without reload ----
        await T.click('.tab.add'); await T.fill('#fName', 'Pay the water bill'); await T.click('#fOwner [data-owner=both]'); await T.click('.head-save')
        await saved(T)
        await until(E, "document.querySelector('#todayView').innerText.includes('Pay the water bill')")
        check('Eloise sees it without reloading', True)
        # ---- Eloise completes the joint task for both ----
        await E.click('.card:has-text("Pay the water bill") [data-toggle]')
        await saved(E)
        await until(T, "[...document.querySelectorAll('.card')].some(c => c.innerText.includes('Pay the water bill') && c.innerText.includes('Done'))")
        check('joint task done for both, seen on Toby\'s phone', True)
        nt = [r for r in store.t['entries'].values() if r['name'] == 'Pay the water bill']
        check('stored once', len(nt) == 1 and nt[0]['done'] is True and nt[0]['owner'] == 'both', nt)
        # ---- CSP + errors ----
        check('no page errors (E)', not E.errs, E.errs); check('no page errors (T)', not T.errs, T.errs)
        check('nothing blocked by the security policy', not E.csp and not T.csp, E.csp + T.csp)
        await E.screenshot(path='live-eloise.png')
        # ---- sign out ----
        await E.evaluate("window.scrollTo(0, 99999)")
        await E.click('#btnSignOut')
        check('sign-out asks first', await E.is_visible('#dlg') and 'Sign out?' in await E.inner_text('#dlgTitle'))
        await E.click('#dlgBtns button:has-text("Stay signed in")'); await E.wait_for_timeout(200)
        check('staying signed in keeps the planner', await E.is_visible('#appMain') and not await E.is_visible('#dlg'))
        await E.click('#btnSignOut'); await E.click('#dlgBtns button:text-is("Sign out")')
        await E.wait_for_selector('#gSignin:not([hidden])')
        check('signed out shows the sign-in screen', await E.is_visible('#gSignin') and not await E.is_visible('#appMain'))
        check('entries gone from the page', 'Dentist' not in await E.inner_text('body') and 'water bill' not in await E.inner_text('body'))
        stored = await E.evaluate("JSON.stringify(Object.assign({}, localStorage))")
        check('no session left on this phone', 'access_token' not in stored, stored[:120])
        await E.reload(); await E.wait_for_selector('#gSignin:not([hidden])')
        check('still signed out after reload', await E.is_visible('#gSignin'))
        check('Toby still signed in (sign-out only this device)', await T.is_visible('#appMain'))
        print('\nFAILED:', bad or 'none')
        await b.close()
asyncio.run(main())
