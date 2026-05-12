locals {
  required_apis = [
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "firestore.googleapis.com",
    "iam.googleapis.com",
  ]

  ar_image_uri = "${var.region}-docker.pkg.dev/${var.project_id}/${var.ar_repo_name}/${var.service_name}:${var.image_tag}"

  # Bootstrap placeholder image for the very first apply (before CI has pushed
  # anything). On subsequent applies, var.image_tag is set to the commit SHA.
  effective_image = var.image_tag == "bootstrap" ? "us-docker.pkg.dev/cloudrun/container/hello" : local.ar_image_uri
}

resource "google_project_service" "apis" {
  for_each           = toset(local.required_apis)
  service            = each.value
  disable_on_destroy = false
}

# ---------- Firestore (Native mode) ----------
# Only one Firestore database per project unless you use multi-database. We
# create the default database in the chosen location.
resource "google_firestore_database" "default" {
  name        = "(default)"
  location_id = var.firestore_location
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.apis]
}

# ---------- Artifact Registry repo for the container image ----------
resource "google_artifact_registry_repository" "apps" {
  location      = var.region
  repository_id = var.ar_repo_name
  format        = "DOCKER"
  description   = "Container images for sample apps"

  depends_on = [google_project_service.apis]
}

# ---------- Service account that Cloud Run runs as ----------
resource "google_service_account" "runtime" {
  account_id   = "${var.service_name}-sa"
  display_name = "${var.service_name} runtime SA"
}

# Read/write Firestore data.
resource "google_project_iam_member" "runtime_firestore" {
  project = var.project_id
  role    = "roles/datastore.user" # Firestore in Native mode uses the datastore.* roles
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

# Logging + Monitoring writes (so the app can emit metrics).
resource "google_project_iam_member" "runtime_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "runtime_metrics" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

# ---------- Cloud Run service ----------
resource "google_cloud_run_v2_service" "app" {
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.runtime.email

    containers {
      image = local.effective_image

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "APP_ENV"
        value = "prod"
      }
      env {
        name  = "APP_LOG_LEVEL"
        value = "INFO"
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      startup_probe {
        http_get { path = "/api/health" }
        period_seconds        = 10
        initial_delay_seconds = 5
        timeout_seconds       = 3
        failure_threshold     = 6
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }
  }

  depends_on = [
    google_firestore_database.default,
    google_artifact_registry_repository.apps,
    google_project_iam_member.runtime_firestore,
  ]

  # Image tag changes are managed by CI (which calls `gcloud run services update`
  # or re-runs apply with -var image_tag=<sha>); ignore mid-deploy churn.
  lifecycle {
    ignore_changes = [client, client_version]
  }
}

# Public access (toggleable). Not creating this binding leaves the service
# requiring an authenticated invoker (any authenticated GCP identity with
# roles/run.invoker on the project — typically still needs an explicit grant).
resource "google_cloud_run_v2_service_iam_member" "public" {
  count    = var.allow_public ? 1 : 0
  project  = var.project_id
  location = google_cloud_run_v2_service.app.location
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
