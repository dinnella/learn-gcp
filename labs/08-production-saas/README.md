# Lab 08 — Production SaaS on Cloud Run

**Exam coverage:** PCA §1.3, §2.3, §2.5, §3.4, §5.1; DevOps §2.1–2.4, §3.2
**Prereqs:** bootstrap/, labs 01–02 (concepts only; this lab is self-contained infra)
**Cost:** ~$0/day (Cloud Run scale-to-zero; Firestore free tier; Secret Manager <1 000 accesses/mo; Cloudflare Free)

---

## What you build

A real, internet-facing FastAPI app deployed to Cloud Run, fronted by Cloudflare,
backed by Firestore — no long-running VMs, no JSON service-account keys, no ingress
that bypasses your edge security layer.

```
Browser
  │
  ▼
Cloudflare Free (DNS proxy)
  ├── TLS Full-strict (Cloud Run's managed cert is the origin cert)
  ├── WAF Managed Ruleset    → blocks common exploits (OWASP core)
  ├── Bot Fight Mode         → blocks automated scanners (manual toggle only)
  ├── Rate limit: 300 req/min/IP → 60 s block
  └── Transform Rule: inject  X-Edge-Auth: <shared-secret>
          │
          ▼
  Cloud Run service          (INGRESS_TRAFFIC_ALL — but see edge-auth below)
  ├── FastAPI + Pydantic 2
  ├── EDGE_SHARED_SECRET mounted from Secret Manager
  ├── Middleware: reject requests where X-Edge-Auth != secret (exempt: /api/health)
  ├── Firestore Native (read/write via runtime SA binding)
  └── Runtime SA (least-privilege: datastore.user + logging + metrics)
```

**Security guarantee:** `*.run.app` direct hits return `403 Forbidden`. Only Cloudflare-proxied
requests carry the shared secret. The secret lives in Secret Manager — never in source
or CI logs.

**The reference implementation is `practice-app/`** in this repo. This README explains
the *why* behind every design decision. Use `practice-app/infra/` and
`practice-app/infra-cloudflare/` as the IaC you study, deploy, and evolve.

---

## Architecture decisions worth memorizing

### 1. Cloud Run ingress = `INGRESS_TRAFFIC_ALL`, not internal-only

You might expect to lock ingress to `INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER` and
route Cloudflare through a GCP External Load Balancer. That architecture costs
~$20/mo minimum (the forwarding rule alone). On Cloudflare Free, the ELB approach
also cannot work for custom-cert HTTPS without a Cloudflare Origin CA cert.

**The pattern here instead:** Allow all ingress at the GCP layer. Enforce the edge at
the application layer via the `X-Edge-Auth` middleware. This costs $0 on Cloud Run
free tier and is auditable in application logs.

**Trade-off:** If the shared secret leaks, a direct attacker can bypass Cloudflare.
The rotation runbook (Step H in the operator guide) is therefore mandatory, not
optional.

### 2. Secret Manager + secret_key_ref instead of env var injection at deploy time

Cloud Run's `secret_key_ref` pulls the secret value from Secret Manager *at container
start*, not at tofu-apply time. Benefits:

- Rotating the secret requires updating the Secret Manager version and restarting the
  service — no re-deploy, no tofu-apply.
- The secret value never appears in the Cloud Run revision's environment variable
  metadata (unlike a hardcoded `value =` env var, which is visible in the console).
- Audit trail: Secret Manager logs every access with which SA read it and when.

### 3. Workload Identity Federation — no SA JSON keys anywhere

The CI deployer identity (`gh-deployer@...`) is granted IAM directly via WIF. GitHub's
OIDC token exchange removes the need for a downloaded JSON key. This eliminates the
most common credential-leak vector in GCP CI/CD pipelines.

```
GitHub Actions runner
  → exchanges OIDC JWT (from GitHub) with
  → iamcredentials.googleapis.com (STS endpoint)
  → receives short-lived access token for gh-deployer SA
  → uses token for gcloud / tofu / docker push
```

**Exam note:** `iamcredentials.googleapis.com` *and* `cloudresourcemanager.googleapis.com`
must be enabled for WIF to work. The Google Terraform provider also calls the CRM API
on every plan/apply to resolve project numbers.

### 4. Firestore Native mode, not Datastore mode

Cloud Firestore can operate in two modes:

| | Firestore Native | Datastore mode |
|---|---|---|
| API surface | Firestore SDK + REST | Datastore SDK |
| Real-time listeners | Yes | No |
| Transactions | Optimistic (MVCC) | Optimistic |
| Max document size | 1 MB | 1 MB |
| Subcollections | Yes | No |
| GCP billing | Same | Same |

**Native mode is the modern default.** The IAM role for both is `roles/datastore.user`
(Firestore reuses the datastore.* permission namespace regardless of mode).

`delete_protection_state = "DELETE_PROTECTION_ENABLED"` prevents `tofu destroy` from
dropping the database. Remove this before running `destroy` in a lab teardown.

### 5. Cloudflare Free is a real security layer

Many tutorials treat Cloudflare as just a CDN. At the Free plan it provides:

| Feature | How it's configured here |
|---|---|
| TLS Full (strict) | `ssl = "strict"` in zone settings override |
| TLS 1.2 minimum | `min_tls_version = "1.2"` |
| Always HTTPS | `always_use_https = "on"` |
| WAF Managed Ruleset | `cloudflare_ruleset` on `http_request_firewall_managed` phase |
| Rate limiting | `cloudflare_ruleset` on `http_ratelimit` phase (1 rule on Free) |
| Bot Fight Mode | Manual toggle in dashboard (`Security → Bots`); no API on Free |
| Header injection | Transform Rule on `http_request_late_transform` phase |

**Exam note (cloud-agnostic):** Cloudflare is not a GCP product, but the PCA exam
covers "third-party security tools and their integration with GCP." The pattern of
"edge proxy injects auth header; origin enforces it" is identical to using Google
Cloud Armor + a backend service custom header.

---

## AWS / Azure analogs

| This lab does… | …in AWS | …in Azure |
|---|---|---|
| Cloud Run | App Runner / ECS Fargate | Container Apps |
| Firestore Native | DynamoDB | Cosmos DB (NoSQL API) |
| Secret Manager secret_key_ref | ECS secrets from Secrets Manager | Key Vault secret ref in Container Apps |
| Workload Identity Federation | GitHub OIDC → IAM Role (no keys) | GitHub OIDC → federated credential |
| Cloudflare WAF + Transform Rule | CloudFront + WAF + Lambda@Edge | Front Door + WAF + Rules Engine |
| Cloud Run scale-to-zero | Fargate (min-tasks=0) | Container Apps (min-replicas=0) |
| Artifact Registry | ECR | ACR |

---

## GCP twists worth memorizing for the exam

1. **`INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER`** is not "free LB." It requires a GCP
   External Application Load Balancer, which has a base cost even with zero traffic.

2. **Cloud Run always gets a `*.run.app` URL** with a Google-managed TLS cert. You do
   not need to provision a cert for the origin. Cloudflare can use "Full (strict)"
   mode against this cert because it's a valid cert from Google Trust Services.

3. **`secret_key_ref version = "latest"`** resolves at container start. If you rotate
   the secret (add a new version), you must restart the service for the new value to
   take effect. This is a restart, not a re-deploy — no image rebuild required.

4. **Firestore's free tier** (1 GiB storage, 50K reads/day, 20K writes/day) covers
   this app indefinitely for a personal project.

5. **`containerscanning.googleapis.com`** is enabled in `required_apis` so Artifact
   Registry automatically scans pushed images for CVEs at no cost.

6. **`roles/datastore.owner`** is required by the *deployer* SA (to create the
   Firestore database via tofu). The *runtime* SA only needs `roles/datastore.user`.
   Use `roles/datastore.owner` only in CI; never grant it to a long-lived identity.

7. **Concurrency group `cancel-in-progress: false`** on the deploy workflow means a
   second push while a deploy is running queues rather than cancels the first run.
   This prevents a race where a second deploy starts before the first has seeded data.

---

## How the CI/CD pipeline works

```
push to main (practice-app/** or .github/workflows/practice-app.yml)
  │
  ├─ Job: build-deploy (runs on ubuntu-latest, environment: production)
  │     1. Checkout (persist-credentials: false)
  │     2. Authenticate to GCP via WIF  (google-github-actions/auth)
  │     3. docker build  →  docker push  →  Artifact Registry
  │     4. tofu init + tofu apply  (bootstrap: creates AR repo, Firestore, Secret, Cloud Run)
  │        └── on first run: image_tag=bootstrap → uses google hello container placeholder
  │        └── on subsequent runs: image_tag=<commit SHA>
  │     5. Seed: python seed/seed.py  (idempotent — skips if questions already exist)
  │
  └─ Job: cloudflare-apply  (only if ENABLE_CLOUDFLARE=true repo variable is set)
        1. Checkout
        2. tofu init + tofu apply  (infra-cloudflare/)
        └── creates DNS record, WAF, rate limit, Transform Rule in Cloudflare
```

**Bootstrap pattern:** The first `tofu apply` runs before any image has been pushed.
`var.image_tag = "bootstrap"` resolves to Google's public `us-docker.pkg.dev/cloudrun/container/hello`.
Once the AR repo exists, CI pushes the real image and a second apply sets the correct tag.

---

## Operator runbook (first deploy)

### Prerequisites

```bash
# Must be done once before the workflow can run
gcloud auth login
gcloud config set project next3k-levelup
gh auth login

# Verify deployer SA has all required roles
gcloud projects get-iam-policy $PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:gh-deployer" \
  --format="table(bindings.role)"

# Required roles for gh-deployer SA:
#   roles/run.admin                          — create and update Cloud Run services
#   roles/artifactregistry.admin              — create AR repos (writer only pushes to existing repos)
#   roles/iam.serviceAccountAdmin             — create the Cloud Run runtime SA
#   roles/iam.serviceAccountUser              — deploy Cloud Run services as the runtime SA
#   roles/resourcemanager.projectIamAdmin     — bind roles via google_project_iam_member
#   roles/datastore.owner                     — create the Firestore (Native) database
#   roles/storage.objectAdmin                 — read/write tofu state in GCS
#   roles/secretmanager.admin                 — create and version the edge-auth secret
#   roles/serviceusage.serviceUsageAdmin      — enable GCP APIs via google_project_service
```

### Step A — Configure GitHub repo and secrets

[`scripts/setup-github.sh`](../../scripts/setup-github.sh) is a one-time script that configures the GitHub repo for CI deployment. Run it once after `bootstrap/` succeeds:

```bash
./scripts/setup-github.sh
# Sets: PROJECT_ID, REGION, AR_REPO, IMAGE, SERVICE_NAME, WIF_PROVIDER,
#       WIF_SERVICE_ACCOUNT, EDGE_SHARED_SECRET (generated, never echoed)
# Applies branch protection + Actions allow-list
```

### Step B — First deploy (GCP only)

```bash
gh workflow run "practice-app — build, deploy, seed"
gh run watch  # follow live
```

Expected: `build-deploy` passes; `cloudflare-apply` is skipped (`ENABLE_CLOUDFLARE` not set yet).

Smoke test the raw Cloud Run URL:
```bash
URL=$(gcloud run services describe practice-app --region=us-central1 --format='value(status.url)')
curl -sI "$URL/api/health"                   # 200 OK
curl -sI "$URL/api/questions"                # 403 Forbidden (no X-Edge-Auth)
curl -sI -H "X-Edge-Auth: wrong" "$URL/..."  # 403 Forbidden
```

### Step C — Cloudflare setup (once)

1. In Cloudflare dashboard: **Security → Bots → Bot Fight Mode = ON** (can't be set via API on Free plan).
2. Mint a Cloudflare API token with scopes: Zone:DNS:Edit, Zone Settings:Edit, Zone WAF:Edit, Transform Rules:Edit — scoped to `next3k.com`.
3. Get your Zone ID from the Cloudflare dashboard (`Overview → Zone ID`).
4. Set secrets:

```bash
gh secret   set CLOUDFLARE_API_TOKEN --repo dinnella/learn-gcp --body "<token>"
gh secret   set CLOUDFLARE_ZONE_ID   --repo dinnella/learn-gcp --body "<zone id>"
gh variable set ENABLE_CLOUDFLARE    --repo dinnella/learn-gcp --body "true"
```

5. Trigger the workflow again; both jobs run this time.

### Step D — Smoke test through Cloudflare

```bash
curl -sI https://levelup.next3k.com/api/health   # 200, cf-ray header present
curl -sI https://levelup.next3k.com/api/questions # 200 (Cloudflare injects X-Edge-Auth)
curl -sI https://<your-service>.run.app/api/health  # 200 (health is exempt)
curl -sI https://<your-service>.run.app/api/questions # 403 (no edge auth on direct hit)
```

### Step E — Secret rotation drill

```bash
NEW_SECRET=$(openssl rand -hex 32)

# 1. Add a new Secret Manager version
echo -n "$NEW_SECRET" | gcloud secrets versions add practice-app-edge-auth --data-file=-

# 2. Update the GitHub secret Cloudflare uses (so it injects the new value)
printf '%s' "$NEW_SECRET" | gh secret set EDGE_SHARED_SECRET --repo dinnella/learn-gcp

# 3. Restart Cloud Run service to pull the new secret version
gcloud run services update practice-app --region=us-central1 --no-traffic

# 4. Re-run deploy to update Cloudflare Transform Rule
gh workflow run "practice-app — build, deploy, seed"

# 5. Verify old value no longer works
curl -sI -H "X-Edge-Auth: <old-value>" https://<your-service>.run.app/api/questions
# 403 — correct

unset NEW_SECRET
```

---

## Teardown

```bash
# Remove delete protection before destroying Firestore
# In practice-app/infra/main.tf, set:
#   delete_protection_state = "DELETE_PROTECTION_DISABLED"
# Then apply, then destroy.

cd practice-app/infra
tofu apply -var "project_id=..." -var "delete_protection=false"
tofu destroy -var "project_id=..."

cd ../infra-cloudflare
tofu destroy -var "zone_id=..." ...
```

---

## TODO (extend as exercises)

- [ ] Add Cloud Armor in front of Cloud Run instead of Cloudflare (compare cost and features)
- [ ] Replace the shared-secret pattern with mTLS (client cert from Cloudflare Origin CA)
- [ ] Add a Cloud Run job for scheduled data refresh (Firestore seeder as a Job, not a one-shot script)
- [ ] Add VPC Connector + private Firestore endpoint (eliminate public Firestore API surface)
- [ ] Enable Artifact Analysis vulnerability alerts and fail CI on CRITICAL CVEs
- [ ] Add Cloud Monitoring uptime check + alerting policy for `/api/health`
