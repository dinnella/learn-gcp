variable "project_id" { type = string }
variable "region" {
  type    = string
  default = "us-central1"
}
variable "cluster_name" {
  type    = string
  default = "autopilot-canary"
}
variable "network_self_link" {
  description = "Self-link of an existing VPC (output of lab 01). Leave null to auto-create."
  type        = string
  default     = null
}
variable "subnet_self_link" {
  type    = string
  default = null
}
