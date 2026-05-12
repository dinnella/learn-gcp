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
