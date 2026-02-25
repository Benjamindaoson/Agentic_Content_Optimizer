#!/bin/bash
# Growth Flywheel 2.5 — Production Deploy (Tencent Cloud Lighthouse)
set -e

COMPOSE_FILE="docker-compose.prod.yml"
BACKUP_TAG="backup-$(date +%Y%m%d-%H%M%S)"

echo "🚀 Growth Flywheel 2.5 — Production Deploy"
echo "=========================================="

# Pre-flight
if [ ! -f .env ]; then
    echo "❌ .env not found. Copy .env.example and configure."
    exit 1
fi

# Backup current API image
echo "📦 Backing up current API image..."
docker tag growth-flywheel-api:prod "growth-flywheel-api:${BACKUP_TAG}" 2>/dev/null || true

# Build & up
echo "🔨 Building and starting services..."
docker compose -f "$COMPOSE_FILE" build api
docker compose -f "$COMPOSE_FILE" up -d

# Wait for ready
echo "⏳ Waiting for /health/ready..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8080/health/ready >/dev/null 2>&1; then
        echo "✅ API ready"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "❌ API not ready after 30s"
        exit 1
    fi
    sleep 2
done

echo ""
echo "✅ Deploy complete"
echo "   API: http://localhost:8080"
echo "   Docs: http://localhost:8080/docs"
echo ""
echo "Rollback: docker tag growth-flywheel-api:${BACKUP_TAG} growth-flywheel-api:prod"
echo "          docker compose -f $COMPOSE_FILE up -d api"
