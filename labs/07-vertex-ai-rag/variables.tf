variable "project_id" { type = string }
variable "region" {
  type    = string
  default = "us-central1"
}
variable "corpus_bucket_name" {
  description = "GCS bucket holding source documents for the RAG corpus."
  type        = string
}
