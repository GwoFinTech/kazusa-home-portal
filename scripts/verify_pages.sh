#!/bin/bash
# Render-verify every HTML page of the portal in all four locales.
#
# Why: page templates fail at *runtime* (a broken page returns 500 while
# /health stays green). Run this after every deploy that touches app/ or
# app/static/.
#
# Checks per route × locale:
#   - expected HTTP status
#   - body is real HTML (<html ...>)
#   - no Python traceback / "Internal Server Error" leaked into the body
# For server-rendered (templated) routes additionally:
#   - no unresolved placeholders: {st(, {config., {request, ${, {{, }}
#
# Usage: bash scripts/verify_pages.sh [base_url]
set -uo pipefail

BASE=${1:-${KAZUSA_LOCAL:-http://127.0.0.1:8001}}
ENVF=${KAZUSA_ENV:-/opt/kazusa-home-portal/.env}
FAILS=0
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

envval() { grep -E "^$1=" "$ENVF" | head -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'\$//"; }
check() { if [ "$2" = "$3" ]; then echo "PASS: $1 ($3)"; else echo "FAIL: $1 expected=$2 actual=$3"; FAILS=$((FAILS+1)); fi; }
fail() { echo "FAIL: $1"; FAILS=$((FAILS+1)); }

SECRET=$(envval MOCK_AUTH_SECRET)
TOK=$(curl -s -X POST "$BASE/auth/mock-login" -H 'Content-Type: application/json' \
        -H "X-Mock-Auth: $SECRET" -d '{}' \
      | python3 -c 'import sys,json;print(json.load(sys.stdin).get("cookie_value",""))')
[ -n "$TOK" ] || { echo "FAIL: mock-login returned no cookie (is MOCK_AUTH_SECRET set?)"; exit 1; }

SID=$(curl -s -X POST "$BASE/auth/qr/create" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("sid",""))')
[ -n "$SID" ] || { echo "FAIL: /auth/qr/create returned no sid"; exit 1; }

# "path|expected_status|kind(html|tpl|asset)"
ROUTES=(
  "/|200|html"
  "/login|200|html"
  "/account/sessions|200|html"
  "/account/tokens|200|html"
  "/admin|200|html"
  "/manifest.json|200|asset"
  "/sw.js|200|asset"
  "/common.js|200|asset"
  "/i18n.js|200|asset"
  "/qr-confirm.js|200|asset"
  "/auth/qr/confirm|400|tpl"
  "/auth/qr/confirm?sid=definitely-not-a-real-sid|410|tpl"
  "/auth/qr/confirm?sid=$SID|200|tpl"
)
LOCALES=(zh-CN zh-TW en-US ja)
LEFT_RE='\{st\(|\{config\.|\{request\.[a-z]|\$\{|NameError|Traceback|Internal Server Error'

for loc in "${LOCALES[@]}"; do
  echo "== locale $loc =="
  for r in "${ROUTES[@]}"; do
    path=${r%%|*}; rest=${r#*|}; want=${rest%%|*}; kind=${rest##*|}
    out="$TMP/page"
    code=$(curl -s -o "$out" -w '%{http_code}' -A "HermesPageSmoke/1.0" \
                -H "Accept-Language: $loc" -H "Cookie: hp_session=$TOK" "$BASE$path")
    check "GET $path [$loc] status" "$want" "$code"
    [ -s "$out" ] || fail "GET $path [$loc] empty body"
    if [ "$kind" != "asset" ]; then
      grep -q '<html' "$out" || fail "GET $path [$loc] body is not HTML"
      grep -qE 'Traceback|Internal Server Error' "$out" && fail "GET $path [$loc] body leaks error text"
    fi
    if [ "$kind" = "tpl" ]; then
      if grep -qE "$LEFT_RE" "$out"; then
        fail "GET $path [$loc] unresolved placeholder: $(grep -oE "$LEFT_RE" "$out" | head -3 | tr '\n' ' ')"
      fi
      grep -qE '\{\{|\}\}' "$out" && fail "GET $path [$loc] doubled-brace artifact ({{ or }})"
    fi
  done
done

echo "== qr-confirm page wiring =="
curl -s -H "Cookie: hp_session=$TOK" "$BASE/auth/qr/confirm?sid=$SID" -o "$TMP/qr.html"
grep -q "data-sid=\"$SID\"" "$TMP/qr.html" && echo "PASS: page carries data-sid" || fail "page missing data-sid"
grep -q 'data-i18n="' "$TMP/qr.html" && echo "PASS: page carries data-i18n" || fail "page missing data-i18n"
grep -q 'src="/qr-confirm.js' "$TMP/qr.html" && echo "PASS: page loads /qr-confirm.js" || fail "page does not load /qr-confirm.js"
curl -s "$BASE/qr-confirm.js" -o "$TMP/qr.js"
grep -q "replace('{sec}', sec)" "$TMP/qr.js" && echo "PASS: JS countdown placeholder intact" || fail "JS lost the {sec} placeholder"
grep -q 'body.dataset' "$TMP/qr.js" && echo "PASS: JS reads data-* config" || fail "JS does not read data-* config"

echo "== recent app log =="
docker logs kazusa-home-portal --since 5m 2>&1 | grep -E 'Traceback|HTTP/1.1" 5[0-9][0-9]' \
  && fail "5xx or traceback in app log since deploy" \
  || echo "PASS: no 5xx/traceback in last 5m"

echo "RESULT: $FAILS failure(s)"
exit $FAILS
