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

async def phone(b, store, w=390, h=800):
    ctx = await b.new_context(viewport={'width': w, 'height': h}, locale='en-GB', accept_downloads=True)
    await ctx.add_init_script(FAKE)
    await mock.attach(ctx, store)
    pg = await ctx.new_page()
    pg.errs = []; pg.csp = []
    pg.on('pageerror', lambda e: pg.errs.append(str(e)))
    pg.on('console', lambda m: pg.csp.append(m.text) if 'Content Security' in m.text or 'Refused' in m.text else None)
    return ctx, pg

async def login(b, store, who='eloise', w=390, h=800):
    pw = {'eloise': 'correct-horse-1', 'toby': 'battery-staple-2'}[who]
    ctx, pg = await phone(b, store, w, h)
    await pg.goto(URL); await pg.wait_for_selector('#gSignin:not([hidden])')
    await pg.fill('#siEmail', who + '@example.test'); await pg.fill('#siPass', pw); await pg.click('#siGo')
    await pg.wait_for_selector('#appMain:not([hidden])')
    return ctx, pg

async def add(pg, name, owner='both', when=None, rep=None, task=True):
    await pg.click('.tab.add'); await pg.fill('#fName', name); await pg.click('#fOwner [data-owner=%s]' % owner)
    if when:
        await pg.click('[data-when=time]'); await pg.fill('#fStart', when)
    if rep:
        await pg.click('#repToggle'); await pg.click('[data-rep=%s]' % rep)
    await pg.click('.head-save')

def names(store, tb='entries'): return sorted(r['name'] for r in store.t[tb].values())
async def visible_text(pg): return await pg.inner_text('#todayView')
async def poke(pg):
    """Pretend the phone has just come back to the foreground."""
    await pg.evaluate("() => { document.dispatchEvent(new Event('visibilitychange')); window.dispatchEvent(new Event('focus')); }")
