locals {
  required_apis = [
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "firestore.googleapis.com",
    "iam.googleapis.com",
    "compute.googleapis.com",
    "certificatemanager.googleapis.com",
    "containerscanning.googleapis.com",
    "secretmanager.googleapis.com",
  ]

  ar_image_uri = "${var.region}-docker.pkg.dev/${var.project_id}/${var.ar_repo_name}/${var.service_name}:${var.image_tag}"

  # Bootstrap placeholder image for the very first apply (before CI has pushed
  # anything). On subsequent applies, var.image_tag is set to the commit SHA.
  effective_image = var.image_tag == "bootstrap" ? "us-docker.pkg.dev/cloudrun/container/hello" : local.ar_image_uri

  lb_enabled       = var.enable_lb && var.domain != ""
  cloud_run_ingress = var.restrict_ingress_to_lb ? "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER" : "INGRESS_TRAFFIC_ALL"
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

  # Point-in-time recovery: 7-day window of historical reads + restore.
  point_in_time_recovery_enablement = "POINT_IN_TIME_RECOVERY_ENABLED"
  # Refuse `tofu destroy` of the database; remove this if you ever need to nuke it.
  delete_protection_state = "DELETE_PROTECTION_ENABLED"

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

# ---------- Edge shared secret (Cloudflare → origin) ----------
# Created/updated only when var.edge_shared_secret is non-empty. Stored in
# Secret Manager so it never appears in Cloud Run's plain-env config.
resource "google_secret_manager_secret" "edge_auth" {
  count     = var.edge_shared_secret == "" ? 0 : 1
  secret_id = "${var.service_name}-edge-auth"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "edge_auth" {
  count       = var.edge_shared_secret == "" ? 0 : 1
  secret      = google_secret_manager_secret.edge_auth[0].id
  secret_data = var.edge_shared_secret
}

resource "google_secret_manager_secret_iam_member" "edge_auth_runtime" {
  count     = var.edge_shared_secret == "" ? 0 : 1
  secret_id = google_secret_manager_secret.edge_auth[0].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

# ---------- Cloud Run service ----------
resource "google_cloud_run_v2_service" "app" {
  name     = var.service_name
  location = var.region
  ingress  = local.cloud_run_ingress

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

      dynamic "env" {
        for_each = var.edge_shared_secret == "" ? [] : [1]
        content {
          name = "EDGE_SHARED_SECRET"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.edge_auth[0].secret_id
              version = "latest"
            }
          }
        }
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
