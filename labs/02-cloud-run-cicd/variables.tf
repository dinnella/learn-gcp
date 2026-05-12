variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "service_name" {
  type    = string
  default = "hello-cicd"
}

variable "ar_repo_name" {
  type    = string
  default = "apps"
}
