#!/usr/bin/env bash
#
# One-time VPS setup for the 10% Discount Pharmacy backend (Ubuntu 24.04).
#
#   sudo bash deploy/install.sh
#
# Deliberately non-destructive: it never overwrites an existing web server
# config, and it stops rather than guessing if something is already there.
# It installs Node.js if missing, creates the service user and directories,
# and registers the systemd service. It does NOT start the service — that
# happens once you have added the config in /etc/pharmacy.
set -euo pipefail

APP_DIR=${APP_DIR:-/opt/pharmacy}
CONFIG_DIR=/etc/pharmacy
SERVICE_USER=pharmacy
NODE_MAJOR=20

if [[ $EUID -ne 0 ]]; then
  echo "Run this with sudo: sudo bash deploy/install.sh" >&2
  exit 1
fi

echo "==> Checking Node.js"
if ! command -v node >/dev/null 2>&1 || [[ $(node -v | sed 's/v\([0-9]*\).*/\1/') -lt $NODE_MAJOR ]]; then
  echo "    installing Node.js ${NODE_MAJOR}.x"
  curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | bash -
  apt-get install -y nodejs
else
  echo "    found $(node -v)"
fi

echo "==> Creating the service user"
if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
  echo "    created $SERVICE_USER"
else
  echo "    $SERVICE_USER already exists"
fi

echo "==> Creating directories"
mkdir -p "$CONFIG_DIR"
chown root:"$SERVICE_USER" "$CONFIG_DIR"
# The service account key lives here: readable by the service, nobody else.
chmod 750 "$CONFIG_DIR"

if [[ ! -d "$APP_DIR/.git" ]]; then
  echo "!! $APP_DIR does not contain a checkout of the repository."
  echo "   Clone it first:"
  echo "     git clone -b claude/pharmacy-bonus-offer-app-mxgxbs \\"
  echo "       https://github.com/basit132m/10percent-pharmacy.git $APP_DIR"
  exit 1
fi

chown -R "$SERVICE_USER":"$SERVICE_USER" "$APP_DIR"

echo "==> Installing the systemd service"
install -m 644 "$APP_DIR/deploy/pharmacy.service" /etc/systemd/system/pharmacy.service
systemctl daemon-reload
systemctl enable pharmacy.service >/dev/null
echo "    pharmacy.service registered (not started yet)"

echo "==> Looking for a web server to put in front"
for candidate in nginx apache2 lshttpd caddy; do
  if systemctl is-active --quiet "$candidate" 2>/dev/null; then
    echo "    $candidate is running — use it as the reverse proxy"
    FOUND=$candidate
  fi
done

if [[ -z ${FOUND:-} ]]; then
  echo "    none running; installing nginx"
  apt-get install -y nginx
  FOUND=nginx
fi

cat <<EOF

Done. Next:

  1. Put your Firebase service account key at:
       $CONFIG_DIR/service-account.json
     then lock it down:
       chown root:$SERVICE_USER $CONFIG_DIR/service-account.json
       chmod 640 $CONFIG_DIR/service-account.json

  2. Create the server config:
       cp $APP_DIR/server/.env.example $APP_DIR/server/.env
       nano $APP_DIR/server/.env

  3. Build everything:
       sudo -u $SERVICE_USER bash $APP_DIR/deploy/update.sh

  4. Point $FOUND at http://127.0.0.1:8080 — for nginx:
       cp $APP_DIR/deploy/nginx-pharmacy.conf /etc/nginx/sites-available/pharmacy
       ln -s /etc/nginx/sites-available/pharmacy /etc/nginx/sites-enabled/pharmacy
       nginx -t && systemctl reload nginx
       apt-get install -y certbot python3-certbot-nginx
       certbot --nginx -d a1humanizer.site -d www.a1humanizer.site

  5. Start it:
       systemctl start pharmacy
       systemctl status pharmacy

EOF
