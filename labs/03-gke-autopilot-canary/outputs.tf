output "cluster_name" { value = google_container_cluster.autopilot.name }
output "cluster_endpoint" {
  value     = google_container_cluster.autopilot.endpoint
  sensitive = true
}
output "get_credentials_cmd" {
  value = "gcloud container clusters get-credentials ${google_container_cluster.autopilot.name} --region ${var.region} --project ${var.project_id}"
}
