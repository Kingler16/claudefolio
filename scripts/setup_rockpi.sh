#!/bin/bash
# Velora — Server/RockPi/Raspberry Pi Setup
set -e

INSTALL_DIR="${1:-$(pwd)}"
USER=$(whoami)

echo "=== Velora Server Setup ==="

# 1. System-Pakete
echo "Installing system packages..."
sudo apt update
sudo apt install -y python3-pip python3-venv nodejs npm

# 2. Claude Code CLI
echo "Installing Claude Code CLI..."
npm install -g @anthropic-ai/claude-code || echo "Claude CLI install failed — install manually"

# 3. Python venv
echo "Creating Python venv..."
cd "$INSTALL_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --prefer-binary -r requirements.txt

# 4. Cron-Jobs
echo "Setting up cron jobs..."
(crontab -l 2>/dev/null; echo "# Velora — Briefing Mon+Thu 7:00
0 7 * * 1,4 cd $INSTALL_DIR && ./venv/bin/python -m src.main briefing >> $INSTALL_DIR/logs/briefing.log 2>&1
# Velora — Monthly report 1st of month 9:00
0 9 1 * * cd $INSTALL_DIR && ./venv/bin/python -m src.main monthly >> $INSTALL_DIR/logs/monthly.log 2>&1") | crontab -

# 5. Log-Verzeichnis
mkdir -p "$INSTALL_DIR/logs"

# 6. Telegram Bot als systemd Service
echo "Creating systemd service..."
sudo tee /etc/systemd/system/velora-bot.service > /dev/null << SERVICE
[Unit]
Description=Velora Telegram Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=-$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/venv/bin/python -m src.main bot
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable velora-bot
sudo systemctl start velora-bot

# 7. Web Dashboard als systemd Service
echo "Creating web dashboard service..."
sudo tee /etc/systemd/system/velora-web.service > /dev/null << SERVICE
[Unit]
Description=Velora Web Dashboard
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=-$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/venv/bin/python -m src.main web
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable velora-web
sudo systemctl start velora-web

echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "1. Run 'python3 setup.py' to configure"
echo "2. Authenticate Claude: BROWSER='' claude --print 'test'"
echo "3. Test: ./venv/bin/python -m src.main briefing"
echo "4. Dashboard: http://$(hostname -I | awk '{print $1}'):8080"
