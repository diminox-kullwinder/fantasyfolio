#!/bin/bash
# FantasyFolio UAT Server Start Script
cd /Users/claw/projects/dam

# Load UAT environment (supports both old DAM_ and new FANTASYFOLIO_ vars)
if [ -f .env.uat ]; then
  export $(cat .env.uat | grep -v '^#' | xargs)
fi

source .venv/bin/activate
export FLASK_APP=fantasyfolio.app
python -m flask run --host 0.0.0.0 --port ${FANTASYFOLIO_PORT:-${DAM_PORT:-8009}} --cert cert.pem --key key.pem
