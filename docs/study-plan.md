# Dual-cert study plan (PCA + DevOps Engineer)

Default plan: **8 weeks @ ~10 hrs/week**. Adjust based on diagnostic results.

Strategy: PCA and DevOps overlap heavily (IAM, networking, observability, IaC, CI/CD). Take **PCA first** — it's broader; DevOps is then a focused delta of ~3 weeks.

## Exam-guide weights

### PCA (Professional Cloud Architect)
| § | Domain | Weight |
|---|---|---|
| 1 | Designing & planning | 25% |
| 2 | Managing/provisioning infra | 17.5% |
| 3 | Security & compliance | 17.5% |
| 4 | Process analysis | 15% |
| 5 | Managing implementation | 12.5% |
| 6 | Ops excellence | 12.5% |

### DevOps Engineer
| § | Domain | Weight |
|---|---|---|
| 1 | Bootstrapping org | 20% |
| 2 | CI/CD | 25% |
| 3 | SRE practices | 18% |
| 4 | Observability | 25% |
| 5 | Performance & cost | 12% |

## Week-by-week (default; reorder per diagnostic)

| Wk | Focus | Exam guide | Lab | Cheat-sheet rows |
|---|---|---|---|---|
| 0 | Diagnostic + bootstrap | — | [bootstrap/](../bootstrap/) | All |
| 1 | Resource hierarchy, IAM, org policies, billing | PCA 3.1, DevOps 1.1 | [01-landing-zone](../labs/01-landing-zone/) | IAM, Org |
| 2 | Networking: VPC, Shared VPC, PSC, LBs, hybrid | PCA 1.3/2.1, DevOps 1.1 | [01-landing-zone](../labs/01-landing-zone/) + [06-hybrid-networking](../labs/06-hybrid-networking/) | Networking |
| 3 | Compute mapping: GCE, GKE, Cloud Run, Functions | PCA 1.3/2.3, DevOps 3.2 | [02-cloud-run-cicd](../labs/02-cloud-run-cicd/) | Compute |
| 4 | CI/CD: Cloud Build, Cloud Deploy, Artifact Registry, Binary Auth | PCA 5.1, DevOps 2.x | [02](../labs/02-cloud-run-cicd/) + [03-gke-autopilot-canary](../labs/03-gke-autopilot-canary/) | CI/CD |
| 5 | Storage & data: GCS, Cloud SQL, Spanner, BigQuery, Pub/Sub, Dataflow | PCA 1.3/2.2 | [05-data-pipeline](../labs/05-data-pipeline/) | Data |
| 6 | Observability + SRE: Cloud Ops, SLOs, error budgets, OpenTelemetry | PCA 6.x, DevOps 3.x/4.x | [04-observability-slo](../labs/04-observability-slo/) | Observability |
| 7 | Security deep-dive: KMS, Secret Manager, VPC-SC, IAP, WIF, Binary Auth, SLSA | PCA 3.x, DevOps 2.4 | apply across labs | Security |
| 8 | AI/ML + Migration + cost optimization + mock exams | PCA 1.4/2.4-2.5/5, DevOps 5.x | [07-vertex-ai-rag](../labs/07-vertex-ai-rag/) | AI/ML, FinOps |

**Per-section condensed notes** live in [notes/](notes/) and are filled in as we cover each section together.

## Daily rhythm (~1.5 hr)

1. 20 min: read official Google doc for the day's topic
2. 60 min: hands-on (lab work or `gcloud` CLI exploration)
3. 10 min: update notes with "AWS analog / GCP twist / common gotcha"

## Resources

- [Google Cloud Architecture Framework](https://cloud.google.com/architecture/framework) — explicitly required by both exam guides
- [Google Cloud Architecture Center reference patterns](https://cloud.google.com/architecture)
- [SRE Books (free)](https://sre.google/books/) — *Site Reliability Engineering* + *The SRE Workbook*; chapters on SLOs, error budgets, incident response are directly testable
- [Terraform on Google Cloud docs](https://cloud.google.com/docs/terraform)
- [Google Cloud Skills Boost](https://www.cloudskillsboost.google/) — Qwiklabs hands-on
- [OpenTofu docs](https://opentofu.org/docs/) — we use OpenTofu instead of Terraform; HCL & google provider behavior are identical for exam scope
