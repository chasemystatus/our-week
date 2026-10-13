import os
APP_FILE = 'file://' + os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app', 'index.html'))
APP_DEMO = APP_FILE + '?demo=1'
import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await (await b.new_context(viewport={'width':390,'height':844})).new_page()
        await pg.goto(APP_DEMO)
        await pg.click('.card:has-text("Dentist") .body')
        await pg.click('#btnDelete'); await pg.click('#dlgBtns .primary-btn')
        await pg.click('#toastAction')
        t = await pg.eval_on_selector_all('#todayView .card .time', 'els => els.map(e => e.textContent)')
        keys = [x.replace('From ','')[:5] for x in t[2:]]   # first two cards are the untimed ones
        ok = keys == sorted(keys)
        print('PASS' if ok else 'FAIL', 'a deleted entry comes back in time order after Undo', '' if ok else t)
        await b.close()
asyncio.run(main())
