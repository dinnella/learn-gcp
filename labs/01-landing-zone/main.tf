locals {
  required_apis = [
    "compute.googleapis.com",
    "logging.googleapis.com",
    "orgpolicy.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.required_apis)
  service            = each.value
  disable_on_destroy = false
}

# ---------- Custom-mode VPC ----------

resource "google_compute_network" "vpc" {
  name                    = var.network_name
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"

  depends_on = [google_project_service.apis]
}

resource "google_compute_subnetwork" "primary" {
  name                     = "${var.network_name}-${var.region}"
  ip_cidr_range            = "10.10.0.0/20"
  region                   = var.region
  network                  = google_compute_network.vpc.id
  private_ip_google_access = true

  log_config {
    aggregation_interval = "INTERVAL_10_MIN"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

resource "google_compute_subnetwork" "secondary" {
  name                     = "${var.network_name}-${var.secondary_region}"
  ip_cidr_range            = "10.20.0.0/20"
  region                   = var.secondary_region
  network                  = google_compute_network.vpc.id
  private_ip_google_access = true
}

# ---------- Firewall rules ----------
# Default-deny ingress is implicit in GCP. We explicitly allow IAP SSH only.

resource "google_compute_firewall" "allow_iap_ssh" {
  name      = "${var.network_name}-allow-iap-ssh"
  network   = google_compute_network.vpc.name
  direction = "INGRESS"
  priority  = 1000

  # IAP TCP forwarding source range — Google-published.
  source_ranges = ["35.235.240.0/20"]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}

# ---------- Audit log archive ----------

resource "google_storage_bucket" "audit_logs" {
  name                        = "${var.project_id}-audit-logs"
  location                    = var.region
  force_destroy               = false
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type          = "SetStorageClass"
      storage_class = "ARCHIVE"
    }
  }
}

resource "google_logging_project_sink" "audit" {
  name        = "audit-archive"
  destination = "storage.googleapis.com/${google_storage_bucket.audit_logs.name}"

  # Admin Activity audit logs only (Data Access logs cost extra).
  filter = "logName:\"cloudaudit.googleapis.com%2Factivity\""

  unique_writer_identity = true
}

# Grant the sink's writer identity permission to write to the bucket.
resource "google_storage_bucket_iam_member" "audit_writer" {
  bucket = google_storage_bucket.audit_logs.name
  role   = "roles/storage.objectCreator"
  member = google_logging_project_sink.audit.writer_identity
}

# ---------- Org policy at project level ----------
# These constraints are built-in. See: https://cloud.google.com/resource-manager/docs/organization-policy/org-policy-constraints

resource "google_org_policy_policy" "require_os_login" {
  name   = "projects/${var.project_id}/policies/compute.requireOsLogin"
  parent = "projects/${var.project_id}"

  spec {
    rules {
      enforce = "TRUE"
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_org_policy_policy" "disable_serial_port" {
  name   = "projects/${var.project_id}/policies/compute.disableSerialPortAccess"
  parent = "projects/${var.project_id}"

  spec {
    rules {
      enforce = "TRUE"
    }
  }

  depends_on = [google_project_service.apis]
}
