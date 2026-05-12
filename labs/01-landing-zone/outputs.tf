output "vpc_self_link" {
  value = google_compute_network.vpc.self_link
}

output "primary_subnet" {
  value = google_compute_subnetwork.primary.self_link
}

output "audit_bucket" {
  value = google_storage_bucket.audit_logs.name
}
