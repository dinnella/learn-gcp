resource "google_project_service" "apis" {
  for_each = toset([
    "container.googleapis.com",
    "clouddeploy.googleapis.com",
    "artifactregistry.googleapis.com",
    "binaryauthorization.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

# Minimal Autopilot regional cluster. We omit explicit network/subnet to keep the stub
# self-contained; for production wire in lab 01's VPC via the variables.
resource "google_container_cluster" "autopilot" {
  name     = var.cluster_name
  location = var.region

  enable_autopilot = true

  # Required when enable_autopilot = true:
  ip_allocation_policy {}

  # If a VPC is provided, use it; otherwise let GKE use the default network.
  network    = var.network_self_link
  subnetwork = var.subnet_self_link

  release_channel {
    channel = "REGULAR"
  }

  deletion_protection = false

  depends_on = [google_project_service.apis]
}
