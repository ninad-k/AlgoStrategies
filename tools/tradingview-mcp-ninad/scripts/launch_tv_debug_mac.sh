#!/bin/bash
# Launch TradingView Desktop on macOS with Chrome DevTools Protocol enabled.
# Usage: ./scripts/launch_tv_debug_mac.sh [port]

PORT="${1:-9222}"

# Find the binary
TV_PATH="/Applications/TradingView.app/Contents/MacOS/TradingView"
if [ ! -f "$TV_PATH" ]; then
    TV_PATH="$HOME/Applications/TradingView.app/Contents/MacOS/TradingView"
fi
if [ ! -f "$TV_PATH" ]; then
    TV_PATH=$(mdfind "kMDItemFSName == TradingView.app" 2>/dev/null | head -1)
    if [ -n "$TV_PATH" ]; then
        TV_PATH="$TV_PATH/Contents/MacOS/TradingView"
    fi
fi

if [ ! -f "$TV_PATH" ]; then
    echo "TradingView not found. Install it from https://www.tradingview.com/desktop/"
    exit 1
fi

# Kill any running instance
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
