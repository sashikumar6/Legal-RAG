#!/bin/bash
# High-MoJo Deployment Script for Legal AI Agent
# =============================================================================

set -e

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INFRA_DIR="$PROJECT_ROOT/infra"
BACKEND_DIR="$PROJECT_ROOT/backend"

echo "🚀 Starting Deployment for Legal AI Agent (Optimized Size)..."

# 1. Environment Pre-flight
if [ ! -f "$INFRA_DIR/.env" ]; then
    echo "⚠️  infra/.env not found. Copying from .env.example..."
    cp "$INFRA_DIR/.env.example" "$INFRA_DIR/.env"
fi

# 2. Build and Start Services
echo "🛠️  Building Docker images with 'full' profile (includes monitoring)..."
docker compose -f "$INFRA_DIR/docker-compose.yml" --profile full build

echo "📡 Starting all services in the background..."
docker compose -f "$INFRA_DIR/docker-compose.yml" --profile full up -d

# 3. Wait for Services
echo "⏳ Waiting for Database and Vector Store to be ready..."
sleep 10

# 4. Initialize Data (Trimmed Corpus)
echo "📚 Ingesting Optimized Federal Corpus (Titles 11 & 18)..."
docker exec -it infra-backend-1 python -m app.ingestion.run_ingestion

echo "✅ Deployment Complete!"
echo "-----------------------------------------------------------------------"
echo "Frontend:  http://localhost:3000"
echo "Backend:   http://localhost:8000/api/v1"
echo "Grafana:   http://localhost:3001 (Monitoring Dashboard)"
echo "Prometheus: http://localhost:9090"
echo "-----------------------------------------------------------------------"
echo "Use 'docker compose --profile full logs -f' to monitor technical logs."
