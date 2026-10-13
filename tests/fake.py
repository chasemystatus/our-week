def fake(iso_utc):
    return """(() => { const fixed = new Date("%s").getTime(); const R = Date;
      class F extends R { constructor(...a) { if (a.length === 0) super(fixed); else super(...a); } static now() { return fixed; } }
      window.Date = F; })();""" % iso_utc
FAKE = fake("2026-10-12T11:00:00Z")   # Monday 12 October 2026, midday in London
