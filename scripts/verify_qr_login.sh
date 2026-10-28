#!/bin/bash
# Verify QR scan-login flow end-to-end (regression for GET /auth/qr/confirm 500)
set -uo pipefail
BASE=${1:-${KAZUSA_LOCAL:-http://127.0.0.1:8001}}
ENVF=${KAZUSA_ENV:-/opt/kazusa-home-portal/.env}
FAILS=0
envval() { grep -E "^$1=" "$ENVF" | head -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'\$//"; }
check() { if [ "$2" = "$3" ]; then echo "PASS: $1 ($3)"; else echo "FAIL: $1 expected=$2 actual=$3"; FAILS=$((FAILS+1)); fi; }
SECRET=$(envval MOCK_AUTH_SECRET); SSEC=$(envval SESSION_SECRET)

echo "== device A (scanner) login =="
TOK=$(curl -s -X POST "$BASE/auth/mock-login" -H 'Content-Type: application/json' -H "X-Mock-Auth: $SECRET" -d '{}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["cookie_value"])')
CSRF=$(printf 'csrf:%s' "$TOK" | openssl dgst -sha256 -hmac "$SSEC" | awk '{print substr($2,1,32)}')
[ -n "$TOK" ] && echo "  ok" || { echo "FAIL: no device A token"; exit 1; }

echo "== device B: create QR =="
SID=$(curl -s -X POST "$BASE/auth/qr/create" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("sid",""))')
[ -n "$SID" ] && echo "  sid=$SID" || { echo "FAIL: no sid"; exit 1; }

echo "== device A: render confirm page (was HTTP 500) =="
PAGE=/root/.hermes/cache/scratch/qr_confirm.html
CODE=$(curl -s -o "$PAGE" -w '%{http_code}' -H "Cookie: hp_session=$TOK" "$BASE/auth/qr/confirm?sid=$SID")
check "GET /auth/qr/confirm status" 200 "$CODE"
grep -q "data-sid=\"$SID\"" "$PAGE" && echo "PASS: page carries data-sid" || { echo "FAIL: data-sid missing"; FAILS=$((FAILS+1)); }
grep -q 'data-i18n="' "$PAGE" && echo "PASS: page carries i18n payload" || { echo "FAIL: data-i18n missing"; FAILS=$((FAILS+1)); }
grep -q 'src="/qr-confirm.js' "$PAGE" && echo "PASS: page loads external JS" || { echo "FAIL: external JS not referenced"; FAILS=$((FAILS+1)); }
grep -qE '\$\{|\{st\(|\{\{' "$PAGE" && { echo "FAIL: unresolved template placeholder in page"; FAILS=$((FAILS+1)); } || echo "PASS: no unresolved placeholders"
JS=$(curl -s "$BASE/qr-confirm.js")
printf '%s' "$JS" | grep -q "replace('{sec}', sec)" && echo "PASS: JS countdown placeholder intact" || { echo "FAIL: JS lost {sec} placeholder"; FAILS=$((FAILS+1)); }
printf '%s' "$JS" | grep -q 'document.body.dataset' && echo "PASS: JS config comes from data-*" || { echo "FAIL: JS not reading data-*"; FAILS=$((FAILS+1)); }

echo "== device A confirms, device B polls =="
CF=$(curl -s -X POST "$BASE/auth/qr/confirm" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" -H "Cookie: hp_session=$TOK" -d "{\"sid\":\"$SID\"}")
echo "  confirm -> $CF"
BTOK=$(curl -s "$BASE/auth/qr/status?sid=$SID" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d.get("status",""),d.get("token",""))')
STATUS=$(printf '%s' "$BTOK" | awk '{print $1}')
TOKB=$(printf '%s' "$BTOK" | awk '{print $2}')
check "qr status confirmed" confirmed "$STATUS"
[ -n "$TOKB" ] && echo "PASS: device B received token (len=${#TOKB})" || { echo "FAIL: no token"; FAILS=$((FAILS+1)); }

echo "== device B token is usable =="
ME=$(curl -s -H "Cookie: hp_session=$TOKB" "$BASE/api/me" | head -c 120)
echo "  /api/me -> $ME"
printf '%s' "$ME" | grep -q 'email' && echo "PASS: QR session authenticates" || { echo "FAIL: QR session not usable"; FAILS=$((FAILS+1)); }

echo "== HTML page smoke (authenticated) =="
for p in / /account/sessions /account/tokens /admin /login; do
  C=$(curl -s -o /dev/null -w '%{http_code}' -H "Cookie: hp_session=$TOK" "$BASE$p")
  check "GET $p" 200 "$C"
done

echo "== log check =="
docker logs kazusa-home-portal --since 5m 2>&1 | grep -E 'NameError|Traceback|HTTP/1.1" 500' && { echo "FAIL: 5xx/traceback in log"; FAILS=$((FAILS+1)); } || echo "PASS: no 5xx or traceback"

echo "RESULT: $FAILS failure(s)"
exit $FAILS
