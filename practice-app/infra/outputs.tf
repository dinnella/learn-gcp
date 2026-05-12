output "service_url" {
  value = google_cloud_run_v2_service.app.uri
}

output "service_hostname" {
  description = "Bare hostname (no scheme) of the Cloud Run URL — feed to Cloudflare as origin_hostname."
  value       = replace(google_cloud_run_v2_service.app.uri, "https://", "")
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

output "lb_ip_address" {
  description = "Reserved global IP for the HTTPS LB. Point your DNS A record at this. Empty when enable_lb=false."
  value       = local.lb_enabled ? google_compute_global_address.app[0].address : ""
}

output "managed_cert_name" {
  description = "Name of the Google-managed cert; check status with `gcloud compute ssl-certificates describe`."
  value       = local.lb_enabled ? google_compute_managed_ssl_certificate.app[0].name : ""
}

output "public_url" {
  description = "Final user-facing URL once DNS + cert are live."
  value       = local.lb_enabled ? "https://${var.domain}" : google_cloud_run_v2_service.app.uri
}
