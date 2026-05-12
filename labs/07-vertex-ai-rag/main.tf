resource "google_project_service" "apis" {
  for_each = toset([
    "aiplatform.googleapis.com",
    "discoveryengine.googleapis.com",
    "run.googleapis.com",
    "storage.googleapis.com",
    "modelarmor.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "corpus" {
  name                        = var.corpus_bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true

  depends_on = [google_project_service.apis]
}

# TODO: google_discovery_engine_data_store + google_discovery_engine_search_engine
# TODO: Cloud Run service calling Vertex AI Gemini SDK
# TODO: Model Armor template binding
