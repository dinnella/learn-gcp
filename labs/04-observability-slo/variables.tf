variable "project_id" { type = string }
variable "region" {
  type    = string
  default = "us-central1"
}
variable "cloud_run_service_name" {
  description = "Name of the Cloud Run service to monitor (output of lab 02)."
  type        = string
  default     = "hello-cicd"
}
