# bootstrap

One-time setup, run **manually from your laptop** with user credentials. Creates everything CI needs to take over.

## What it creates

| Resource | Purpose | AWS analog |
|---|---|---|
| GCS bucket `tfstate-<project>` | Remote Terraform state for all labs | S3 backend |
| Workload Identity Pool `github-pool` | Trust anchor for GitHub OIDC | IAM OIDC provider |
| Workload Identity Provider `github-provider` | Maps GitHub claims → GCP principals | IAM OIDC provider config |
| Service Account `tf-deployer@…` | Identity that Terraform applies as | IAM Role assumed by GH Actions |
| IAM bindings | Grants `tf-deployer` `roles/owner` on the project (lab scope only — narrow for prod) | IAM trust policy + permissions |
| API enablement | Enables required GCP APIs | (no analog — APIs are on by default in AWS) |

## Prerequisites

- A GCP project with billing enabled. (Use `gcloud projects create learn-gcp-$(openssl rand -hex 3)` then link a billing account in the console.)
- `gcloud` CLI authenticated (`gcloud auth login` + `gcloud auth application-default login`).
- [OpenTofu](https://opentofu.org/docs/intro/install/) `>= 1.8`.
- Your GitHub repo path (e.g. `your-user/learn-gcp`).

## Run

```bash
cd bootstrap
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars
tofu init
tofu plan
tofu apply
```

Outputs include the values you need for GitHub repo secrets:

```bash
tofu output -raw workload_identity_provider
tofu output -raw deployer_service_account_email
tofu output -raw tfstate_bucket
```

Add the first two as GitHub Actions **variables** (not secrets — they're not sensitive), names:
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_DEPLOYER_SA`
- `GCP_PROJECT_ID`
- `GCP_TFSTATE_BUCKET`

## Cleanup

```bash
tofu destroy
```

Then delete the project: `gcloud projects delete <project-id>`.

## Why not use the [terraform-google-bootstrap](https://github.com/terraform-google-modules/terraform-google-bootstrap) module?

That module assumes an **org-level** install (org admin role, seed project provisioning, group bindings). For single-project lab use it's overkill and requires permissions a $300-trial account doesn't have. Once you complete lab 01 (landing zone) you can swap to the official module.
