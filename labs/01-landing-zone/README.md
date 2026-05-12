# Lab 01 — Landing zone

**Exam coverage:** PCA §1.1, §1.3, §3.1; DevOps §1.1
**Prereqs:** bootstrap/ complete
**Cost:** ~$0/day if you skip the optional Cloud NAT + Cloud Logging Data Access toggles. ~$1.50/day with them.

## What you build

A single-project landing zone (lab-scoped):

- Custom-mode VPC with regional subnets in 2 regions
- Hierarchical firewall policy with default-deny + allow-IAP-SSH
- Org policy constraints applied at the project level (`requireOsLogin`, `restrictPublicIP`, `disableSerialPortAccess`)
- IAM groups + role bindings using least-privilege patterns
- Centralized log sink to a GCS bucket (audit log archive)

> **Why "single project"?** True landing zones live at the org/folder level using [terraform-google-modules/terraform-example-foundation](https://github.com/terraform-google-modules/terraform-example-foundation). That requires org admin. We learn the same primitives at the project level here. Walk through the foundation repo as reading.

## AWS / Azure analogs

| This lab does… | …in AWS | …in Azure |
|---|---|---|
| Custom-mode VPC | VPC + subnets in regions | VNet + subnets |
| Hierarchical firewall policy | SCP + SG-as-default-deny pattern | Azure Firewall Policy + NSG |
| Org policy `restrictPublicIP` | SCP denying `ec2:RunInstances` w/ public IP | Azure Policy `denyPublicIP` |
| Centralized log sink | Org-level CloudTrail to S3 | Diagnostic settings → Log Analytics |
| Audit log archive bucket | S3 bucket w/ object lock + lifecycle | Storage account w/ immutability policy |

## GCP twists worth memorizing

1. **VPC is global.** One network, regional subnets. No "VPC peering across regions" concept needed.
2. **Firewall rules attach to the VPC by tag/SA**, not to NICs/instances. `network_tag` and `target_service_account` are the two targeting mechanisms.
3. **Hierarchical firewall policies** override VPC firewall rules and apply at org/folder. Equivalent of an SCP for network traffic.
4. **Org policies** are constraint-based (built-in list), not free-form like Azure Policy. Custom constraints exist but are limited to specific services.
5. **Default network is created automatically** in new projects — disable via the `compute.skipDefaultNetworkCreation` org policy or `auto_create_subnetworks = false`.

## IAM prerequisites

Local runs use your own gcloud identity (Owner is sufficient). For CI runs via `labs-apply.yml`, the deployer SA needs:

```bash
PROJECT=your-project-id
SA="serviceAccount:gh-deployer@${PROJECT}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding "$PROJECT" --member="$SA" --condition=None \
  --role="roles/compute.networkAdmin"          # create VPC, subnets, hierarchical firewall policies

gcloud projects add-iam-policy-binding "$PROJECT" --member="$SA" --condition=None \
  --role="roles/logging.admin"                 # create log sinks and log buckets

gcloud projects add-iam-policy-binding "$PROJECT" --member="$SA" --condition=None \
  --role="roles/orgpolicy.policyAdmin"         # apply org policy constraints at project level

gcloud projects add-iam-policy-binding "$PROJECT" --member="$SA" --condition=None \
  --role="roles/storage.admin"                 # create GCS bucket for log archive

gcloud projects add-iam-policy-binding "$PROJECT" --member="$SA" --condition=None \
  --role="roles/resourcemanager.projectIamAdmin" # bind IAM roles (google_storage_bucket_iam_member)

gcloud projects add-iam-policy-binding "$PROJECT" --member="$SA" --condition=None \
  --role="roles/serviceusage.serviceUsageAdmin" # enable GCP APIs via google_project_service
```

## Run

Local:
```bash
tofu init -backend-config="bucket=$GCP_TFSTATE_BUCKET" -backend-config="prefix=labs/01-landing-zone"
tofu plan -var "project_id=$GCP_PROJECT_ID"
tofu apply -var "project_id=$GCP_PROJECT_ID"
```

Or open a PR; the [plan workflow](../../.github/workflows/terraform-plan.yml) will comment the diff.

## Verify

```bash
gcloud compute networks list --project="$GCP_PROJECT_ID"
gcloud compute firewall-rules list --project="$GCP_PROJECT_ID"
gcloud resource-manager org-policies list --project="$GCP_PROJECT_ID"
gcloud logging sinks list --project="$GCP_PROJECT_ID"
```

## TODO (build out together as we cover the topic)

- [ ] Shared VPC host/service project pattern (requires 2nd project)
- [ ] Cloud NAT for egress from private subnets
- [ ] Add `terraform-google-modules/terraform-google-network` example for comparison
- [ ] Add VPC Service Controls perimeter (requires Premium SCC; skip in trial)
