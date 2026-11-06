#!/usr/bin/env bash
# Build the research site and publish it to the VM, served by nginx on :6699.
#   site/deploy.sh                 # build + rsync + (first time) nginx vhost
set -euo pipefail
HOST="${HOST:-ubuntu@140.238.207.12}"
PORT="${PORT:-6699}"
WEBROOT="/var/www/llm-research"
cd "$(dirname "$0")/.."

python3 site/build.py

ssh "$HOST" "sudo mkdir -p $WEBROOT && sudo chown \$(id -u):\$(id -g) $WEBROOT"
rsync -az --delete site/dist/ "$HOST:$WEBROOT/"

ssh "$HOST" "sudo tee /etc/nginx/sites-available/llm-research >/dev/null" <<NGINX
server {
    listen $PORT;
    listen [::]:$PORT;
    server_name _;
    root $WEBROOT;
    index index.html;
    charset utf-8;

    gzip on;
    gzip_types text/plain text/css application/javascript application/json image/svg+xml;
    gzip_min_length 1024;

    # raw evidence files are plain text whatever their extension
    location /raw/ {
        types { image/png png; image/jpeg jpg jpeg; image/svg+xml svg; application/json json; }
        default_type text/plain;
        add_header X-Content-Type-Options nosniff;
        add_header Cache-Control "no-cache";
    }
    location = /index.html { add_header Cache-Control "no-cache"; }
    location ~ \.(json|js|css)$ { add_header Cache-Control "no-cache"; }
    location / { try_files \$uri \$uri/ /index.html; }
}
NGINX
ssh "$HOST" "sudo ln -sf /etc/nginx/sites-available/llm-research /etc/nginx/sites-enabled/llm-research && sudo nginx -t && sudo systemctl reload nginx"
echo "deployed: http://${HOST#*@}:$PORT/"
