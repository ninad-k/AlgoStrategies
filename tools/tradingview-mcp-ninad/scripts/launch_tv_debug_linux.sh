#!/bin/bash
# Launch TradingView Desktop on Linux with Chrome DevTools Protocol enabled.
# Usage: ./scripts/launch_tv_debug_linux.sh [port]

PORT="${1:-9222}"

# Find the binary
TV_PATH=""
for p in \
    /opt/TradingView/tradingview \
    /opt/TradingView/TradingView \
    "$HOME/.local/share/TradingView/TradingView" \
    /usr/bin/tradingview \
    /snap/tradingview/current/tradingview; do
    if [ -f "$p" ]; then
        TV_PATH="$p"
        break
    fi
done

if [ -z "$TV_PATH" ]; then
    TV_PATH=$(which tradingview 2>/dev/null)
fi

if [ -z "$TV_PATH" ] || [ ! -f "$TV_PATH" ]; then
    echo "TradingView not found. Install it from https://www.tradingview.com/desktop/"
    exit 1
fi

pkill -f TradingView 2>/dev/null
sleep 1

echo "Launching TradingView with CDP on port $PORT..."
"$TV_PATH" --remote-debugging-port="$PORT" &
disown

echo "Waiting for CDP..."
for i in $(seq 1 15); do
    if curl -s "http://localhost:$PORT/json/version" > /dev/null 2>&1; then
        echo "TradingView ready on http://localhost:$PORT"
        exit 0
    fi
    sleep 1
done

echo "TradingView launched but CDP not ready yet. Try again in a few seconds."
