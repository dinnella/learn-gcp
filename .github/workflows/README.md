# GitHub Actions workflows

These workflows authenticate to GCP via [Workload Identity Federation](https://github.com/google-github-actions/auth) — **no JSON keys, no long-lived secrets**.

## Required GitHub repo configuration

After running `bootstrap/`, set these in **Settings → Secrets and variables → Actions → Variables** (not Secrets — they're not sensitive):

| Variable | Source | Example |
|---|---|---|
| `GCP_PROJECT_ID` | `terraform output project_id` | `learn-gcp-abc123` |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `terraform output workload_identity_provider` | `projects/123456789/locations/global/workloadIdentityPools/github-pool/providers/github-provider` |
| `GCP_DEPLOYER_SA` | `terraform output deployer_service_account_email` | `tf-deployer@learn-gcp-abc123.iam.gserviceaccount.com` |
| `GCP_TFSTATE_BUCKET` | `terraform output tfstate_bucket` | `tfstate-learn-gcp-abc123` |

## Workflows

| File | Trigger | Action |
|---|---|---|
| [labs-plan.yml](labs-plan.yml) | Pull request changing `labs/**` | `tofu plan` for each changed lab; comments diff on PR |
| [labs-apply.yml](labs-apply.yml) | Push to `main` changing `labs/**` | `tofu apply` for each changed lab |
| [practice-app.yml](practice-app.yml) | Push to `main` changing `practice-app/**` | Build image → push to Artifact Registry → `tofu apply` → seed Firestore |

## How auth works (mental model for AWS people)

1. GitHub mints an OIDC token claiming "I am workflow X in repo `owner/name` on branch `main`".
2. `google-github-actions/auth@v3` posts that token to GCP's STS endpoint.
3. STS exchanges it for a federated token because:
   - The OIDC issuer (`token.actions.githubusercontent.com`) matches our **WIF Provider**, AND
   - The `assertion.repository` claim equals our repo (enforced by the provider's `attribute_condition`).
4. The federated token impersonates the **deployer SA** (because that SA has `roles/iam.workloadIdentityUser` granted to `principalSet://...attribute.repository/owner/name`).
5. Subsequent `gcloud` / OpenTofu calls use that SA's permissions.

This is the same pattern as AWS GitHub OIDC → IAM Role assumption, just with two layers (pool + provider) instead of one.
