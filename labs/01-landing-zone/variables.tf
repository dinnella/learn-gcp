variable "project_id" {
  description = "Project that hosts the landing-zone resources."
  type        = string
}

variable "region" {
  description = "Primary region."
  type        = string
  default     = "us-central1"
}

variable "secondary_region" {
  description = "Secondary region for multi-region patterns."
  type        = string
  default     = "us-east1"
}

variable "network_name" {
  description = "Name of the custom-mode VPC."
  type        = string
  default     = "lz-vpc"
}
