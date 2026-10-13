from livelib import *
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        store = mock.Store()
        # ---------- invite link ----------
        sess, _ = store.issue('toby@example.test')
        ctx, pg = await phone(b, store)
        await pg.goto(URL + '#access_token=%s&expires_in=3600&refresh_token=%s&token_type=bearer&type=invite' % (sess['access_token'], sess['refresh_token']))
        await pg.wait_for_selector('#gSetpw:not([hidden])')
        check('invite link goes to Choose a password', 'Choose a password' in await pg.inner_text('#spTitle') and not await pg.is_visible('#appMain'))
        check('the link\'s tokens are cleared from the address bar', 'access_token' not in pg.url and 'refresh_token' not in pg.url, pg.url)
        await pg.fill('#spPass', 'short'); await pg.fill('#spPass2', 'short'); await pg.click('#spGo')
        check('short password refused', '10 characters' in await pg.inner_text('#spMsg'))
        await pg.fill('#spPass', 'a-long-enough-one'); await pg.fill('#spPass2', 'a-long-enough-two'); await pg.click('#spGo')
        check('mismatch refused', "don't match" in await pg.inner_text('#spMsg'))
        await pg.fill('#spPass', 'aaaaaaaaaa'); await pg.fill('#spPass2', 'aaaaaaaaaa'); await pg.click('#spGo')
        await until(pg, "document.querySelector('#spMsg').textContent.includes('easy to guess')")
        check('weak password gets a plain explanation', True)
        check('nothing was set by the failed tries', store.pw_updates[-1][1] == 'aaaaaaaaaa' and len(store.pw_updates) == 1, store.pw_updates)
        await pg.fill('#spPass', 'a-long-enough-one'); await pg.fill('#spPass2', 'a-long-enough-one'); await pg.click('#spGo')
        await pg.wait_for_selector('#appMain:not([hidden])')
        check('good password saves and opens the planner', store.pw_updates[-1] == ('toby@example.test', 'a-long-enough-one') and 'toby@example.test' in await pg.inner_text('#footWho'), store.pw_updates)
        await pg.reload(); await pg.wait_for_selector('#appMain:not([hidden])')
        check('stays signed in after a reload', await pg.is_visible('#appMain') and not await pg.is_visible('#gSetpw'))

        # ---------- password reset link ----------
        sess, _ = store.issue('eloise@example.test')
        ctx2, pg2 = await phone(b, store)
        await pg2.goto(URL + '#access_token=%s&expires_in=3600&refresh_token=%s&token_type=bearer&type=recovery' % (sess['access_token'], sess['refresh_token']))
        await pg2.wait_for_selector('#gSetpw:not([hidden])')
        check('reset link goes to Choose a new password', 'new password' in await pg2.inner_text('#spTitle'))
        await ctx2.close()

        # ---------- expired / used link ----------
        ctx3, pg3 = await phone(b, store)
        await pg3.goto(URL + '#error=access_denied&error_code=otp_expired&error_description=Email+link+is+invalid+or+has+expired')
        await pg3.wait_for_selector('#gSignin:not([hidden])')
        check('expired link explains and says who to ask', 'expired' in await pg3.inner_text('#siInfo') and 'Ask whoever set this up' in await pg3.inner_text('#siInfo'))
        check('error text cleared from the address bar', 'error' not in pg3.url)

        check('no forgot-password link any more, just a plain note', await pg3.query_selector('#goForgot') is None)
        check('the note tells people who to ask', 'Ask Mum!' in await pg3.inner_text('#gSignin'))

        # ---------- no network at all ----------
        ctx4, pg4 = await phone(b, store)
        store.drop = True
        await pg4.goto(URL); await pg4.wait_for_selector('#gSignin:not([hidden])')
        await pg4.fill('#siEmail', 'eloise@example.test'); await pg4.fill('#siPass', 'correct-horse-1'); await pg4.click('#siGo')
        await until(pg4, "document.querySelector('#siMsg').textContent.length > 0")
        check('no connection: says so, rather than "wrong password"', 'reach' in await pg4.inner_text('#siMsg') and not await pg4.is_visible('#appMain'), await pg4.inner_text('#siMsg'))
        store.drop = False

        # ---------- phone-width look ----------
        for name, pgx in [('signin', pg4), ('setpw', None)]:
            if pgx: await pgx.screenshot(path='live-%s.png' % name)
        check('no page errors', not pg.errs and not pg3.errs and not pg4.errs, pg.errs + pg3.errs + pg4.errs)
        check('nothing blocked by the security policy', not pg.csp and not pg3.csp and not pg4.csp)
        print('\nFAILED:', bad or 'none')
        await b.close()
asyncio.run(main())
