#!/bin/bash
cd /Users/claw/projects/dam

# Load .env.local for database path and configuration
if [ -f .env.local ]; then
  export $(cat .env.local | grep -v '^#' | xargs)
fi

source .venv/bin/activate
python -m flask run --host 0.0.0.0 --port ${DAM_PORT:-8008} --cert cert.pem --key key.pem >> /Users/claw/projects/dam/logs/server.log 2>&1 &
