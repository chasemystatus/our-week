#!/usr/bin/env bash
# Runs every test against the app in ../app, using a pretend Supabase (no real project, no network).
# Needs: python3, playwright (pip install playwright; playwright install chromium).
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d)"          # tests save a few screenshots, so run from a scratch folder
cd "$WORK"
python3 "$HERE/serve.py" & SERVER=$!
trap 'kill $SERVER 2>/dev/null' EXIT
sleep 1
failed=0
for t in live1 live2 live3 live4 live5 test2 test3 test4 test5 test6 test7 test8 test9 test10 test11; do
  out="$(PYTHONPATH="$HERE" timeout 300 python3 "$HERE/$t.py" 2>&1)"
  if echo "$out" | grep -qE "^FAIL |^FAILED: \[" || echo "$out" | grep -qi "traceback"; then
    echo "✗ $t"; echo "$out" | grep -E "^FAIL |^FAILED: \[|Error" | head -5; failed=1
  else
    echo "✓ $t  ($(echo "$out" | grep -c '^PASS') checks)"
  fi
done
exit $failed
