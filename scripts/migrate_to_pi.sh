#!/usr/bin/env bash
# One-time move of the live data from this PC to the Pi (ARCHITECTURE §12, phase 4b).
#
# 1. Appends the app's secrets from .env to ~/infra/config/jobsearcher/jobsearcher.env on the Pi
#    (values are never printed).
# 2. Copies a consistent copy of the DB, the cache, company notes, exports, Finn state and the
#    profile to ~/infra/config/jobsearcher/data/ on the Pi.
# Refuses to run if the Pi already has a DB, so it can't overwrite live data.
# Run before the first `scripts/deploy_pi.sh`, with `serve` stopped on this PC.
#
# Usage: bash scripts/migrate_to_pi.sh
set -euo pipefail

HOST="${PI_HOST:-pi}"
REMOTE="infra/config/jobsearcher"
KEYS='^(GMAIL_ADDRESS|GMAIL_APP_PASSWORD|OPENROUTER_API_KEY|OPENROUTER_MANAGEMENT_KEY|NAV_FEED_TOKEN)='

cd "$(git rev-parse --show-toplevel)"

if ssh "$HOST" "test -e ~/$REMOTE/data/jobsearcher.db"; then
  echo "Pi-en har allerede en database i ~/$REMOTE/data. Avbryter." >&2
  exit 1
fi

echo "Legger hemmeligheter i jobsearcher.env (verdiene vises ikke) ..."
present="$(ssh "$HOST" "cut -d= -f1 ~/$REMOTE/jobsearcher.env")"
grep -E "$KEYS" .env | tr -d '\r' | while IFS= read -r line; do
  key="${line%%=*}"
  if grep -qx "$key" <<<"$present"; then
    echo "  $key finnes allerede, hopper over"
  else
    printf '%s\n' "$line"
  fi
done | ssh "$HOST" "f=~/$REMOTE/jobsearcher.env; [ -z \"\$(tail -c1 \$f)\" ] || echo >> \$f; cat >> \$f; chmod 600 \$f; echo '  Nøkler nå:' \$(cut -d= -f1 \$f)"

echo "Kopierer database og profil ..."
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
uv run python -c "
import sqlite3, sys
src = sqlite3.connect('data/jobsearcher.db'); dst = sqlite3.connect(sys.argv[1])
src.backup(dst); dst.close()
assert sqlite3.connect(sys.argv[1]).execute('pragma integrity_check').fetchone()[0] == 'ok'
" "$tmp/jobsearcher.db"

tar -czf - -C "$tmp" jobsearcher.db \
  -C "$PWD/data" cache companies exports finn_device.json finn_filters.json \
  -C "$PWD/context" profile derived \
  | ssh "$HOST" "mkdir -p ~/$REMOTE/data && tar -xzf - -C ~/$REMOTE/data && du -sh ~/$REMOTE/data && ls ~/$REMOTE/data"

echo "Ferdig. Neste: tjenesten i infra-stacken, så bash scripts/deploy_pi.sh."
