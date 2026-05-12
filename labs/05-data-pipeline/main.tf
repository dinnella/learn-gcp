resource "google_project_service" "apis" {
  for_each = toset([
    "pubsub.googleapis.com",
    "bigquery.googleapis.com",
    "dataflow.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

resource "google_pubsub_topic" "events" {
  name = var.topic_name

  depends_on = [google_project_service.apis]
}

resource "google_bigquery_dataset" "lake" {
  dataset_id = var.dataset_id
  location   = var.region

  depends_on = [google_project_service.apis]
}

resource "google_bigquery_table" "events" {
  dataset_id = google_bigquery_dataset.lake.dataset_id
  table_id   = "events"

  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = null # ingestion-time partitioning
  }

  schema = jsonencode([
    { name = "event_id", type = "STRING", mode = "REQUIRED" },
    { name = "event_ts", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "payload", type = "JSON", mode = "NULLABLE" },
  ])
}

# TODO: google_dataflow_flex_template_job for Pub/Sub → BigQuery template.
