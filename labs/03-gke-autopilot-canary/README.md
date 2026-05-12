# Lab 03 — GKE Autopilot + Cloud Deploy canary + Binary Authorization

**Exam coverage:** PCA §1.3, §2.3, §3.1, §5.1; DevOps §1.4, §2.x, §3.2
**Prereqs:** bootstrap/, lab 01 (VPC), lab 02 (Artifact Registry, Binary Authorization basics)
**Cost:** GKE Autopilot ≈ **$0.10/hr cluster fee + pod usage**. Plan ~$3–5/day; **always destroy when done**.

## What you build

GKE Autopilot regional cluster running a 2-revision canary deployment driven by Cloud Deploy:

```
git push image → Cloud Build builds + signs → AR
                     ↓
              Cloud Deploy pipeline:
                stage 1: canary 10% → verify SLO → 100%
              Binary Authorization on cluster: only signed images admit
```

## AWS / Azure analogs

| This lab does… | …in AWS | …in Azure |
|---|---|---|
| GKE Autopilot | EKS Auto Mode (newer) / Fargate-on-EKS | AKS Automatic |
| Cloud Deploy canary | CodeDeploy blue/green / Argo Rollouts | Pipelines + Argo |
| Binary Authorization | (image signing w/ Notation in EKS — newer) | AKS image integrity policy |
| GKE fleets | EKS multi-cluster via EKS-A | Azure Arc fleets |
| Workload Identity (in-cluster) | IRSA | AAD Workload Identity |

## GCP twists worth memorizing

1. **Autopilot vs. Standard:**
   - Autopilot = no node management, billed per pod CPU/RAM, opinionated security defaults (no host network, no privileged), `cluster-autoscaler` hardened.
   - Standard = you pick machine types, manage node pools, can use any K8s feature.
   - **Default exam answer: Autopilot** unless the question requires DaemonSets-on-system-nodes / privileged pods / GPU customization.
2. **Workload Identity (cluster-internal)** binds K8s ServiceAccounts to GCP service accounts via the `roles/iam.workloadIdentityUser` role. Same name as the federation feature — different mechanism.
3. **Cloud Deploy** is K8s-native: targets are GKE clusters; it uses Skaffold + Kustomize/Helm to render manifests per stage.
4. **Canary in Cloud Deploy = a Strategy** in the DeliveryPipeline. Phases auto-progress unless `verify: true` — then you script verification.
5. **Binary Authorization on GKE** is enforced at admission via an admission controller webhook. On Cloud Run it's enforced at deploy time.
6. **Regional cluster** spans 3 zones automatically; **zonal cluster** is one zone (don't use for prod).

## IAM prerequisites

Local runs use your own gcloud identity (Owner is sufficient). For CI runs via `labs-apply.yml`, the deployer SA needs:

```bash
PROJECT=your-project-id
SA="serviceAccount:gh-deployer@${PROJECT}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding "$PROJECT" --member="$SA" --condition=None \
  --role="roles/container.admin"               # create and manage GKE Autopilot clusters

gcloud projects add-iam-policy-binding "$PROJECT" --member="$SA" --condition=None \
  --role="roles/artifactregistry.admin"        # create AR repos for canary images

gcloud projects add-iam-policy-binding "$PROJECT" --member="$SA" --condition=None \
  --role="roles/iam.serviceAccountAdmin"       # create node-pool and workload identity SAs

gcloud projects add-iam-policy-binding "$PROJECT" --member="$SA" --condition=None \
  --role="roles/resourcemanager.projectIamAdmin" # bind Workload Identity and node SA roles

gcloud projects add-iam-policy-binding "$PROJECT" --member="$SA" --condition=None \
  --role="roles/serviceusage.serviceUsageAdmin" # enable GCP APIs via google_project_service
```

## TODO

- [ ] Autopilot regional cluster OpenTofu config
- [ ] Workload Identity-bound app KSA
- [ ] Cloud Deploy `delivery-pipeline.yaml` + `target.yaml`
- [ ] Skaffold + Kustomize overlays for canary/stable
- [ ] BinAuthz cluster policy requiring an attestation
- [ ] GH Actions: build → sign → create release in Cloud Deploy
