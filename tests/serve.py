# Serves a copy of ../app on localhost with the same security headers as app/_headers.
# The placeholder project address in index.html is swapped for a test address, which the
# pretend Supabase in mock.py answers for, so no real project is needed.
import http.server, os, shutil, socketserver, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, '..', 'app')
TEST_HOST = 'test-project.supabase.co'
tmp = tempfile.mkdtemp(prefix='our-week-app-')
shutil.copytree(APP, tmp, dirs_exist_ok=True)
p = os.path.join(tmp, 'index.html')
s = open(p, encoding='utf-8').read().replace('https://YOUR-PROJECT-REF.supabase.co', 'https://' + TEST_HOST)
open(p, 'w', encoding='utf-8').write(s)
CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
       f"connect-src 'self' https://{TEST_HOST} wss://{TEST_HOST}; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'")
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=tmp, **k)
    def end_headers(self):
        self.send_header('Content-Security-Policy', CSP)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(('127.0.0.1', 8765), H) as srv:
    srv.serve_forever()
