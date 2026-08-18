# AWS deployment

> Status: Current
>
> Audience: Release engineers and operators
>
> Owner: Reliability Memory operations maintainers
>
> Last reviewed: 2026-08-16

## Outcome

The stack creates one public HTTPS judge URL. CloudFront serves the React UI from a private S3 bucket and forwards `/health` and `/v1/*` to API Gateway. API Gateway invokes a FastAPI Lambda container that calls Amazon Bedrock and CockroachDB Cloud.

## Services

| Service           | Responsibility                                                                             |
| ----------------- | ------------------------------------------------------------------------------------------ |
| CloudFront        | Public HTTPS, same-origin routing, compression, and security headers                       |
| S3                | Private static UI origin                                                                   |
| API Gateway       | Public API routes, access logging, throttling, and CORS                                    |
| Lambda            | FastAPI, one-node LangGraph, evidence evaluator, and deterministic policy                  |
| Bedrock           | Nova Lite proposals and Titan V2 embeddings                                                |
| Secrets Manager   | CockroachDB URL and Managed MCP service-account key                                        |
| CloudWatch Logs   | API and function logs with 14-day retention                                                |
| CockroachDB Cloud | Cases, evidence bundles, episodes, vectors, outcomes, corrections, audits, and checkpoints |

## Prerequisites

- Authenticated AWS CLI for the target account
- AWS SAM CLI and running Docker daemon
- Node.js 22.13+ and Python 3.13 dependencies
- CockroachDB Cloud 25.4+ connection URL
- CockroachDB Cloud Managed MCP service account assigned the Cluster Operator role and scoped to the target cluster
- Bedrock access to `amazon.nova-lite-v1:0` and `amazon.titan-embed-text-v2:0`

## Configuration

Provide either a URL for the script to store:

```bash
export DATABASE_URL='postgresql://reliability_runtime:REDACTED@HOST/reliability_memory?sslmode=verify-full'
```

The Lambda image includes the CockroachDB Cloud CA bundle and sets
`PGSSLROOTCERT=/var/task/certs/cockroach-cloud-ca.pem`. The database URL keeps
`sslmode=verify-full`, so the driver verifies both the certificate chain and the
cluster hostname without relying on a workstation-only `~/.postgresql/root.crt`
path.
Certificate and hostname verification remain enabled.

Or an existing secret ARN containing the URL or a JSON `DATABASE_URL` field:

```bash
export DATABASE_SECRET_ARN='arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:NAME'
```

Provide the cluster ID and either a service-account API key for the script to store or an existing secret ARN:

```bash
export COCKROACH_MCP_CLUSTER_ID='your-cluster-id'
read -r -s 'COCKROACH_MCP_API_KEY?Paste the service-account API key: '
export COCKROACH_MCP_API_KEY
```

```bash
export COCKROACH_MCP_CLUSTER_ID='your-cluster-id'
export COCKROACH_MCP_SECRET_ARN='arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:NAME'
```

The browser never receives this key. Lambda reads it from Secrets Manager and sends it only as the bearer credential for the cluster-scoped `https://cockroachlabs.cloud/mcp` connection.

Validate the connection before deploying. The command prints only a shortened cluster ID, database metadata, and three vector neighbors; it never prints the key:

```bash
python scripts/verify_managed_mcp.py
```

Optional values: `AWS_STACK_NAME`, `AWS_DEPLOY_REGION`, `SEED_EPISODES`,
`EMBEDDING_REQUESTS_PER_SECOND`, and `SKIP_DATA_PREP`. Defaults are
`reliability-memory`, `us-east-1`, `5000`, `10`, and `false`. Set
`SKIP_DATA_PREP=true` only for an application or infrastructure redeploy after
the target database has already passed its migrations, seed, and embedding
index checks.

## Deploy

```bash
npm run check
npm run audit:prod
./scripts/deploy_aws.sh
```

For a code-only or infrastructure-only update against the already-prepared
database:

```bash
SKIP_DATA_PREP=true ./scripts/deploy_aws.sh
```

The script:

1. Verifies AWS identity, Docker, Node, Python dependencies, and SAM.
2. Creates or reuses separate database and Managed MCP secrets.
3. Applies all numbered migrations, upserts the 26 evidence cases, seeds the
   base corpus, and idempotently adds 150 case-shaped verified episodes for
   each context expected to earn autonomy.
4. Resume-safely replaces non-production memory vectors with normalized Titan
   V2 vectors, reuses embeddings for identical inputs, and records model and
   input provenance on every row.
5. Builds the static UI and Lambda image.
6. Deploys Lambda, API Gateway, private S3, and CloudFront.
7. Uploads versioned assets and no-cache HTML.
8. Invalidates CloudFront and waits for completion.
9. Calls public `/health`, requires CockroachDB, Bedrock, and mandatory Managed MCP verification, and prints the judge URL only after success.

## Acceptance

1. Open the CloudFront URL in a signed-out browser.
2. Confirm health reports CockroachDB, Bedrock, configured read-only Managed MCP, one node, and policy v5.0.
3. Confirm 26 CockroachDB cases include `evidence_bundle` data.
4. Run `CASE-184-26`; confirm $60 partial refund proposal, `VERIFY`, and episode ID.
5. Run `CASE-202-26`; confirm automatic replacement, a Managed MCP receipt, vector-neighbor overlap, and verified provider reference.
6. Run safety and high-value freight cases; confirm no automatic action.
7. Resume `CASE-771-26`; confirm correction ID, then run `CASE-841-26` and observe replay.
8. Download a receipt and run retry injection.
9. Confirm CloudWatch contains request ID, route, status, and latency.

## Security

- S3 blocks public access; only CloudFront origin access control can read assets.
- Lambda invokes only the approved Bedrock models and reads the two explicitly supplied CockroachDB secrets.
- Managed MCP is cluster-scoped, calls only `select_query`, and cannot receive browser input or credentials.
- API Gateway rate limits and Lambda reserved concurrency bound downstream load.
- CloudFront adds CSP, HSTS, frame denial, content-type, referrer, and permissions-policy headers.
- API routes are never cached.
- Judges need no AWS account.

## Rollback

Redeploy the last validated application artifacts for a code regression. Never destructively reverse an applied database migration. Add a forward fix and preserve compatibility until the previous runtime is retired. Use the [runbook](./RUNBOOK.md) for diagnosis.
