#!/usr/bin/env bash
# Build and push to Docker Hub
# Usage:
#   export DOCKERHUB_USER=your-dockerhub-username
#   ./docker-publish.sh
# Optional: IMAGE_TAG=v1.0.0 ./docker-publish.sh

set -euo pipefail

cd "$(dirname "$0")"

DOCKERHUB_USER="${DOCKERHUB_USER:-}"
IMAGE_NAME="${IMAGE_NAME:-automated-book-generation-system}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

if [[ -z "$DOCKERHUB_USER" ]]; then
  echo "Error: Set your Docker Hub username first:"
  echo "  export DOCKERHUB_USER=yourusername"
  exit 1
fi

FULL_IMAGE="${DOCKERHUB_USER}/${IMAGE_NAME}:${IMAGE_TAG}"

echo "==> Building ${FULL_IMAGE}"
docker build -t "${FULL_IMAGE}" .

echo "==> Pushing ${FULL_IMAGE}"
docker push "${FULL_IMAGE}"

echo ""
echo "Done! Pull anywhere with:"
echo "  docker pull ${FULL_IMAGE}"
echo ""
echo "Run (pass env file with Supabase + OpenRouter keys):"
echo "  docker run -p 8000:8000 --env-file .env ${FULL_IMAGE}"
