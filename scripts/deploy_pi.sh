#!/usr/bin/env bash
# Deploy JobSearcher to the Pi homeserver (ARCHITECTURE §12, README "Drift").
#
# Ships the working tree (tracked + untracked, minus .gitignore'd files, so no personal data)
# to ~/infra/jobsearcher on the Pi, rebuilds the image there and restarts only the
# `jobsearcher` service. Needs `ssh pi` (key login) from this machine.
#
# Usage: bash scripts/deploy_pi.sh
set -euo pipefail

HOST="${PI_HOST:-pi}"
REMOTE_DIR="infra/jobsearcher"

cd "$(git rev-parse --show-toplevel)"

if [ -n "$(git status --porcelain)" ]; then
  echo "Merk: deployer arbeidskopien med ucommittede endringer."
fi

echo "Sender kildekoden til $HOST:~/$REMOTE_DIR ..."
git ls-files -z --cached --others --exclude-standard \
  | tar --null --ignore-failed-read -T - -czf - \
  | ssh "$HOST" "set -e; rm -rf ~/$REMOTE_DIR.new; mkdir -p ~/$REMOTE_DIR.new; tar -xzf - -C ~/$REMOTE_DIR.new; rm -rf ~/$REMOTE_DIR; mv ~/$REMOTE_DIR.new ~/$REMOTE_DIR"

echo "Bygger og starter containeren (kan ta noen minutter på Pi-en) ..."
ssh "$HOST" "cd ~/infra && docker compose build jobsearcher && docker compose up -d jobsearcher && docker image prune -f >/dev/null"

echo "Venter på healthcheck ..."
for _ in $(seq 1 30); do
  status="$(ssh "$HOST" "docker inspect -f '{{.State.Health.Status}}' jobsearcher" 2>/dev/null || true)"
  if [ "$status" = "healthy" ]; then
    echo "OK: jobsearcher er oppe (https://jobb.mariuskristensen.no)."
    exit 0
  fi
  sleep 5
done
echo "Containeren ble ikke healthy. Logger:" >&2
ssh "$HOST" "docker logs --tail 50 jobsearcher" >&2
exit 1
