#!/bin/bash
# GPU FinOps Lab - Run script for Linux
# Usage: ./run-linux.sh [start|stop|tunnel|status|logs]

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
TUNNEL_PID_FILE="$PROJECT_DIR/.tunnel.pid"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_step() { echo -e "\n${GREEN}[STEP]${NC} $1"; }
print_info() { echo -e "${YELLOW}[INFO]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

detect_distro() {
  if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo "$ID"
  else
    echo "unknown"
  fi
}

case "${1:-start}" in
  start)
    print_step "1/3 - Checking Docker..."
    if ! docker info >/dev/null 2>&1; then
      print_error "Docker is not running. Start Docker first:"
      echo "  sudo systemctl start docker"
      exit 1
    fi
    echo "  Docker is running"

    print_step "2/3 - Building and starting services..."
    cd "$PROJECT_DIR"
    docker compose up --build -d

    print_step "3/3 - Waiting for services to be healthy..."
    sleep 5

    # Test gateway
    if curl -s http://localhost:8000/ >/dev/null 2>&1; then
      echo -e "  ${GREEN}Gateway is UP at http://localhost:8000${NC}"
    else
      print_error "Gateway not responding. Check: docker compose logs gateway"
      exit 1
    fi

    echo ""
    echo "=========================================="
    echo -e "${GREEN} ALL SERVICES RUNNING${NC}"
    echo "=========================================="
    echo ""
    echo "  Gateway:          http://localhost:8000"
    echo "  GPU Node Manager: http://localhost:8001"
    echo "  Billing API:      http://localhost:8002"
    echo "  Spot Manager:     http://localhost:8003"
    echo "  Autoscaler:       http://localhost:8004"
    echo "  Cost Tracker:     http://localhost:8005"
    echo ""
    echo "Next: Run './run-linux.sh tunnel' to expose to Kaggle/Colab"
    ;;

  tunnel)
    print_step "Starting tunnel to expose gateway..."

    # Check if cloudflared is installed
    if command -v cloudflared >/dev/null 2>&1; then
      print_info "Using cloudflared (free, no account needed)"
      echo "  Starting tunnel..."
      cloudflared tunnel --url http://localhost:8000 2>&1 | tee "$PROJECT_DIR/.tunnel.log" &
      echo $! > "$TUNNEL_PID_FILE"

      # Wait up to 15s for the URL to appear
      TUNNEL_URL=""
      for i in $(seq 1 15); do
        TUNNEL_URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$PROJECT_DIR/.tunnel.log" 2>/dev/null | head -1)
        if [ -n "$TUNNEL_URL" ]; then break; fi
        sleep 1
      done
      if [ -n "$TUNNEL_URL" ]; then
        echo ""
        echo "=========================================="
        echo -e "${GREEN} TUNNEL ACTIVE${NC}"
        echo "=========================================="
        echo ""
        echo -e "  URL: ${GREEN}${TUNNEL_URL}${NC}"
        echo ""
        echo "  Copy this URL into your Kaggle/Colab notebook:"
        echo "  GATEWAY_URL = \"${TUNNEL_URL}\""
        echo ""
      else
        print_info "Tunnel starting... Check .tunnel.log for the URL"
        echo "  Run: grep 'trycloudflare' .tunnel.log"
      fi

    elif command -v ngrok >/dev/null 2>&1; then
      print_info "Using ngrok"
      ngrok http 8000 &
      echo $! > "$TUNNEL_PID_FILE"
      sleep 3
      # Get ngrok URL via API
      TUNNEL_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "import sys,json; print(json.load(sys.stdin)['tunnels'][0]['public_url'])" 2>/dev/null)
      echo ""
      echo "=========================================="
      echo -e "${GREEN} TUNNEL ACTIVE${NC}"
      echo "=========================================="
      echo ""
      echo -e "  URL: ${GREEN}${TUNNEL_URL}${NC}"
      echo ""
      echo "  GATEWAY_URL = \"${TUNNEL_URL}\""
      echo ""

    else
      DISTRO=$(detect_distro)
      print_info "No tunnel tool found. Install one:"
      echo ""
      echo "  Option A (recommended - free, no signup):"
      case "$DISTRO" in
        ubuntu|debian)
          echo "    curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o /tmp/cloudflared.deb"
          echo "    sudo dpkg -i /tmp/cloudflared.deb"
          ;;
        fedora|rhel|centos)
          echo "    curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-x86_64.rpm -o /tmp/cloudflared.rpm"
          echo "    sudo rpm -i /tmp/cloudflared.rpm"
          ;;
        arch|manjaro)
          echo "    yay -S cloudflared"
          echo "    # hoặc: sudo pacman -S cloudflared-bin"
          ;;
        *)
          echo "    curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /tmp/cloudflared"
          echo "    sudo install -m 755 /tmp/cloudflared /usr/local/bin/"
          ;;
      esac
      echo ""
      echo "  Option B (requires free account):"
      echo "    # Download từ https://ngrok.com/download"
      echo ""
      echo "  Option C (zero install):"
      echo "    ssh -R 80:localhost:8000 nokey@localhost.run"
      echo ""
      exit 1
    fi
    ;;

  stop)
    print_step "Stopping services..."
    cd "$PROJECT_DIR"
    docker compose down

    if [ -f "$TUNNEL_PID_FILE" ]; then
      kill $(cat "$TUNNEL_PID_FILE") 2>/dev/null || true
      rm "$TUNNEL_PID_FILE"
      echo "  Tunnel stopped"
    fi

    echo -e "${GREEN}  All stopped.${NC}"
    ;;

  status)
    echo "=== Docker Services ==="
    cd "$PROJECT_DIR"
    docker compose ps

    echo ""
    echo "=== Gateway Health ==="
    curl -s http://localhost:8000/ | python3 -m json.tool 2>/dev/null || echo "  Not running"

    echo ""
    echo "=== Tunnel ==="
    if [ -f "$TUNNEL_PID_FILE" ] && kill -0 $(cat "$TUNNEL_PID_FILE") 2>/dev/null; then
      echo "  Tunnel PID: $(cat "$TUNNEL_PID_FILE") (running)"
      grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$PROJECT_DIR/.tunnel.log" 2>/dev/null | tail -1 || echo "  Check .tunnel.log for URL"
    else
      echo "  No tunnel running"
    fi
    ;;

  logs)
    cd "$PROJECT_DIR"
    docker compose logs -f --tail=50 ${2:-}
    ;;

  test)
    print_step "Testing all endpoints..."
    BASE="http://localhost:8000"

    endpoints=(
      "GET  / "
      "GET  /cluster/nodes"
      "GET  /cluster/metrics"
      "GET  /billing/pricing"
      "GET  /spot/pricing"
      "GET  /autoscaler/policy"
      "GET  /cost/dashboard"
    )

    for ep in "${endpoints[@]}"; do
      method=$(echo $ep | awk '{print $1}')
      path=$(echo $ep | awk '{print $2}')
      status=$(curl -s -o /dev/null -w "%{http_code}" "${BASE}${path}")
      if [ "$status" = "200" ]; then
        echo -e "  ${GREEN}[OK]${NC} $method $path"
      else
        echo -e "  ${RED}[FAIL:$status]${NC} $method $path"
      fi
    done
    ;;

  *)
    echo "Usage: ./run-linux.sh [start|stop|tunnel|status|logs|test]"
    echo ""
    echo "Commands:"
    echo "  start   - Build and start all Docker services"
    echo "  tunnel  - Expose gateway via cloudflared/ngrok"
    echo "  stop    - Stop everything"
    echo "  status  - Show current status"
    echo "  logs    - View logs (optionally: ./run-linux.sh logs gateway)"
    echo "  test    - Test all API endpoints"
    ;;
esac
