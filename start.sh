#!/bin/bash
# Start the Portfolio Dashboard server
# Usage: ./start.sh [--http]

cd "$(dirname "$0")"
source venv/bin/activate

# Kill any existing server on port 8000
lsof -ti:8000 | xargs kill -9 2>/dev/null

if [ "$1" == "--http" ]; then
    echo "Starting server (HTTP)..."
    echo "Access at: http://localhost:8000"
    python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
else
    # Check if certs exist
    if [ ! -f "certs/cert.pem" ] || [ ! -f "certs/key.pem" ]; then
        echo "Generating SSL certificates..."
        mkdir -p certs
        MY_IP=$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')
        openssl req -x509 -newkey rsa:4096 -keyout certs/key.pem -out certs/cert.pem \
            -days 365 -nodes -subj "/CN=Portfolio Dashboard" \
            -addext "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:${MY_IP}" 2>/dev/null
        echo "Certificates created in certs/"
    fi

    MY_IP=$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')
    echo "Starting server (HTTPS)..."
    echo ""
    echo "Access at:"
    echo "  Local:   https://localhost:8000"
    echo "  Network: https://${MY_IP}:8000"
    echo ""
    echo "Note: Browser will warn about self-signed cert - click 'Advanced' -> 'Proceed'"
    echo ""
    python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 \
        --ssl-keyfile certs/key.pem --ssl-certfile certs/cert.pem
fi
