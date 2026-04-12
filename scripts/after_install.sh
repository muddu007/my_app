#!/bin/bash
set -e

echo "========================================="
echo "HOOK: AfterInstall"
echo "Timestamp: $(date)"
echo "========================================="

# Verify the new task set has been created
echo ">> Verifying new task set was created..."
TASK_SETS=$(aws ecs describe-services \
  --cluster "$ECS_CLUSTER_NAME" \
  --services "$ECS_SERVICE_NAME" \
  --region "$AWS_DEFAULT_REGION" \
  --query 'services[0].taskSets[*].{ID:id,Status:status,Scale:scale}' \
  --output table 2>&1)

echo "$TASK_SETS"

if [ -z "$TASK_SETS" ]; then
  echo "ERROR: No task sets found after install"
  exit 1
fi

# Verify ECR image exists
echo ">> Verifying Docker image exists in ECR..."
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REGISTRY="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com"

IMAGE_EXISTS=$(aws ecr describe-images \
  --repository-name "$IMAGE_REPO_NAME" \
  --image-ids imageTag=latest \
  --region "$AWS_DEFAULT_REGION" \
  --query 'imageDetails[0].imageTags' \
  --output text 2>&1)

if [ -z "$IMAGE_EXISTS" ] || echo "$IMAGE_EXISTS" | grep -q "error\|Error"; then
  echo "ERROR: Image not found in ECR: $ECR_REGISTRY/$IMAGE_REPO_NAME:latest"
  exit 1
fi

echo "Image verified: $ECR_REGISTRY/$IMAGE_REPO_NAME:latest"
echo "AfterInstall hook completed successfully."
exit 0