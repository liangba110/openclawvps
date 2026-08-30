#!/bin/bash
# One-click deploy: rebuild frontend + restart backend + sync to public server
# Run this on the build/data server (Server A).
# Requires: sshpass on the local machine, password-based SSH to Server B.
#
# Concrete example (Tongtu Dazi / 同途搭子):
#   Server A (backend+DB):  42.193.113.230  (Flask API :5002, MySQL)
#   Server B (public/Nginx): 82.157.202.24   (serves frontend, proxies /api/ → Server A)
#
# Usage:
#   cd /opt/<project> && bash deploy.sh

set -e

# ═══════════════════════════════════════════
# CONFIGURE THESE FOR YOUR PROJECT
# ═══════════════════════════════════════════
PROJECT_DIR="/opt/ttdazi"            # project root on THIS server
SERVER_B="82.157.202.24"             # public Nginx server IP
SERVER_B_USER="ubuntu"
SERVER_B_PASS="wll16562341@"         # password or SSH key path
SERVER_B_PATH="/home/ubuntu/ttdazi-frontend"  # where dist/ lives on Server B
BACKEND_PORT="5002"
BACKEND_SERVICE="ttdazi"             # systemd service name
# ═══════════════════════════════════════════

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "========================================"
echo "  🚀 One-Click Deploy — $BACKEND_SERVICE"
echo "========================================"

# 1. Backup current build
echo -e "${YELLOW}[1/5]${NC} Backup current dist..."
BACKUP_DIR="/tmp/${BACKEND_SERVICE}_backup_$(date +%Y%m%d_%H%M%S)"
cp -r "$PROJECT_DIR/frontend/dist" "$BACKUP_DIR" 2>/dev/null || true
echo "  → $BACKUP_DIR"

# 2. Build frontend
echo -e "${YELLOW}[2/5]${NC} Build frontend..."
cd "$PROJECT_DIR/frontend"
BUILD_LOG=$(npm run build 2>&1) && echo "  ✅ Build complete" || {
  echo "  ❌ Build FAILED — check output below:"
  echo "$BUILD_LOG"
  exit 1
}

# 3. Restart backend API
echo -e "${YELLOW}[3/5]${NC} Restart backend API..."
sudo systemctl restart "$BACKEND_SERVICE" 2>/dev/null || \
  systemctl --user restart "$BACKEND_SERVICE" 2>/dev/null || {
    pkill -f "gunicorn main:app" 2>/dev/null
    sleep 1
    cd "$PROJECT_DIR/backend"
    nohup python3.12 -m gunicorn main:app -b 0.0.0.0:$BACKEND_PORT -w 2 --timeout 120 &
  }
echo "  ✅ Backend restarted"

# 4. Verify local API
echo -e "${YELLOW}[4/5]${NC} Verify local API..."
sleep 3
HEALTH=$(curl -s -w '%{http_code}' -o /dev/null "http://localhost:$BACKEND_PORT/api/health")
if [ "$HEALTH" = "200" ]; then
    echo "  ✅ API health check passed (HTTP $HEALTH)"
else
    echo "  ⚠️  API returned $HEALTH — check backend logs"
fi

# 5. Sync frontend to public server
echo -e "${YELLOW}[5/5]${NC} Sync frontend to $SERVER_B..."
sshpass -p "$SERVER_B_PASS" ssh -o StrictHostKeyChecking=no \
  "$SERVER_B_USER@$SERVER_B" "mkdir -p $SERVER_B_PATH"
sshpass -p "$SERVER_B_PASS" scp -r -o StrictHostKeyChecking=no \
  "$PROJECT_DIR/frontend/dist/"* "$SERVER_B_USER@$SERVER_B:$SERVER_B_PATH/"
echo "  ✅ Sync complete"

echo ""
echo -e "${GREEN}🎉 Deploy complete!${NC}"
echo "  Frontend: http://$SERVER_B"
echo "  API:      http://$SERVER_B/api/health"
echo ""
