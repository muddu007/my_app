#!/bin/bash
set -e

echo "========================================="
echo "HOOK: BeforeInstall"
echo "Timestamp: $(date)"
echo "========================================="

# Verify AWS CLI is available
if ! command -v aws &> /dev/null; then
  echo "ERROR: AWS CLI not found"
  exit 1
fi

# Verify required environment variables
echo ">> Checking environment variables..."
REQUIRED_VARS=("ECS_CLUSTER_NAME" "ECS_SERVICE_NAME" "AWS_DEFAULT_REGION")
for VAR in "${REQUIRED_VARS[@]}"; do
  if [ -z "${!VAR}" ]; then
    echo "WARNING: $VAR is not set"
  else
    echo "OK: $VAR = ${!VAR}"
  fi
done

# Log current ECS service status
echo ">> Fetching current ECS service status..."
aws ecs describe-services \
  --cluster "$ECS_CLUSTER_NAME" \
  --services "$ECS_SERVICE_NAME" \
  --region "$AWS_DEFAULT_REGION" \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount,Pending:pendingCount}' \
  --output table 2>&1 || echo "WARNING: Could not fetch ECS service status"

# Log current task definition in use
echo ">> Current task definition in use:"
aws ecs describe-services \
  --cluster "$ECS_CLUSTER_NAME" \
  --services "$ECS_SERVICE_NAME" \
  --region "$AWS_DEFAULT_REGION" \
  --query 'services[0].taskDefinition' \
  --output text 2>&1 || echo "WARNING: Could not fetch task definition"

echo "BeforeInstall hook completed successfully."
exit 0