#!/usr/bin/env bash
set -euo pipefail

OWNER=${OWNER:-"evilpandas"}
IMAGE=${IMAGE:-"pm"}
TAG=${TAG:-"latest"}

FULL_IMAGE="ghcr.io/${OWNER}/${IMAGE}:${TAG}"

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI is required. Install it first."
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "Run 'gh auth login' first."
  exit 1
fi

echo "Authenticating Docker to GHCR..."
if ! gh auth token | docker login ghcr.io -u "${OWNER}" --password-stdin; then
  echo "Docker login to ghcr.io failed."
  exit 1
fi

echo "Building ${FULL_IMAGE}..."
docker build -t "${FULL_IMAGE}" .

echo "Pushing ${FULL_IMAGE}..."
docker push "${FULL_IMAGE}"

echo "Published ${FULL_IMAGE}"
