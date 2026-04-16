#!/bin/bash
# Velora — Deploy to remote server
set -e

REMOTE="${1:-admin@192.168.1.27}"
REMOTE_DIR="/home/$(echo $REMOTE | cut -d@ -f1)/velora"
LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Deploying Velora to $REMOTE:$REMOTE_DIR ==="

# 1. Verzeichnisstruktur erstellen
echo "Creating directories..."
ssh $REMOTE "mkdir -p $REMOTE_DIR/{config,memory/cache,logs,scripts}"
ssh $REMOTE "mkdir -p $REMOTE_DIR/src/{data,analysis,delivery,chat,web/{routes,services,templates/components,static/{css,js,vendor}}}"

# 2. Source-Code kopieren
echo "Copying source code..."
scp -r "$LOCAL_DIR"/src/data/*.py $REMOTE:$REMOTE_DIR/src/data/
scp -r "$LOCAL_DIR"/src/analysis/*.py $REMOTE:$REMOTE_DIR/src/analysis/
scp -r "$LOCAL_DIR"/src/delivery/*.py $REMOTE:$REMOTE_DIR/src/delivery/
scp -r "$LOCAL_DIR"/src/chat/*.py $REMOTE:$REMOTE_DIR/src/chat/
scp "$LOCAL_DIR"/src/__init__.py $REMOTE:$REMOTE_DIR/src/
scp "$LOCAL_DIR"/src/main.py $REMOTE:$REMOTE_DIR/src/ 2>/dev/null || true

# 3. Web-Dashboard kopieren
echo "Copying web dashboard..."
scp "$LOCAL_DIR"/src/web/__init__.py $REMOTE:$REMOTE_DIR/src/web/
scp "$LOCAL_DIR"/src/web/app.py $REMOTE:$REMOTE_DIR/src/web/
scp "$LOCAL_DIR"/src/web/i18n.py $REMOTE:$REMOTE_DIR/src/web/ 2>/dev/null || true
scp "$LOCAL_DIR"/src/web/routes/__init__.py $REMOTE:$REMOTE_DIR/src/web/routes/
scp "$LOCAL_DIR"/src/web/services/*.py $REMOTE:$REMOTE_DIR/src/web/services/
scp "$LOCAL_DIR"/src/web/templates/*.html $REMOTE:$REMOTE_DIR/src/web/templates/
scp "$LOCAL_DIR"/src/web/templates/components/*.html $REMOTE:$REMOTE_DIR/src/web/templates/components/
scp "$LOCAL_DIR"/src/web/static/css/*.css $REMOTE:$REMOTE_DIR/src/web/static/css/
scp "$LOCAL_DIR"/src/web/static/js/*.js $REMOTE:$REMOTE_DIR/src/web/static/js/ 2>/dev/null || true
scp "$LOCAL_DIR"/src/web/static/vendor/*.js $REMOTE:$REMOTE_DIR/src/web/static/vendor/

# 4. Config, Scripts, Root-Dateien
echo "Copying config & scripts..."
scp "$LOCAL_DIR"/config/*.example.json $REMOTE:$REMOTE_DIR/config/
scp "$LOCAL_DIR"/requirements.txt $REMOTE:$REMOTE_DIR/
scp "$LOCAL_DIR"/setup.py $REMOTE:$REMOTE_DIR/
scp "$LOCAL_DIR"/scripts/setup_rockpi.sh $REMOTE:$REMOTE_DIR/scripts/

# 5. Bestehende Config übertragen (wenn lokal vorhanden)
if [ -f "$LOCAL_DIR/config/settings.json" ]; then
    echo "Copying settings.json..."
    scp "$LOCAL_DIR"/config/settings.json $REMOTE:$REMOTE_DIR/config/
fi
if [ -f "$LOCAL_DIR/config/portfolio.json" ]; then
    echo "Copying portfolio.json..."
    scp "$LOCAL_DIR"/config/portfolio.json $REMOTE:$REMOTE_DIR/config/
fi
if [ -f "$LOCAL_DIR/config/watchlist.json" ]; then
    echo "Copying watchlist.json..."
    scp "$LOCAL_DIR"/config/watchlist.json $REMOTE:$REMOTE_DIR/config/
fi

echo ""
echo "=== Deploy complete ==="
echo "Next: ssh $REMOTE 'cd $REMOTE_DIR && bash scripts/setup_rockpi.sh'"
