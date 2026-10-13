import asyncio
async def until(pg, expr, timeout=8000, step=100):
    """Poll a JS expression (a function body returning a value) without eval, so it works under the page's security policy."""
    waited = 0
    fn = "() => { " + expr + " }" if "return" in expr else "() => (" + expr + ")"
    while waited <= timeout:
        if await pg.evaluate(fn): return True
        await asyncio.sleep(step / 1000); waited += step
    raise TimeoutError("never became true: " + expr)
saved = lambda pg: until(pg, "document.querySelector('#saveState').textContent.includes('Saved')")
