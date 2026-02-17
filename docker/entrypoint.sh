#!/bin/bash
set -e

echo "[INIT] FantasyFolio starting..."

# Initialize database if it doesn't exist
if [ ! -f /app/data/fantasyfolio.db ]; then
    echo "[INIT] No database found, creating from schema.sql..."
    sqlite3 /app/data/fantasyfolio.db < /app/schema.sql
    echo "[INIT] Database initialized successfully"
else
    echo "[INIT] Database exists, skipping initialization"
fi

# Execute the main command
exec "$@"
