# Enable APIs required for the bootstrap itself + WIF.
resource "google_project_service" "apis" {
  for_each = toset(var.enabled_apis)

  service            = each.value
  disable_on_destroy = false
}

# ---------- Terraform state bucket ----------

resource "google_storage_bucket" "tfstate" {
  name                        = var.tfstate_bucket_name
  location                    = var.region
  force_destroy               = false
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      num_newer_versions = 10
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.apis]
}

# ---------- Workload Identity Federation for GitHub Actions ----------

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = var.wif_pool_id
  display_name              = "GitHub Actions pool"
  description               = "Trust anchor for GitHub OIDC tokens"

  depends_on = [google_project_service.apis]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = var.wif_provider_id
  display_name                       = "GitHub OIDC provider"

  attribute_mapping = {
    "google.subject"             = "assertion.sub"
    "attribute.actor"            = "assertion.actor"
    "attribute.repository"       = "assertion.repository"
    "attribute.repository_owner" = "assertion.repository_owner"
    "attribute.ref"              = "assertion.ref"
    "attribute.event_name"       = "assertion.event_name"
  }

  # Restrict to your repo only — without this, ANY GitHub repo could mint tokens.
  attribute_condition = "assertion.repository == \"${var.github_repo}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# ---------- Deployer service account ----------

resource "google_service_account" "deployer" {
  account_id   = var.deployer_sa_id
  display_name = "Terraform deployer (CI)"
  description  = "Impersonated by GitHub Actions via WIF to run Terraform."
}

# Allow GitHub Actions running in our repo to impersonate the deployer SA.
resource "google_service_account_iam_member" "deployer_wif_binding" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repo}"
}

# Lab-scope grant: deployer gets project-level owner.
# In a real org this would be much narrower (per-environment SAs with per-folder roles).
resource "google_project_iam_member" "deployer_owner" {
  project = var.project_id
  role    = "roles/owner"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

# Grant the deployer access to the state bucket explicitly (defense in depth — even if
# project owner were narrowed, state access still works).
resource "google_storage_bucket_iam_member" "deployer_state" {
  bucket = google_storage_bucket.tfstate.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.deployer.email}"
}
