# Lab 02 — Cloud Run + Cloud Build CI/CD

**Exam coverage:** PCA §1.3, §2.3, §5.1; DevOps §2.1, §2.2, §2.4
**Prereqs:** bootstrap/, lab 01 (uses the VPC for VPC connector — optional)
**Cost:** ~$0 (Cloud Run scales to zero; Artifact Registry storage ~$0.10/GB/mo)

## What you build

A simple containerized HTTP service deployed via:

```
GitHub push → GitHub Actions (build + push to Artifact Registry)
                       ↓
              Cloud Deploy pipeline → Cloud Run (canary 10% → 100%)
                       ↑
              Binary Authorization policy (only signed images allowed)
```

You'll learn three of the most-tested DevOps concepts:
1. **Artifact Registry** repo creation + push from CI
2. **Cloud Deploy** as the release-orchestration layer (separate from Cloud Build)
3. **Binary Authorization** with attestor-based admission control

## AWS / Azure analogs

| This lab does… | …in AWS | …in Azure |
|---|---|---|
| Cloud Run service | App Runner / ECS Fargate behind ALB | Container Apps |
| Artifact Registry | ECR | ACR |
| Cloud Build | CodeBuild | Pipelines (build) |
| Cloud Deploy | CodeDeploy / CodePipeline | Pipelines (release) |
| Binary Authorization | (Notation + ECR signing — newer) | ACR signing + AKS image policy |
| WIF for GitHub | GitHub OIDC → IAM Role | GitHub OIDC → federated credential |

## GCP twists worth memorizing

1. **Cloud Run = stateless containers, request-billed, scale-to-zero.** The default answer for "deploy a container" unless K8s API is required.
2. **Cloud Build vs. Cloud Deploy split.** Build = produce artifact. Deploy = roll it through environments. Don't conflate.
3. **Cloud Deploy uses Skaffold** under the hood — even for Cloud Run targets.
4. **Binary Authorization** runs at admission time on GKE/Cloud Run. Default policy = `allow_all`. Production = require attestations from a specific attestor (which itself verifies a signature in Container Analysis).
5. **Artifact Registry replaced Container Registry.** GCR redirects but is read-only as of 2025 — always create AR repos for new work.
6. **Direct Workload Identity Federation** (used in this repo) avoids the SA-impersonation hop. The federated principal `principalSet://...attribute.repository/owner/name` gets IAM directly.

## IAM prerequisites

Local runs use your own gcloud identity (Owner is sufficient). For CI runs via `labs-apply.yml`, the deployer SA needs:

```bash
PROJECT=your-project-id
SA="serviceAccount:gh-deployer@${PROJECT}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding "$PROJECT" --member="$SA" --condition=None \
  --role="roles/run.admin"                     # create and manage Cloud Run services

gcloud projects add-iam-policy-binding "$PROJECT" --member="$SA" --condition=None \
  --role="roles/artifactregistry.admin"        # create AR repos and push images (writer can only push to existing repos)

gcloud projects add-iam-policy-binding "$PROJECT" --member="$SA" --condition=None \
  --role="roles/iam.serviceAccountAdmin"       # create runtime service accounts for Cloud Run

gcloud projects add-iam-policy-binding "$PROJECT" --member="$SA" --condition=None \
  --role="roles/iam.serviceAccountUser"        # deploy Cloud Run services as the runtime SA

gcloud projects add-iam-policy-binding "$PROJECT" --member="$SA" --condition=None \
  --role="roles/resourcemanager.projectIamAdmin" # bind IAM roles via google_project_iam_member

gcloud projects add-iam-policy-binding "$PROJECT" --member="$SA" --condition=None \
  --role="roles/serviceusage.serviceUsageAdmin" # enable GCP APIs via google_project_service
```

## Run

This lab will be built incrementally:

- [ ] Stub: Artifact Registry repo + Cloud Run "hello" service deploy via OpenTofu (current state)
- [ ] Add: Cloud Build trigger + cloudbuild.yaml
- [ ] Add: Cloud Deploy delivery pipeline with canary
- [ ] Add: Binary Authorization attestor + signing in CI
- [ ] Bonus: replicate just the Cloud Run service via [Infrastructure Manager](https://cloud.google.com/infrastructure-manager/docs) for IaC comparison

```bash
tofu init -backend-config="bucket=$GCP_TFSTATE_BUCKET" -backend-config="prefix=labs/02-cloud-run-cicd"
tofu apply -var "project_id=$GCP_PROJECT_ID"
```

After apply:

```bash
URL=$(tofu output -raw service_url)
curl -s -H "Authorization: Bearer $(gcloud auth print-identity-token)" "$URL"
```

## TODO

- [ ] cloudbuild.yaml + GH Actions trigger
- [ ] Cloud Deploy pipeline manifest (canary)
- [ ] Binary Authorization attestor + Voucher signing step in CI
- [ ] Compare TF apply vs. Infrastructure Manager deployment of identical config
