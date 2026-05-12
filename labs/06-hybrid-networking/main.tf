resource "google_project_service" "apis" {
  for_each = toset([
    "compute.googleapis.com",
    "servicenetworking.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

# Two minimal VPCs to exercise HA VPN between them.
resource "google_compute_network" "vpc_a" {
  name                    = "hybrid-vpc-a"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.apis]
}

resource "google_compute_network" "vpc_b" {
  name                    = "hybrid-vpc-b"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.apis]
}

resource "google_compute_subnetwork" "subnet_a" {
  name          = "subnet-a"
  region        = var.region
  network       = google_compute_network.vpc_a.id
  ip_cidr_range = "10.100.0.0/24"
}

resource "google_compute_subnetwork" "subnet_b" {
  name          = "subnet-b"
  region        = var.secondary_region
  network       = google_compute_network.vpc_b.id
  ip_cidr_range = "10.200.0.0/24"
}

# TODO: google_compute_ha_vpn_gateway × 2, google_compute_router × 2,
# google_compute_vpn_tunnel × 4 (2 per side), google_compute_router_peer.
