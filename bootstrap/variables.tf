variable "project_id" {
  description = "GCP project that hosts TF state + WIF pool. Must already exist with billing enabled."
  type        = string
}

variable "region" {
  description = "Default region for regional resources (e.g. us-central1, europe-west1)."
  type        = string
  default     = "us-central1"
}

variable "tfstate_bucket_name" {
  description = "Globally-unique name for the GCS bucket holding Terraform state."
  type        = string
}

variable "github_repo" {
  description = "GitHub repository in 'owner/name' form. Used to scope the WIF trust."
  type        = string
  validation {
    condition     = can(regex("^[^/]+/[^/]+$", var.github_repo))
    error_message = "github_repo must be in 'owner/name' form."
  }
}

variable "wif_pool_id" {
  description = "Workload Identity Pool ID."
  type        = string
  default     = "github-pool"
}

variable "wif_provider_id" {
  description = "Workload Identity Provider ID inside the pool."
  type        = string
  default     = "github-provider"
}

variable "deployer_sa_id" {
  description = "ID (local part of email) for the Terraform deployer service account."
  type        = string
  default     = "tf-deployer"
}

variable "enabled_apis" {
  description = "APIs to enable on the bootstrap project."
  type        = list(string)
  default = [
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
    "storage.googleapis.com",
  ]
}
