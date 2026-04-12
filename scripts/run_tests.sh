#!/bin/bash
set -e

echo "========================================="
echo "Running integration tests on TEST listener"
echo "========================================="

# Replace with your ALB test listener URL (port 8080 by default in Blue/Green)
TEST_ENDPOINT="http://fargate-load-balancer-730437436.ap-south-1.elb.amazonaws.com:80"

echo "Testing endpoint: $TEST_ENDPOINT"

# --- Health Check ---
echo ">> Health check..."
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$TEST_ENDPOINT")
if [ "$HTTP_STATUS" != "200" ]; then
  echo "FAILED: Health check returned $HTTP_STATUS"
  exit 1
fi
echo "Health check passed (200 OK)"
echo "All tests passed. Allowing traffic shift."
exit 0