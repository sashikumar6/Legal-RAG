#!/usr/bin/env bash
# Run the backend development server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT/backend"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt

# Set default environment variables
export FEDERAL_XML_BASE_PATH="${FEDERAL_XML_BASE_PATH:-$PROJECT_ROOT}"
export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://postgres:postgres@localhost:5432/federal_law_agent}"
export DATABASE_URL_SYNC="${DATABASE_URL_SYNC:-postgresql+psycopg2://postgres:postgres@localhost:5432/federal_law_agent}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"

echo ""
echo "=== Federal Law & Document AI Agent ==="
echo "  XML Path: $FEDERAL_XML_BASE_PATH"
echo "  API: http://localhost:8000"
echo "  Docs: http://localhost:8000/docs"
echo "======================================="
echo ""

# Run the server
uvicorn app.main:app --port 8000 --host 0.0.0.0
