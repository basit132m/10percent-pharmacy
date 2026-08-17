#!/usr/bin/env bash
#
# Pull the latest code, rebuild the dashboard and server, restart the service.
#
#   sudo -u pharmacy bash /opt/pharmacy/deploy/update.sh
#   sudo systemctl restart pharmacy
#
# Run it after every change you want live.
set -euo pipefail

APP_DIR=${APP_DIR:-/opt/pharmacy}
BRANCH=${BRANCH:-claude/pharmacy-bonus-offer-app-mxgxbs}

cd "$APP_DIR"

echo "==> Fetching $BRANCH"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"

echo "==> Building the dashboard"
cd "$APP_DIR/web"
npm ci --no-audit --no-fund
npm run build

echo "==> Building the server"
cd "$APP_DIR/server"
npm ci --no-audit --no-fund --omit=dev
# The TypeScript compiler is a dev dependency, so install it just for the build.
npm install --no-save typescript@5.7.3
npx tsc

echo
echo "Built. Restart the service to pick it up:"
echo "  sudo systemctl restart pharmacy"
