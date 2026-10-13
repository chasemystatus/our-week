from livelib import *
import tempfile, os, uuid as U
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        store = mock.Store()
        ctxE, E = await login(b, store, 'eloise'); ctxT, T = await login(b, store, 'toby')

        # ---------- repeating entries over the database ----------
        await add(E, 'Water plants', 'both', rep='weekly'); await saved(E)
        await add(E, 'One-off dentist', 'eloise'); await saved(E)
        S = list(store.t['series'].values())
        check('repeating entry stored once as a series', len(S) == 1 and S[0]['name'] == 'Water plants' and S[0]['rule'] == {'kind': 'weeks', 'every': 1}, S)
        check('series starts today and has no end', S and S[0]['from_date'] == '2026-10-12' and S[0]['last_date'] is None, S)
        check('the one-off is a separate plain entry', names(store) == ['One-off dentist'], names(store))
        await E.click('[data-nav="1"]'); await T.click('[data-nav="1"]')
        await until(T, "document.querySelector('#todayView').innerText.includes('Water plants')")
        check('next week: Toby sees the repeating entry', True)
        check('next week: the one-off is not carried forward', 'One-off dentist' not in await visible_text(T) and 'One-off dentist' not in await visible_text(E))
        # change this week only
        await E.click('.card:has-text("Water plants") .body'); await E.fill('#fName', 'Water plants (holiday cover)'); await E.click('.head-save')
        await E.click('[data-scope=one]'); await saved(E)
        X = list(store.t['exceptions'].values())
        check('one-week change stored as an exception, series untouched', len(X) == 1 and X[0]['data']['name'] == 'Water plants (holiday cover)' and list(store.t['series'].values())[0]['name'] == 'Water plants', X)
        await until(T, "document.querySelector('#todayView').innerText.includes('holiday cover')")
        check('Toby sees the one-week change', True)
        # Toby ticks the joint repeating task for both
        await T.click('.card:has-text("holiday cover") [data-toggle]'); await saved(T)
        await until(E, "[...document.querySelectorAll('.card')].some(c => c.innerText.includes('holiday cover') && c.innerText.includes('Done'))")
        check('tick on a repeating joint task reaches the other phone', True)
        await T.click('[data-nav="1"]'); await E.click('[data-nav="1"]')
        check('following week is a fresh to-do', 'To do' in await visible_text(E) and 'Done' not in await visible_text(E))
        # delete this and later weeks
        await E.click('.card:has-text("Water plants") .body'); await E.click('#btnDelete'); await E.click('[data-scope=future]'); await saved(E)
        S = list(store.t['series'].values())
        check('ending a series from here sets its last day', len(S) == 1 and S[0]['last_date'] == '2026-10-25', S)
        await E.click('[data-nav="-1"]'); await E.click('[data-nav="-1"]')
        check('this week still has it', 'Water plants' in await visible_text(E))
        # deleting from the first week removes the series and its exceptions
        await E.click('.card:has-text("Water plants") .body'); await E.click('#btnDelete'); await E.click('[data-scope=future]'); await saved(E)
        check('deleting from the very first week removes the series and its changes', not store.t['series'] and not store.t['exceptions'], (store.t['series'], store.t['exceptions']))

        # ---------- backup ----------
        await add(E, 'Weekly bins', 'toby', rep='fortnight'); await add(E, 'Pay rent', 'both'); await saved(E)
        await E.evaluate("window.scrollTo(0, 99999)")
        async with E.expect_download() as dl: await E.click('#btnBackup')
        d = await dl.value
        check('backup file has a dated name', re.match(r'our-week-backup-2026-10-12\.json', d.suggested_filename), d.suggested_filename)
        path = await d.path(); data = json.load(open(path))
        check('backup holds everything', len(data['entries']) == len(store.t['entries']) and len(data['series']) == len(store.t['series']) and data['app'] == 'our-week', {k: len(v) for k, v in data.items() if isinstance(v, list)})
        # ---------- restore: bad files change nothing ----------
        before = json.dumps({k: sorted(map(json.dumps, v.values())) for k, v in store.t.items()})
        tmp = tempfile.mkdtemp()
        def put(name, obj):
            fp = os.path.join(tmp, name); open(fp, 'w').write(obj if isinstance(obj, str) else json.dumps(obj)); return fp
        for label, obj in [('not json', 'hello'), ('wrong app', {'app': 'other', 'version': 1, 'entries': [], 'series': [], 'exceptions': []}),
                           ('bad owner', {**data, 'entries': [{**data['entries'][0], 'owner': 'nobody'}]}),
                           ('script in a time', {**data, 'entries': [{**data['entries'][0], 'start': '<b>'}]}),
                           ('bad rule', {**data, 'series': [{**data['series'][0], 'rule': {'kind': 'weeks', 'every': 0}}]}),
                           ('orphan change', {**data, 'exceptions': [{'sid': 'nope', 'orig': '2026-10-12', 'skip': True}]}),
                           ('bad date', {**data, 'entries': [{**data['entries'][0], 'date': '2026-02-30'}]})]:
            await E.evaluate("() => { document.querySelector('#restoreFile').value = ''; }"); await E.set_input_files('#restoreFile', put('x.json', obj))
            await until(E, "document.querySelector('#dlg').open")
            ok = 'Couldn\'t use that file' in await E.inner_text('#dlgTitle')
            await E.click('#dlg >> text=OK')
            check('rejects: ' + label, ok)
        await E.wait_for_timeout(300)
        after = json.dumps({k: sorted(map(json.dumps, v.values())) for k, v in store.t.items()})
        check('bad files changed nothing', before == after)
        # ---------- restore: a good, edited backup ----------
        edited = {**data, 'entries': [e for e in data['entries'] if e['name'] != 'Pay rent'] + [{'id': 5, 'date': '2026-10-13', 'name': 'Restored from demo-style id', 'owner': 'eloise', 'type': 'plan', 'start': '10:00'}]}
        await E.evaluate("() => { document.querySelector('#restoreFile').value = ''; }"); await E.set_input_files('#restoreFile', put('good.json', edited))
        await until(E, "document.querySelector('#dlg').open")
        check('restore asks first and says what it holds', 'Replace everything' in await E.inner_text('#dlgTitle') and '2 entries, 1 repeating entry and 0 one-week changes' in await E.inner_text('#dlgBody'), await E.inner_text('#dlgBody'))
        await E.click('#dlg >> text=Cancel')
        check('cancel changes nothing', 'Pay rent' in names(store))
        await E.evaluate("() => { document.querySelector('#restoreFile').value = ''; }"); await E.set_input_files('#restoreFile', put('good.json', edited)); await until(E, "document.querySelector('#dlg').open")
        await E.click('#dlg button:has-text("Replace everything")')
        for _ in range(50):
            if 'Pay rent' not in names(store): break
            await asyncio.sleep(0.1)
        check('restore replaces the saved data', 'Pay rent' not in names(store) and 'Restored from demo-style id' in names(store), names(store))
        check('old-style ids became proper ids', all(re.match(r'^[0-9a-f-]{36}$', r['id']) for r in store.t['entries'].values()))
        check('the repeating entry survived', len(store.t['series']) == 1)
        await poke(T); await until(T, "entries.some(e => e.name === 'Restored from demo-style id')")
        check('and Toby\'s phone follows', not await T.evaluate("() => entries.some(e => e.name === 'Pay rent')"))

        # ---------- more than 1000 rows ----------
        for i in range(2300):
            eid = str(U.uuid4())
            store.t['entries'][eid] = {'id': eid, 'date': '2026-11-%02d' % (i % 28 + 1), 'name': 'Filler %d' % i, 'owner': 'both', 'type': 'plan', 'start_time': '09:00:00', 'end_time': None, 'label': None, 'close': False, 'done': False}
        store.log.clear()
        await E.reload(); await E.wait_for_selector('#appMain:not([hidden])')
        n = await E.evaluate("() => entries.length")
        gets = [x for x in store.log if x[0] == 'GET' and x[1].endswith('/entries')]
        check('every row loads, not just the first 1000', n == 2300 + len(edited['entries']), n)
        check('loaded in pages', len(gets) >= 3, len(gets))
        check('postgres time with seconds shows as HH:MM', await E.evaluate("() => entries.find(e => e.name === 'Filler 5').start") == '09:00')
        check('no page errors', not E.errs and not T.errs, E.errs + T.errs)
        check('nothing blocked by the security policy', not E.csp and not T.csp, E.csp + T.csp)
        print('\nFAILED:', bad or 'none')
        await b.close()
asyncio.run(main())
