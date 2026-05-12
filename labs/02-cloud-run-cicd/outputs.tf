output "service_url" {
  value = google_cloud_run_v2_service.hello.uri
}

output "ar_repo_path" {
  value = "${google_artifact_registry_repository.apps.location}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.apps.repository_id}"
}
