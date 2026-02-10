#!/bin/bash
# FantasyFolio Server Start Script
# Starts the Flask server with HTTPS on port 8008

cd /Users/claw/projects/dam
source .venv/bin/activate

export FLASK_APP=fantasyfolio.app
export FANTASYFOLIO_DATABASE_PATH=/Users/claw/.openclaw/workspace/dam/data/dam.db

exec .venv/bin/python -m flask run \
  --host 0.0.0.0 \
  --port 8008 \
  --cert cert.pem \
  --key key.pem
