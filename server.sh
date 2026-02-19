#!/bin/bash
# FantasyFolio Test Server Management
# Usage: ./server.sh [start|stop|restart|status]

cd /Users/claw/projects/dam
PID_FILE="$HOME/.openclaw/workspace/fantasyfolio-test.pid"

start() {
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "Flask already running (PID $(cat "$PID_FILE"))"
        return 1
    fi
    
    source .venv/bin/activate
    export $(grep -v '^#' .env.local | xargs)
    
    nohup flask run --host 0.0.0.0 --port 8008 --cert cert.pem --key key.pem > /dev/null 2>&1 &
    echo $! > "$PID_FILE"
    sleep 1
    
    if kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "Flask started (PID $(cat "$PID_FILE")"
        echo "URL: https://192.168.50.190:8008"
    else
        echo "Failed to start Flask"
        rm -f "$PID_FILE"
        return 1
    fi
}

stop() {
    if [ ! -f "$PID_FILE" ]; then
        echo "Flask not running (no PID file)"
        return 1
    fi
    
    PID=$(cat "$PID_FILE")
    if kill -0 $PID 2>/dev/null; then
        kill $PID
        rm -f "$PID_FILE"
        echo "Flask stopped (PID $PID)"
    else
        echo "Flask not running (stale PID file)"
        rm -f "$PID_FILE"
    fi
}

status() {
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        PID=$(cat "$PID_FILE")
        echo "Flask running (PID $PID)"
        ps -p $PID -o pid,etime,command | tail -1
        curl -k -s -o /dev/null -w "Status: %{http_code}\n" https://192.168.50.190:8008/
    else
        echo "Flask not running"
        [ -f "$PID_FILE" ] && rm -f "$PID_FILE"
    fi
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        sleep 1
        start
        ;;
    status)
        status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
