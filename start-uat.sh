#!/bin/bash
cd /Users/claw/projects/dam

# Load UAT environment
if [ -f .env.uat ]; then
  export $(cat .env.uat | grep -v '^#' | xargs)
fi

source .venv/bin/activate
python -m flask run --host 0.0.0.0 --port ${DAM_PORT:-8009} --cert cert.pem --key key.pem
