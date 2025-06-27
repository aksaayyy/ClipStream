#!/bin/bash

# ClipStack Service Manager
# Usage: ./run.sh [start|stop|restart|status|logs]

set -e

# Configuration
SERVICE_NAME="yt-fetcher"
LOG_FILE="yt-fetcher.log"
PID_FILE="yt-fetcher.pid"
PORT=${PORT:-8000}
KEEP_ALIVE=${KEEP_ALIVE:-60}
TIMEOUT=${TIMEOUT:-300}
UVICORN_CMD="uvicorn services.yt-fetcher.app.main:app --host 0.0.0.0 --port $PORT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Ensure we're in the project root
cd "$(dirname "$0")"

# Check if virtual environment exists and activate it
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating one...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies if needed
if [ ! -f "venv/.installed" ]; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install --upgrade pip
    pip install -r services/yt-fetcher/requirements.txt
    touch venv/.installed
fi

start_service() {
    if [ -f "$PID_FILE" ]; then
        echo "$SERVICE_NAME is already running (PID: $(cat $PID_FILE))"
        exit 1
    fi
    
    echo "Starting $SERVICE_NAME..."
    nohup python -m uvicorn services.yt-fetcher.app.main:app \
        --host 0.0.0.0 \
        --port $PORT \
        --timeout-keep-alive $KEEP_ALIVE \
        --timeout-graceful-shutdown $TIMEOUT \
        --log-level info \
        --no-access-log \
        --limit-concurrency 10 \
        --limit-max-requests 1000 > "$LOG_FILE" 2>&1 & echo $! > "$PID_FILE"
    
    echo "$SERVICE_NAME started with PID $(cat $PID_FILE)"
    echo "Logs: $PWD/$LOG_FILE"
    echo "Server timeout: $TIMEOUT seconds"
}

stop_service() {
    if [ ! -f "$PID_FILE" ]; then
        echo -e "${YELLOW}$SERVICE_NAME is not running${NC}"
        return 0
    fi
    
    PID=$(cat "$PID_FILE")
    if ps -p $PID > /dev/null 2>&1; then
        echo -e "${YELLOW}Stopping $SERVICE_NAME (PID: $PID)...${NC}"
        kill -TERM $PID
        rm -f "$PID_FILE"
        echo -e "${GREEN}Stopped $SERVICE_NAME${NC}"
    else
        echo -e "${YELLOW}$SERVICE_NAME is not running${NC}"
        rm -f "$PID_FILE"
    fi
}

status_service() {
    if [ -f "$PID_FILE" ] && ps -p $(cat "$PID_FILE") > /dev/null 2>&1; then
        echo -e "${GREEN}$SERVICE_NAME is running (PID: $(cat $PID_FILE))${NC}"
        echo -e "Logs: $(pwd)/$LOG_FILE"
        return 0
    else
        echo -e "${RED}$SERVICE_NAME is not running${NC}"
        return 1
    fi
}

show_logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -f "$LOG_FILE"
    else
        echo -e "${YELLOW}No log file found${NC}"
    fi
}

case "$1" in
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        stop_service
        sleep 2
        start_service
        ;;
    status)
        status_service
        ;;
    logs)
        show_logs
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        exit 1
        ;;
esac

exit 0
