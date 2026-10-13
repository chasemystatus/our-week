# A stand-in for the Supabase project, so the app's sign-in and saving can be tested without reaching the real one.
import json, re, base64, asyncio
from urllib.parse import urlparse, parse_qs, unquote
SB = "https://test-project.supabase.co"
CORS = {"access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS", "access-control-expose-headers": "*"}
b64 = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")

class Store:
    def __init__(self):
        self.t = {"entries": {}, "series": {}, "exceptions": {}}
        self.members = {"eloise@example.test", "toby@example.test"}
        self.users = {"eloise@example.test": "correct-horse-1", "toby@example.test": "battery-staple-2", "stranger@example.test": "not-on-the-list-3"}
        self.tokens = {}          # access token -> email
        self.refresh = {}         # refresh token -> email
        self.fail_writes = False  # answer writes with a server error
        self.drop = False         # act as if the network is down
        self.log = []             # (method, path)
        self.sockets = []         # live websocket sessions
        self.n = 0
        self.recover = []
        self.pw_updates = []
        self.invalidate_next = False

    # ---------- sessions ----------
    def issue(self, email):
        self.n += 1
        uid = "u-" + email.split("@")[0]
        tok = b64({"alg": "HS256", "typ": "JWT"}) + "." + b64({"sub": uid, "email": email, "role": "authenticated", "aud": "authenticated", "exp": 1900000000, "n": self.n}) + ".sig"
        rt = "refresh-%d" % self.n
        self.tokens[tok] = email; self.refresh[rt] = email
        user = {"id": uid, "aud": "authenticated", "role": "authenticated", "email": email, "app_metadata": {}, "user_metadata": {}, "created_at": "2026-01-01T00:00:00Z"}
        return {"access_token": tok, "token_type": "bearer", "expires_in": 3600, "expires_at": 1900000000, "refresh_token": rt, "user": user}, user

    def who(self, headers):
        a = headers.get("authorization", "")
        return self.tokens.get(a[7:]) if a.startswith("Bearer ") else None

    # ---------- http ----------
    async def handle(self, route):
        req = route.request
        u = urlparse(req.url); path = u.path; q = parse_qs(u.query); m = req.method
        if m == "OPTIONS":
            return await route.fulfill(status=204, headers=CORS)
        self.log.append((m, path + ("?" + u.query if "token" in path else "")))
        if self.drop:
            return await route.abort()
        def js(status, body, extra=None):
            h = dict(CORS); h["content-type"] = "application/json"; h.update(extra or {})
            return route.fulfill(status=status, headers=h, body=json.dumps(body))
        body = json.loads(req.post_data) if req.post_data else None
        email = self.who(req.headers)

        if path == "/auth/v1/token":
            gt = q.get("grant_type", [""])[0]
            if gt == "password":
                if self.users.get(body["email"]) == body["password"]:
                    s, _ = self.issue(body["email"]); return await js(200, s)
                return await js(400, {"code": 400, "error_code": "invalid_credentials", "msg": "Invalid login credentials"})
            if gt == "refresh_token":
                em = self.refresh.get(body["refresh_token"])
                if em and not getattr(self, "refresh_broken", False):
                    s, _ = self.issue(em); return await js(200, s)
                return await js(400, {"code": 400, "error_code": "refresh_token_not_found", "msg": "Invalid Refresh Token"})
        if path == "/auth/v1/user":
            if not email: return await js(401, {"code": 401, "msg": "invalid JWT"})
            if m == "GET": return await js(200, {"id": "u-" + email.split("@")[0], "aud": "authenticated", "role": "authenticated", "email": email, "app_metadata": {}, "user_metadata": {}})
            if m == "PUT":
                self.pw_updates.append((email, body.get("password")))
                if body.get("password") in ("password1234", "aaaaaaaaaa"):
                    return await js(422, {"code": 422, "error_code": "weak_password", "msg": "Password is known to be weak and easy to guess"})
                self.users[email] = body.get("password")
                return await js(200, {"id": "u-" + email.split("@")[0], "aud": "authenticated", "role": "authenticated", "email": email})
        if path == "/auth/v1/logout":
            return await route.fulfill(status=204, headers=CORS)
        if path == "/auth/v1/recover":
            self.recover.append(body.get("email")); return await js(200, {})
        if path == "/rest/v1/rpc/is_member":
            if not email: return await js(401, {"code": "PGRST301", "message": "JWT required"})
            return await js(200, email in self.members)
        mt = re.match(r"^/rest/v1/(entries|series|exceptions)$", path)
        if mt:
            tb = mt.group(1)
            if self.invalidate_next and email:
                self.invalidate_next = False
                for k in [k for k, v in self.tokens.items() if v == email]: del self.tokens[k]
                email = None
            if not email: return await js(401, {"code": "PGRST301", "message": "JWT expired"})
            if email not in self.members:      # row-level security: reads see nothing, writes are refused
                if m == "GET": return await js(200, [])
                return await js(403, {"code": "42501", "message": "new row violates row-level security policy for table \"%s\"" % tb})
            key = (lambda r: (r["series_id"], r["orig"])) if tb == "exceptions" else (lambda r: r["id"])
            if m == "GET":
                rows = list(self.t[tb].values())
                order = q.get("order", [""])[0].split(",")
                for o in reversed([x for x in order if x]):
                    rows.sort(key=lambda r: str(r.get(o.split(".")[0])))
                off = int(q.get("offset", ["0"])[0]); lim = min(int(q.get("limit", ["1000"])[0]), 1000)
                return await js(200, rows[off:off + lim])
            if self.fail_writes:
                return await js(500, {"message": "the database is having a moment"})
            if m == "POST":
                rows = body if isinstance(body, list) else [body]
                for r in rows: self.t[tb][key(r)] = dict(r)
                self.notify(tb)
                return await route.fulfill(status=201, headers=CORS)
            if m == "DELETE":
                def match(r):
                    for col, vals in q.items():
                        if col in ("select",): continue
                        v = vals[0]
                        if v.startswith("in.("):
                            if str(r.get(col)) not in v[4:-1].split(","): return False
                        elif v.startswith("eq."):
                            if str(r.get(col)) != unquote(v[3:]): return False
                    return True
                for k in [k for k, r in self.t[tb].items() if match(r)]: del self.t[tb][k]
                if tb == "series":
                    for k in [k for k in self.t["exceptions"] if k[0] not in {r["id"] for r in self.t["series"].values()}]: del self.t["exceptions"][k]
                self.notify(tb)
                return await route.fulfill(status=204, headers=CORS)
        return await js(404, {"message": "mock has no answer for " + m + " " + path})

    # ---------- realtime websocket (Phoenix protocol, version 2) ----------
    async def ws(self, ws):
        sess = {"ws": ws, "ids": {}, "topic": None}
        self.sockets.append(sess)
        def on_msg(message):
            if isinstance(message, bytes): return
            jr, ref, topic, event, payload = json.loads(message)
            if event == "heartbeat":
                ws.send(json.dumps([None, ref, "phoenix", "phx_reply", {"status": "ok", "response": {}}]))
            elif event == "phx_join":
                pcs = (payload.get("config") or {}).get("postgres_changes") or []
                resp = []
                for i, pc in enumerate(pcs):
                    sess["ids"][pc["table"]] = i + 1
                    resp.append({"id": i + 1, "event": pc["event"], "schema": pc["schema"], "table": pc["table"]})
                sess["topic"] = topic
                ws.send(json.dumps([jr, ref, topic, "phx_reply", {"status": "ok", "response": {"postgres_changes": resp}}]))
            elif event == "phx_leave":
                ws.send(json.dumps([jr, ref, topic, "phx_reply", {"status": "ok", "response": {}}]))
        ws.on_message(on_msg)

    def notify(self, table):
        for s in self.sockets:
            if s["topic"] and table in s["ids"]:
                try:
                    s["ws"].send(json.dumps([None, None, s["topic"], "postgres_changes", {"ids": [s["ids"][table]], "data": {
                        "schema": "public", "table": table, "commit_timestamp": "2026-10-12T11:00:00Z", "type": "UPDATE", "columns": [], "record": {}, "old_record": {}, "errors": None}}]))
                except Exception:
                    pass

async def attach(ctx, store):
    await ctx.route(SB + "/**", store.handle)
    await ctx.route_web_socket(re.compile(r"^wss://test-project\.supabase\.co/realtime/.*"), store.ws)
