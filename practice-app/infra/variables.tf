variable "project_id" {
  description = "GCP project to deploy the practice-app into."
  type        = string
}

variable "region" {
  description = "Region for Cloud Run, AR, Firestore."
  type        = string
  default     = "us-central1"
}

variable "service_name" {
  type    = string
  default = "practice-app"
}

variable "ar_repo_name" {
  type    = string
  default = "apps"
}

variable "image_tag" {
  description = "Container image tag in Artifact Registry. Set by CI to the commit SHA."
  type        = string
  default     = "bootstrap"
}

variable "allow_public" {
  description = "Whether to grant roles/run.invoker to allUsers (public access)."
  type        = bool
  default     = true
}

variable "firestore_location" {
  description = "Firestore location (regional like 'us-central1' or multi-region 'nam5')."
  type        = string
  default     = "nam5"
}

variable "domain" {
  description = "Public custom domain for the load-balanced service. Empty string disables the LB."
  type        = string
  default     = ""
}

variable "enable_lb" {
  description = "Provision the global HTTPS LB + Cloud Armor + managed cert in front of Cloud Run. Requires var.domain."
  type        = bool
  default     = false
}

variable "restrict_ingress_to_lb" {
  description = "When true, Cloud Run only accepts traffic from the LB (cuts off the *.run.app URL). Flip on AFTER DNS is pointed at the LB IP and the cert is ACTIVE."
  type        = bool
  default     = false
}

variable "rate_limit_rpm" {
  description = "Per-IP requests-per-minute allowed by Cloud Armor before throttling."
  type        = number
  default     = 60
}

variable "edge_shared_secret" {
  description = "Secret value Cloudflare must inject as X-Edge-Auth on every origin request. Empty disables edge auth (origin accepts anyone). Pass via -var or TF_VAR_edge_shared_secret; do NOT commit."
  type        = string
  default     = ""
  sensitive   = true
}
