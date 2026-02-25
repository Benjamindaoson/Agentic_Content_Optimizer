#!/bin/bash
# Growth Flywheel 2.5 — Production Rollback
set -e

COMPOSE_FILE="docker-compose.prod.yml"

echo "🔄 Growth Flywheel 2.5 — Production Rollback"
echo "==========================================="

# List available backups
BACKUPS=$(docker images --format '{{.Repository}}:{{.Tag}}' | grep 'growth-flywheel-api:backup-' | sort -r)
if [ -z "$BACKUPS" ]; then
    echo "❌ No backup images found"
    exit 1
fi

# Use latest backup
LATEST=$(echo "$BACKUPS" | head -1)
echo "Rolling back to: $LATEST"

docker tag "$LATEST" growth-flywheel-api:prod
docker compose -f "$COMPOSE_FILE" up -d api

echo "⏳ Waiting for /health/ready..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8080/health/ready >/dev/null 2>&1; then
        echo "✅ Rollback complete"
        exit 0
    fi
    sleep 2
done

echo "⚠️  API may still be starting. Check: docker compose -f $COMPOSE_FILE logs -f api"
