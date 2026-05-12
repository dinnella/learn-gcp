# learn-gcp

Hands-on study repo for the [Google Cloud Professional Cloud Architect](professional_cloud_architect_exam_guide_english.pdf) and [Professional Cloud DevOps Engineer](professional_cloud_devops_engineer_exam_guide_english.pdf) certifications, optimized for an engineer with deep AWS + Azure background.

## Layout

| Path | Purpose |
|---|---|
| [docs/study-plan.md](docs/study-plan.md) | 8-week dual-cert plan, weighted by exam-guide percentages |
| [docs/aws-azure-gcp-cheatsheet.md](docs/aws-azure-gcp-cheatsheet.md) | Side-by-side service mapping — your highest-leverage doc |
| [docs/diagnostic-exam.md](docs/diagnostic-exam.md) | Pre-study practice exam plan + scoring rubric |
| [docs/notes/](docs/notes/) | Condensed notes per exam-guide section |
| [bootstrap/](bootstrap/) | One-time Terraform: TF state bucket + GitHub WIF |
| [labs/](labs/) | 7 hands-on labs, each self-contained |
| [.github/workflows/](.github/workflows/) | Reusable plan/apply workflows using WIF |

## Quick start

1. Activate [GCP $300 free trial](https://cloud.google.com/free) and create one project (e.g. `learn-gcp-bootstrap-<random>`).
2. `gcloud auth login && gcloud config set project <id>` and enable billing.
3. Read [docs/diagnostic-exam.md](docs/diagnostic-exam.md) and take the cold practice exam **before** studying — this drives the plan.
4. Run [bootstrap/](bootstrap/) (manual `tofu apply` from your laptop — the only step not run via CI).
5. Wire repo secrets per [.github/workflows/README.md](.github/workflows/README.md).
6. Work labs in priority order driven by your diagnostic results.

## Key conventions

- **IaC**: [OpenTofu](https://opentofu.org) (Terraform-compatible fork) using plain HCL with [google-maintained modules](https://github.com/terraform-google-modules) where they add value; `google` provider pinned to `~> 7.0`. The `terraform { ... }` config block is supported by OpenTofu for compatibility — keep using it.
- **Auth**: GitHub Actions → GCP via [Workload Identity Federation](https://github.com/google-github-actions/auth) (no JSON keys).
- **State**: GCS bucket per environment, created by `bootstrap/`.
- **Cost**: every lab README marks expected $/hr and how to `tofu destroy` cleanly.
- **One Infra Manager lab** ([labs/02-cloud-run-cicd/infra-manager/](labs/02-cloud-run-cicd/)) for exam-relevant exposure to GCP-native IaC; everything else is plain OpenTofu.

> **Note on the exam:** Both certs explicitly call out **Terraform** (PCA 5.2, DevOps 1.2). OpenTofu is functionally identical for everything in scope here — same HCL, same provider, same state format, same workflow. When the exam asks about "Terraform", treat the answer as identical.
