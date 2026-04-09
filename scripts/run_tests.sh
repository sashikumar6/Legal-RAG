#!/usr/bin/env bash
# Run the test suite

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT/backend"

# Set test environment
export FEDERAL_XML_BASE_PATH="$PROJECT_ROOT"
export ENVIRONMENT=development
export DEBUG=true
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/federal_law_agent"
export DATABASE_URL_SYNC="postgresql+psycopg2://postgres:postgres@localhost:5432/federal_law_agent"

echo "Running tests..."
python -m pytest app/tests/ -v --tb=short "$@"
