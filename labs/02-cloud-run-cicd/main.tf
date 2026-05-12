locals {
  required_apis = [
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "clouddeploy.googleapis.com",
    "binaryauthorization.googleapis.com",
    "containeranalysis.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.required_apis)
  service            = each.value
  disable_on_destroy = false
}

# ---------- Artifact Registry ----------

resource "google_artifact_registry_repository" "apps" {
  location      = var.region
  repository_id = var.ar_repo_name
  description   = "Container images for sample apps"
  format        = "DOCKER"

  depends_on = [google_project_service.apis]
}

# ---------- Cloud Run service (placeholder image until CI pushes a real one) ----------

resource "google_cloud_run_v2_service" "hello" {
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    containers {
      # Placeholder; replace with AR image once CI is wired.
      image = "us-docker.pkg.dev/cloudrun/container/hello"

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }
  }

  depends_on = [google_project_service.apis]
}

# Authenticated invocation only (no public allUsers).
# To allow public access add a google_cloud_run_v2_service_iam_member with role roles/run.invoker, member allUsers.
