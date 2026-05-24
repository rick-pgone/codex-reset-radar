#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/codex-reset-radar}"
REPO_URL="${REPO_URL:-}"
DOMAIN="${DOMAIN:-}"
PYTHON_BIN="${PYTHON_BIN:-python3.11}"

if [[ -z "$REPO_URL" ]]; then
  echo "Set REPO_URL first, for example:"
  echo "REPO_URL=https://github.com/rick-pgone/codex-reset-radar.git DOMAIN=example.com sudo -E bash deploy/ubuntu-vps-setup.sh"
  exit 1
fi

apt-get update
apt-get install -y git python3.11 python3.11-venv python3-pip nginx certbot python3-certbot-nginx

mkdir -p "$APP_DIR"
if [[ -d "$APP_DIR/.git" ]]; then
  git -C "$APP_DIR" pull --ff-only
else
  git clone "$REPO_URL" "$APP_DIR"
fi

"$PYTHON_BIN" -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install twikit playwright
"$APP_DIR/.venv/bin/python" -m playwright install chromium

"$APP_DIR/scripts/package_site.sh"

cat >/etc/systemd/system/codex-reset-radar-update.service <<SERVICE
[Unit]
Description=Update Codex Reset Radar data
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/python $APP_DIR/scripts/update_reset_radar.py --cadence-hours 12
ExecStartPost=$APP_DIR/scripts/package_site.sh
SERVICE

cat >/etc/systemd/system/codex-reset-radar-update.timer <<TIMER
[Unit]
Description=Run Codex Reset Radar updater every 12 hours

[Timer]
OnBootSec=5min
OnUnitActiveSec=12h
Persistent=true

[Install]
WantedBy=timers.target
TIMER

cat >/etc/nginx/sites-available/codex-reset-radar <<NGINX
server {
  listen 80;
  listen [::]:80;
  server_name ${DOMAIN:-_};
  root $APP_DIR/dist;
  index index.html;

  location / {
    try_files \$uri \$uri/ /index.html;
  }

  location /data/latest.json {
    add_header Cache-Control "no-store";
    try_files \$uri =404;
  }
}
NGINX

ln -sf /etc/nginx/sites-available/codex-reset-radar /etc/nginx/sites-enabled/codex-reset-radar
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx
systemctl daemon-reload
systemctl enable --now codex-reset-radar-update.timer

if [[ -n "$DOMAIN" ]]; then
  certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "admin@$DOMAIN" || true
fi

echo "Done. App directory: $APP_DIR"
echo "Remember to copy X cookies to the server if you want cloud scraping:"
echo "  scp /Users/rick/登录态/x_cookies.json root@SERVER:$APP_DIR/x_cookies.json"
