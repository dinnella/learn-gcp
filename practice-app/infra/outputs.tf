output "service_url" {
  value = google_cloud_run_v2_service.app.uri
}

output "service_account_email" {
  value = google_service_account.runtime.email
}

output "image_uri" {
  value = local.ar_image_uri
}

output "ar_docker_host" {
  value = "${var.region}-docker.pkg.dev"
}

output "ar_repo_path" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${var.ar_repo_name}"
}
