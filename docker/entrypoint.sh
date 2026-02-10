#!/bin/bash
# FantasyFolio Container Entrypoint
# Ensures schema.sql is available even when /app/data is a volume mount

# Copy schema.sql to data directory if not present
if [ ! -f /app/data/schema.sql ]; then
    echo "Copying schema.sql to data directory..."
    cp /app/schema.sql /app/data/schema.sql
fi

# Execute the main command (supervisord)
exec "$@"
