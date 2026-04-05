#!/bin/bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
cd "$(dirname "$0")"
npx vite dev --port 1420 --strictPort --host 127.0.0.1
