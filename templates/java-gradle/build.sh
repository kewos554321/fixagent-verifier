#!/bin/bash
# Script to build the Docker image

set -e

IMAGE_NAME="fixagent-verifier:java-gradle"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Building Docker image: $IMAGE_NAME"
docker build -t "$IMAGE_NAME" "$SCRIPT_DIR"

echo "✓ Image built successfully: $IMAGE_NAME"
docker images | grep fixagent-verifier
