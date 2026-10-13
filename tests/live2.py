from livelib import *
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        store = mock.Store()
        ctxE, E = await login(b, store, 'eloise'); ctxT, T = await login(b, store, 'toby')

        # ---------- a failed save ----------
        store.fail_writes = True
        await add(E, 'Fail me')
        await until(E, "!document.querySelector('#syncBanner').hidden")
        check('banner appears when a save fails', await E.is_visible('#syncBanner') and 'hasn\'t saved' in await E.inner_text('#syncBanner'))
        check('pill says Not saved', 'Not saved' in await E.inner_text('#saveState'))
        check('banner has a Try again button and a plain reason', await E.is_visible('#syncRetry') and 'moment' in await E.inner_text('#syncDetail'), await E.inner_text('#syncDetail'))
        check('the entry stays on screen', 'Fail me' in await visible_text(E))
        check('and is not in the database', 'Fail me' not in names(store))
        await E.screenshot(path='live-fail.png')
        # the other phone adds something meanwhile, then Eloise's phone comes back to the foreground
        store.fail_writes = False
        await add(T, 'From Toby'); await saved(T)
        store.fail_writes = True
        await poke(E); await E.wait_for_timeout(700)
        check('unsaved change is not wiped by a refresh', 'Fail me' in await visible_text(E))
        check('banner still showing', await E.is_visible('#syncBanner'))
        # sign out with unsaved changes asks first
        await E.evaluate("window.scrollTo(0, 99999)"); await E.click('#btnSignOut')
        check('sign-out warns about unsaved changes', await E.is_visible('#dlg') and 'unsaved' in await E.inner_text('#dlgTitle'))
        await E.click('#dlg >> text=Stay signed in')
        check('staying signed in keeps the planner and the unsaved entry', not await E.is_visible('#dlg') and await E.is_visible('#appMain') and 'Fail me' in await visible_text(E))
        # fix it and retry
        store.fail_writes = False
        await E.click('#syncRetry'); await saved(E)
        check('Try again saves it', 'Fail me' in names(store) and not await E.is_visible('#syncBanner'))
        await poke(E); await until(E, "document.querySelector('#todayView').innerText.includes('From Toby')")
        check('afterwards the other phone\'s entry arrives too', True)
        check('and nothing was lost or duplicated', names(store).count('Fail me') == 1 and names(store).count('From Toby') == 1, names(store))

        # ---------- the connection drops ----------
        store.drop = True
        await add(E, 'Offline add')
        await until(E, "!document.querySelector('#syncBanner').hidden")
        check('dropped connection shows the same banner', 'Offline add' in await visible_text(E) and 'Offline add' not in names(store))
        store.drop = False
        await E.click('#syncRetry'); await saved(E)
        check('saves once the connection is back', 'Offline add' in names(store))

        # ---------- sign-in runs out mid-session ----------
        store.invalidate_next = True
        await add(E, 'After expiry'); await saved(E)
        check('an expired token is renewed quietly and the save goes through', 'After expiry' in names(store))
        store.invalidate_next = True; store.refresh_broken = True
        await add(E, 'Cannot renew')
        await until(E, "!document.querySelector('#syncBanner').hidden")
        check('if it cannot be renewed the banner says so', 'sign-in has run out' in await E.inner_text('#syncDetail') and 'Cannot renew' not in names(store), await E.inner_text('#syncDetail'))
        store.refresh_broken = False

        # ---------- undo never overwrites the other phone ----------
        await E.reload(); await E.wait_for_selector('#appMain:not([hidden])')
        await until(E, "document.querySelector('#todayView').innerText.includes('From Toby')")
        await add(E, 'Temp A', 'eloise'); await saved(E)
        await E.click('.card:has-text("Temp A") .body'); await E.click('#btnDelete'); await E.click('#dlgBtns .primary-btn'); await saved(E)
        check('delete is stored', 'Temp A' not in names(store))
        await add(T, 'Added by Toby meanwhile', 'toby'); await saved(T)
        await poke(E); await until(E, "document.querySelector('#todayView').innerText.includes('Added by Toby meanwhile')")
        await E.click('#toastAction')   # may have gone if slow; handled below
        await saved(E)
        check('Undo brings the entry back', 'Temp A' in names(store), names(store))
        check('and keeps what the other phone added', 'Added by Toby meanwhile' in names(store), names(store))

        # ---------- someone deleted it while the sheet was open ----------
        await E.click('.card:has-text("From Toby") .body')
        await T.click('.card:has-text("From Toby") .body'); await T.click('#btnDelete'); await T.click('#dlgBtns .primary-btn'); await saved(T)
        await E.fill('#fName', 'From Toby (renamed)'); await E.click('.head-save'); await saved(E)
        check('editing something deleted elsewhere adds it again instead of losing the edit', 'From Toby (renamed)' in names(store) and 'From Toby' not in names(store), names(store))

        check('no page errors', not E.errs and not T.errs, E.errs + T.errs)
        check('nothing blocked by the security policy', not E.csp and not T.csp, E.csp + T.csp)
        print('\nFAILED:', bad or 'none')
        await b.close()
asyncio.run(main())
