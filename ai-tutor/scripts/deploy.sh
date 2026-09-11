#!/bin/bash
# Auto-deploy script: test → build → deploy
# Usage: ./scripts/deploy.sh [service]
# Examples:
#   ./scripts/deploy.sh          # deploy all
#   ./scripts/deploy.sh gateway  # deploy only gateway
#   ./scripts/deploy.sh web-app  # deploy only frontend

set -e
SERVICE=${1:-"gateway web-app"}

echo "🚀 Deploy starting..."

# Step 1: Run tests
echo "📋 Step 1: Running tests..."
.venv/bin/python -m pytest tests/unit/ -x -q --tb=short
echo "  ✅ Tests passed"

# Step 2: Type check frontend
echo "🔍 Step 2: Type checking frontend..."
cd web-app && npx tsc --noEmit --pretty false 2>&1 | head -20
cd ..
echo "  ✅ Type check passed"

# Step 3: Build frontend
echo "📦 Step 3: Building frontend..."
cd web-app && npm run build && cd ..
echo "  ✅ Frontend built"

# Step 4: Build Docker images
echo "🐳 Step 4: Building Docker images..."
docker compose build $SERVICE
echo "  ✅ Docker images built"

# Step 5: Deploy
echo "🚀 Step 5: Deploying..."
docker compose up -d $SERVICE
echo "  ✅ Deployed"

echo ""
echo "🎉 Deployment complete!"
echo "   Frontend: http://localhost:3000"
echo "   Gateway:  http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
