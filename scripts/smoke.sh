#!/bin/sh
# Health smoke. Verdict rows land here with the live re-check (G049).
set -eu
API_URL="${API_URL:-http://localhost:8000}"
body=""
i=0
while [ "$i" -lt 20 ]; do
  if body=$(curl -fsS "${API_URL}/api/health"); then
    break
  fi
  i=$((i + 1))
  sleep 1
done
[ -n "$body" ]
printf '%s\n' "$body"
printf '%s' "$body" | python3 -c 'import json,sys; body=json.load(sys.stdin); assert body.get("falkordb")=="up", body'
echo "smoke: falkordb up"
