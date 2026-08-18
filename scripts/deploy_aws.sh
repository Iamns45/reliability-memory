#!/usr/bin/env bash
set -euo pipefail

AWS_STACK_NAME="${AWS_STACK_NAME:-reliability-memory}"
AWS_DEPLOY_REGION="${AWS_DEPLOY_REGION:-us-east-1}"
AWS_SAM_TEMPLATE="infra/aws/template.yaml"
DATABASE_SECRET_ARN="${DATABASE_SECRET_ARN:-}"
MCP_SECRET_ARN="${COCKROACH_MCP_SECRET_ARN:-}"
SKIP_DATA_PREP="${SKIP_DATA_PREP:-false}"
SECRET_FILE=""
MCP_SECRET_FILE=""

cleanup() {
  if [[ -n "${SECRET_FILE}" && -f "${SECRET_FILE}" ]]; then
    rm -f -- "${SECRET_FILE}"
  fi
  if [[ -n "${MCP_SECRET_FILE}" && -f "${MCP_SECRET_FILE}" ]]; then
    rm -f -- "${MCP_SECRET_FILE}"
  fi
}
trap cleanup EXIT

if [[ -z "${DATABASE_SECRET_ARN}" && -z "${DATABASE_URL:-}" ]]; then
  echo "Set DATABASE_SECRET_ARN or DATABASE_URL for CockroachDB Cloud." >&2
  exit 1
fi

if [[ -z "${COCKROACH_MCP_CLUSTER_ID:-}" ]]; then
  echo "Set COCKROACH_MCP_CLUSTER_ID to the CockroachDB Cloud cluster ID." >&2
  exit 1
fi

if [[ -z "${MCP_SECRET_ARN}" && -z "${COCKROACH_MCP_API_KEY:-}" ]]; then
  echo "Set COCKROACH_MCP_SECRET_ARN or COCKROACH_MCP_API_KEY." >&2
  exit 1
fi

if [[ "${SKIP_DATA_PREP}" != "true" && "${SKIP_DATA_PREP}" != "false" ]]; then
  echo "SKIP_DATA_PREP must be true or false." >&2
  exit 1
fi

for required_command in aws curl docker node npm openssl python3 sam; do
  if ! command -v "${required_command}" >/dev/null 2>&1; then
    echo "Missing required command: ${required_command}" >&2
    exit 1
  fi
done

COCKROACH_CA_CERT="services/api/certs/cockroach-cloud-ca.pem"
if [[ ! -s "${COCKROACH_CA_CERT}" ]]; then
  echo "Missing CockroachDB Cloud CA bundle: ${COCKROACH_CA_CERT}" >&2
  exit 1
fi
if ! openssl crl2pkcs7 -nocrl -certfile "${COCKROACH_CA_CERT}" \
  | openssl pkcs7 -print_certs -noout >/dev/null; then
  echo "Invalid CockroachDB Cloud CA bundle: ${COCKROACH_CA_CERT}" >&2
  exit 1
fi

aws sts get-caller-identity --region "${AWS_DEPLOY_REGION}" >/dev/null
docker info >/dev/null
node -e 'const [major, minor] = process.versions.node.split(".").map(Number); if (major < 22 || (major === 22 && minor < 13)) process.exit(1)' || {
  echo "Node.js 22.13 or newer is required." >&2
  exit 1
}

# Reproduce the lockfile exactly and include build tooling even when the caller
# has NODE_ENV=production. This keeps a fresh deployment checkout self-contained.
npm ci --include=dev --no-audit --no-fund

if [[ -z "${DATABASE_SECRET_ARN}" ]]; then
  SECRET_NAME="${AWS_STACK_NAME}/cockroachdb/database-url"
  SECRET_FILE="$(mktemp)"
  chmod 600 "${SECRET_FILE}"
  printf '%s' "${DATABASE_URL}" >"${SECRET_FILE}"

  DATABASE_SECRET_ARN="$(aws secretsmanager describe-secret \
    --secret-id "${SECRET_NAME}" \
    --region "${AWS_DEPLOY_REGION}" \
    --query ARN \
    --output text 2>/dev/null || true)"

  if [[ -n "${DATABASE_SECRET_ARN}" && "${DATABASE_SECRET_ARN}" != "None" ]]; then
    aws secretsmanager update-secret \
      --secret-id "${DATABASE_SECRET_ARN}" \
      --secret-string "file://${SECRET_FILE}" \
      --region "${AWS_DEPLOY_REGION}" >/dev/null
  else
    DATABASE_SECRET_ARN="$(aws secretsmanager create-secret \
      --name "${SECRET_NAME}" \
      --description "CockroachDB URL for Reliability Memory" \
      --secret-string "file://${SECRET_FILE}" \
      --region "${AWS_DEPLOY_REGION}" \
      --query ARN \
      --output text)"
  fi

  rm -f -- "${SECRET_FILE}"
  SECRET_FILE=""
fi

if [[ -z "${MCP_SECRET_ARN}" ]]; then
  MCP_SECRET_NAME="${AWS_STACK_NAME}/cockroachdb/managed-mcp-api-key"
  MCP_SECRET_FILE="$(mktemp)"
  chmod 600 "${MCP_SECRET_FILE}"
  printf '%s' "${COCKROACH_MCP_API_KEY}" >"${MCP_SECRET_FILE}"

  MCP_SECRET_ARN="$(aws secretsmanager describe-secret \
    --secret-id "${MCP_SECRET_NAME}" \
    --region "${AWS_DEPLOY_REGION}" \
    --query ARN \
    --output text 2>/dev/null || true)"

  if [[ -n "${MCP_SECRET_ARN}" && "${MCP_SECRET_ARN}" != "None" ]]; then
    aws secretsmanager update-secret \
      --secret-id "${MCP_SECRET_ARN}" \
      --secret-string "file://${MCP_SECRET_FILE}" \
      --region "${AWS_DEPLOY_REGION}" >/dev/null
  else
    MCP_SECRET_ARN="$(aws secretsmanager create-secret \
      --name "${MCP_SECRET_NAME}" \
      --description "CockroachDB Managed MCP service-account key for Reliability Memory" \
      --secret-string "file://${MCP_SECRET_FILE}" \
      --region "${AWS_DEPLOY_REGION}" \
      --query ARN \
      --output text)"
  fi

  rm -f -- "${MCP_SECRET_FILE}"
  MCP_SECRET_FILE=""
fi

python3 -c 'import boto3, psycopg' || {
  echo "Python deployment dependencies are missing. Install services/api/requirements.txt." >&2
  exit 1
}

if [[ "${SKIP_DATA_PREP}" == "false" ]]; then
  if [[ -n "${DATABASE_URL:-}" ]]; then
    python3 scripts/migrate_and_seed.py --episodes "${SEED_EPISODES:-5000}"
    python3 scripts/reindex_embeddings.py \
      --region "${AWS_DEPLOY_REGION}" \
      --requests-per-second "${EMBEDDING_REQUESTS_PER_SECOND:-10}"
  else
    python3 scripts/migrate_and_seed.py \
      --secret-arn "${DATABASE_SECRET_ARN}" \
      --region "${AWS_DEPLOY_REGION}" \
      --episodes "${SEED_EPISODES:-5000}"
    python3 scripts/reindex_embeddings.py \
      --secret-arn "${DATABASE_SECRET_ARN}" \
      --region "${AWS_DEPLOY_REGION}" \
      --requests-per-second "${EMBEDDING_REQUESTS_PER_SECOND:-10}"
  fi
else
  echo "Skipping database migrations, seed, and embedding re-index for this redeploy."
fi
unset DATABASE_URL
unset COCKROACH_MCP_API_KEY

npm run build:aws-ui
sam build --template-file "${AWS_SAM_TEMPLATE}"
sam deploy \
  --template-file .aws-sam/build/template.yaml \
  --stack-name "${AWS_STACK_NAME}" \
  --region "${AWS_DEPLOY_REGION}" \
  --capabilities CAPABILITY_IAM \
  --resolve-s3 \
  --resolve-image-repos \
  --no-confirm-changeset \
  --no-fail-on-empty-changeset \
  --parameter-overrides \
    "DatabaseSecretArn=${DATABASE_SECRET_ARN}" \
    "McpSecretArn=${MCP_SECRET_ARN}" \
    "McpClusterId=${COCKROACH_MCP_CLUSTER_ID}" \
    "AllowedOrigin=*"

JUDGE_BUCKET="$(aws cloudformation describe-stacks \
  --stack-name "${AWS_STACK_NAME}" \
  --region "${AWS_DEPLOY_REGION}" \
  --query "Stacks[0].Outputs[?OutputKey=='JudgeUiBucketName'].OutputValue" \
  --output text)"
JUDGE_DISTRIBUTION_ID="$(aws cloudformation describe-stacks \
  --stack-name "${AWS_STACK_NAME}" \
  --region "${AWS_DEPLOY_REGION}" \
  --query "Stacks[0].Outputs[?OutputKey=='JudgeUiDistributionId'].OutputValue" \
  --output text)"
JUDGE_URL="$(aws cloudformation describe-stacks \
  --stack-name "${AWS_STACK_NAME}" \
  --region "${AWS_DEPLOY_REGION}" \
  --query "Stacks[0].Outputs[?OutputKey=='JudgeUrl'].OutputValue" \
  --output text)"

if [[ -z "${JUDGE_BUCKET}" || -z "${JUDGE_DISTRIBUTION_ID}" || -z "${JUDGE_URL}" ]]; then
  echo "AWS stack did not return the expected judge UI outputs." >&2
  exit 1
fi

aws s3 sync dist-aws-ui "s3://${JUDGE_BUCKET}" \
  --region "${AWS_DEPLOY_REGION}" \
  --delete \
  --cache-control "public,max-age=300"
aws s3 sync dist-aws-ui/assets "s3://${JUDGE_BUCKET}/assets" \
  --region "${AWS_DEPLOY_REGION}" \
  --cache-control "public,max-age=31536000,immutable"
aws s3 cp dist-aws-ui/index.html "s3://${JUDGE_BUCKET}/index.html" \
  --region "${AWS_DEPLOY_REGION}" \
  --cache-control "no-cache,no-store,must-revalidate" \
  --content-type "text/html; charset=utf-8"
INVALIDATION_ID="$(aws cloudfront create-invalidation \
  --distribution-id "${JUDGE_DISTRIBUTION_ID}" \
  --paths "/*" \
  --query Invalidation.Id \
  --output text)"
aws cloudfront wait invalidation-completed \
  --distribution-id "${JUDGE_DISTRIBUTION_ID}" \
  --id "${INVALIDATION_ID}"
curl --fail --silent --show-error \
  --retry 8 \
  --retry-all-errors \
  --retry-delay 5 \
  "${JUDGE_URL}/health" | python3 -c '
import json, sys
health = json.load(sys.stdin)
if health.get("memory") != "cockroachdb":
    raise SystemExit("AWS health check did not confirm CockroachDB memory")
if health.get("model") != "amazon-bedrock":
    raise SystemExit("AWS health check did not confirm Amazon Bedrock")
if health.get("mcp", {}).get("status") != "configured":
    raise SystemExit("AWS health check did not confirm Managed MCP")
if health.get("mcp", {}).get("required_for_autonomy") is not True:
    raise SystemExit("Managed MCP is not required for autonomous execution")
'

SMOKE_ID="deploy-smoke-$(date +%s)-${RANDOM}"
curl --fail --silent --show-error \
  --retry 3 \
  --retry-all-errors \
  --retry-delay 3 \
  -X POST \
  -H 'Content-Type: application/json' \
  -H "Idempotency-Key: ${SMOKE_ID}" \
  -d '{"case_id":"CASE-202-26","customer_id":"C-202","request_text":"Deployment readiness check","requested_amount":89}' \
  "${JUDGE_URL}/v1/cases/run" | python3 -c '
import json, sys
payload = json.load(sys.stdin)
run = payload.get("result") or {}
receipt = run.get("mcp_verification") or {}
if receipt.get("verified") is not True:
    raise SystemExit("Deployment smoke test did not receive a verified Managed MCP receipt")
if receipt.get("observed_episode_id") != run.get("run_id"):
    raise SystemExit("Managed MCP did not observe the persisted smoke-test episode")
if not receipt.get("vector_check_performed"):
    raise SystemExit("Managed MCP did not replay the vector-memory query")
if not run.get("execution") or not run.get("verification", {}).get("success"):
    raise SystemExit("Deployment smoke workflow did not execute and verify")
'

echo "Judge URL: ${JUDGE_URL}"
