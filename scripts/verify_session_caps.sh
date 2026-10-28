#!/bin/bash
# Verify session-cap isolation in app/auth.py _make_session_token().
# Run AFTER deploying session-cap changes, against a running deployment:
#   bash scripts/verify_session_caps.sh
#
# Covers:
#   T1 interactive per-client cap (keep last SESSION_CAP_PER_CLIENT per UA)
#   T2 other devices are not evicted by another client's login churn
#   T3 mock-login storm does not evict interactive (browser) sessions
# Creates temporary sessions as user admin, then removes every row it created.
set -uo pipefail

LOCAL=${KAZUSA_LOCAL:-http://127.0.0.1:8001}
ENVF=${KAZUSA_ENV:-/opt/kazusa-home-portal/.env}
FAILS=0

envval() { grep -E "^$1=" "$ENVF" | head -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'\$//"; }
check() { # check <desc> <expected> <actual>
  if [ "$2" = "$3" ]; then echo "PASS: $1 ($3)"; else echo "FAIL: $1 expected=$2 actual=$3"; FAILS=$((FAILS+1)); fi
}
sql() { sudo -u postgres psql -d kazusa_home -Atc "$1"; }

SECRET=$(envval MOCK_AUTH_SECRET)
SSEC=$(envval SESSION_SECRET)

echo "== cleanup leftovers from any previous run =="
sql "DELETE FROM home_sessions WHERE user_agent LIKE 'HermesE2E/%' OR (is_mock AND created_at > now() - interval '10 minutes')" >/dev/null

echo "== baseline =="
MAC_ID=$(sql "SELECT id FROM home_sessions WHERE user_id=1 AND NOT is_mock AND user_agent LIKE 'Mozilla%Macintosh%' ORDER BY created_at DESC LIMIT 1")
echo "  mac_session=${MAC_ID:-NONE}"
BEFORE_INTERACTIVE=$(sql "SELECT count(*) FROM home_sessions WHERE user_id=1 AND NOT is_mock")
BEFORE_NODE=$(sql "SELECT count(*) FROM home_sessions WHERE user_id=1 AND NOT is_mock AND user_agent='node'")
MOCK_BASE=$(sql "SELECT count(*) FROM home_sessions WHERE user_id=1 AND is_mock")
echo "  interactive_rows=$BEFORE_INTERACTIVE node_rows=$BEFORE_NODE mock_rows=$MOCK_BASE"

echo "== device A cookie (mock login) =="
ML=$(curl -s -X POST "$LOCAL/auth/mock-login" -H 'Content-Type: application/json' -H "X-Mock-Auth: $SECRET" -d '{}')
TOK=$(printf '%s' "$ML" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("cookie_value",""))')
[ -n "$TOK" ] || { echo "FAIL: mock-login gave no token: $ML"; exit 1; }
CSRF=$(printf 'csrf:%s' "$TOK" | openssl dgst -sha256 -hmac "$SSEC" | awk '{print substr($2,1,32)}')
echo "  ok, token_len=${#TOK} csrf=${CSRF:0:8}..."

echo "== T1: interactive per-client cap (12 logins, same UA) =="
UA1='HermesE2E/PerClient v1'
for i in $(seq 1 12); do
  SID=$(curl -s -X POST "$LOCAL/auth/qr/create" -A "$UA1" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("sid",""))')
  R=$(curl -s -X POST "$LOCAL/auth/qr/confirm" -A "$UA1" \
      -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
      -H "Cookie: hp_session=$TOK" -d "{\"sid\":\"$SID\"}")
  printf '  login %02d -> %s\n' "$i" "$(printf '%s' "$R" | head -c 90)"
  sleep 1
done
T1=$(sql "SELECT count(*) FROM home_sessions WHERE user_id=1 AND NOT is_mock AND user_agent='$(printf '%s' "$UA1" | sed "s/'/''/")'")
check "per-client cap keeps last 10" 10 "$T1"

echo "== T2: other devices unaffected (3 logins, different UA) =="
UA2='HermesE2E/OtherDevice v1'
for i in 1 2 3; do
  SID=$(curl -s -X POST "$LOCAL/auth/qr/create" -A "$UA2" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("sid",""))')
  curl -s -X POST "$LOCAL/auth/qr/confirm" -A "$UA2" \
      -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
      -H "Cookie: hp_session=$TOK" -d "{\"sid\":\"$SID\"}" >/dev/null
  sleep 1
done
T2=$(sql "SELECT count(*) FROM home_sessions WHERE user_id=1 AND NOT is_mock AND user_agent='$(printf '%s' "$UA2" | sed "s/'/''/")'")
check "second device keeps all 3" 3 "$T2"
T2b=$(sql "SELECT count(*) FROM home_sessions WHERE user_id=1 AND NOT is_mock AND user_agent='$(printf '%s' "$UA1" | sed "s/'/''/")'")
check "first device still capped at 10 (not evicted by device 2)" 10 "$T2b"
if [ -n "$MAC_ID" ]; then
  ALIVE=$(sql "SELECT count(*) FROM home_sessions WHERE id='$MAC_ID' AND NOT is_mock")
  check "pre-existing browser session survived test logins" 1 "$ALIVE"
else
  echo "WARN: no pre-existing browser session to check"
fi

echo "== T3: mock-login storm (12x) must not evict interactive sessions =="
for i in $(seq 1 12); do
  curl -s -X POST "$LOCAL/auth/mock-login" -H 'Content-Type: application/json' \
       -H "X-Mock-Auth: $SECRET" -A 'HermesE2E/MockStorm' -d '{}' >/dev/null
  sleep 1
done
MOCKN=$(sql "SELECT count(*) FROM home_sessions WHERE user_id=1 AND is_mock")
CAP_MOCK=$(envval SESSION_CAP_MOCK); CAP_MOCK=${CAP_MOCK:-30}
EXP_MOCK=$((MOCK_BASE + 13)); [ "$EXP_MOCK" -gt "$CAP_MOCK" ] && EXP_MOCK=$CAP_MOCK
check "mock pool = min(baseline+13, cap $CAP_MOCK)" "$EXP_MOCK" "$MOCKN"
MOCK_FLAGGED=$(sql "SELECT count(*) FROM home_sessions WHERE user_id=1 AND user_agent='HermesE2E/MockStorm' AND NOT is_mock")
check "storm sessions are all flagged is_mock" 0 "$MOCK_FLAGGED"
NOW_INTERACTIVE=$(sql "SELECT count(*) FROM home_sessions WHERE user_id=1 AND NOT is_mock")
EXP_INTERACTIVE=$((BEFORE_INTERACTIVE + 10 + 3))
check "interactive pool untouched by mock storm" "$EXP_INTERACTIVE" "$NOW_INTERACTIVE"
if [ -n "$MAC_ID" ]; then
  ALIVE2=$(sql "SELECT count(*) FROM home_sessions WHERE id='$MAC_ID' AND NOT is_mock")
  check "pre-existing browser session survived mock storm" 1 "$ALIVE2"
fi
T1b=$(sql "SELECT count(*) FROM home_sessions WHERE user_id=1 AND NOT is_mock AND user_agent='$(printf '%s' "$UA1" | sed "s/'/''/")'")
check "device 1 still 10 after mock storm" 10 "$T1b"
NODE_AFTER=$(sql "SELECT count(*) FROM home_sessions WHERE user_id=1 AND NOT is_mock AND user_agent='node'")
check "pre-existing node rows still present" "$BEFORE_NODE" "$NODE_AFTER"

echo "== cleanup =="
CLEAN=$(sql "DELETE FROM home_sessions WHERE user_agent LIKE 'HermesE2E/%' OR (is_mock AND created_at > now() - interval '10 minutes') RETURNING id" | wc -l)
echo "  removed $CLEAN test rows"
echo "  user1 sessions now: $(sql 'SELECT count(*) FROM home_sessions WHERE user_id=1') (baseline $BEFORE_INTERACTIVE)"

echo "== app log check =="
docker logs kazusa-home-portal --since 15m 2>&1 | grep -E 'Failed to store session hash|Traceback' && { echo "FAIL: session write errors in log"; FAILS=$((FAILS+1)); } || echo "  no session-write errors"

echo "RESULT: $FAILS failure(s)"
exit $FAILS
