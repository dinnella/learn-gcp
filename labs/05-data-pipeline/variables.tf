variable "project_id" { type = string }
variable "region" {
  type    = string
  default = "us-central1"
}
variable "topic_name" {
  type    = string
  default = "events"
}
variable "dataset_id" {
  type    = string
  default = "events_lake"
}
