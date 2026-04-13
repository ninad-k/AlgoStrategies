#!/usr/bin/env bash
# ReySentinel — One-Click Deploy Script
# ================================================
# Usage: ./deploy.sh [up|down|restart|logs|status]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$COMPOSE_DIR/docker-compose.yml"
PROJECT_NAME="reysentinel"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_prerequisites() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
    if ! docker info &> /dev/null 2>&1; then
        log_error "Docker daemon is not running"
        exit 1
    fi
}

compose_cmd() {
    if docker compose version &> /dev/null 2>&1; then
        docker compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" "$@"
    else
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" "$@"
    fi
}

cmd_up() {
    log_info "Building and starting ReySentinel..."
    compose_cmd up -d --build
    log_info "Waiting for services to be healthy..."
    sleep 5
    cmd_status
    echo ""
    log_info "ReySentinel is running!"
    log_info "  Main Engine:       http://localhost:8060"
    log_info "  Heatmap Dashboard: http://localhost:8061"
    log_info "  Multi-Account:     http://localhost:8062"
    log_info "  API Docs:          http://localhost:8060/docs"
}

cmd_down() {
    log_info "Stopping ReySentinel..."
    compose_cmd down
    log_info "All services stopped."
}

cmd_restart() {
    log_info "Restarting ReySentinel..."
    compose_cmd restart
    sleep 3
    cmd_status
}

cmd_logs() {
    compose_cmd logs -f --tail=100
}

cmd_status() {
    log_info "Service status:"
    compose_cmd ps
}

# ---- Main ----
check_prerequisites

ACTION="${1:-up}"

case "$ACTION" in
    up)       cmd_up ;;
    down)     cmd_down ;;
    restart)  cmd_restart ;;
    logs)     cmd_logs ;;
    status)   cmd_status ;;
    *)
        echo "Usage: $0 [up|down|restart|logs|status]"
        echo "  up       - Build and start all services (default)"
        echo "  down     - Stop and remove all services"
        echo "  restart  - Restart all services"
        echo "  logs     - Follow service logs"
        echo "  status   - Show service status"
        exit 1
        ;;
esac
