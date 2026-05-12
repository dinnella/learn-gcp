resource "google_project_service" "apis" {
  for_each = toset([
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "cloudtrace.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

# Log-based counter metric: count log entries with severity=ERROR for the target Cloud Run service.
resource "google_logging_metric" "service_errors" {
  name   = "cloud-run-${var.cloud_run_service_name}-errors"
  filter = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${var.cloud_run_service_name}\" AND severity>=ERROR"

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }

  depends_on = [google_project_service.apis]
}

# TODO (build out): google_monitoring_service + google_monitoring_slo + alert policies + dashboard.
# Stubbed here so terraform validate passes with at least one observability resource.
