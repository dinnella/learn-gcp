output "tfstate_bucket" {
  description = "Name of the GCS bucket holding Terraform state for all labs."
  value       = google_storage_bucket.tfstate.name
}

output "workload_identity_provider" {
  description = "Full WIF provider resource name. Use as GH Actions variable GCP_WORKLOAD_IDENTITY_PROVIDER."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "deployer_service_account_email" {
  description = "Service account that GH Actions impersonates. Use as GH Actions variable GCP_DEPLOYER_SA."
  value       = google_service_account.deployer.email
}

output "project_id" {
  description = "Project hosting bootstrap resources. Use as GH Actions variable GCP_PROJECT_ID."
  value       = var.project_id
}

output "github_actions_setup_hint" {
  description = "Copy-paste these into your GitHub repo (Settings → Secrets and variables → Actions → Variables)."
  value = {
    GCP_PROJECT_ID                 = var.project_id
    GCP_WORKLOAD_IDENTITY_PROVIDER = google_iam_workload_identity_pool_provider.github.name
    GCP_DEPLOYER_SA                = google_service_account.deployer.email
    GCP_TFSTATE_BUCKET             = google_storage_bucket.tfstate.name
  }
}
