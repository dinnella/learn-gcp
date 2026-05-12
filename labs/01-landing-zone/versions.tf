terraform {
  required_version = ">= 1.6.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "= 7.31.0"
    }
  }

  # Backend config injected at `terraform init` time by CI or local commands:
  #   terraform init -backend-config="bucket=..." -backend-config="prefix=labs/01-landing-zone"
  backend "gcs" {}
}

provider "google" {
  project = var.project_id
  region  = var.region
}
